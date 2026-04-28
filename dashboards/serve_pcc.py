#!/usr/bin/env python3
"""
Protocol Command Center (PCC) — V2 production server.

Single-process HTTP server bound to 0.0.0.0:8079, serving:
  GET  /                 -> protocol_command_center.html
  GET  /api/health_data  -> adapted Apple Health snapshot
  GET  /api/scans        -> scan history
  POST /api/save_scan    -> writes scans.json + decoded photos
  POST /api/insight      -> Claude CLI weekly OverwatchTDO synthesis
  GET  /healthz          -> liveness probe

Run:  python3 serve_pcc.py --port 8079

Source-of-truth health_data.json is the canonical Lifeos file under
~/Documents/S6_COMMS_TECH/dashboard/health/. PCC adapts that shape into
the form the HTML expects. If absent, falls back to deterministic mock.
"""

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# --- paths ---
HOME = Path.home()
REPO = HOME / "owens-lifeos"
DASH_DIR = REPO / "dashboards"
DATA_DIR = REPO / "data"
PHOTO_DIR = DATA_DIR / "progress_photos"
LOG_DIR = REPO / "logs"

PCC_HTML = DASH_DIR / "protocol_command_center.html"

# Health data source priority:
#   1. PCC_DATA_FILE — local mirror in repo (TCC-safe under launchd)
#   2. LIFEOS_DATA_FILE — canonical iCloud path (works only when caller has FDA;
#      LaunchAgents typically don't, so this is foreground-only fallback)
# Mirror refresh is the orchestrator's job — see skill for runbook.
PCC_DATA_FILE = DATA_DIR / "health_data.json"
LIFEOS_DATA_FILE = HOME / "Documents" / "S6_COMMS_TECH" / "dashboard" / "health" / "health_data.json"
SCANS_FILE = DATA_DIR / "scans.json"
PHASE_STATE_FILE = DATA_DIR / "phase_state.json"
PHASE_ORDER = ("A", "B", "C", "M")

CLAUDE_CLI = shutil.which("claude") or str(HOME / ".local" / "bin" / "claude")


# --- adapter ---
def _safe_get(d, *path, default=None):
    cur = d
    for p in path:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return default
    return cur


def _parse_label_to_date(label, ref_year):
    """'Apr 17' -> date(2026,4,17). Year inferred from meta.last_updated."""
    try:
        return datetime.strptime(f"{label} {ref_year}", "%b %d %Y").date()
    except ValueError:
        return None


def _build_history_from_trends(trends, ref_year, latest_fields):
    """Merge trends.{weight,hrv,sleep,steps} into a date-keyed history."""
    by_date = {}
    for metric_key, trend_key in [
        ("weight", "weight"),
        ("hrv", "hrv"),
        ("sleep_total", "sleep"),
        ("steps", "steps"),
    ]:
        t = trends.get(trend_key) or {}
        labels = t.get("labels") or []
        values = t.get("values") or []
        for label, val in zip(labels, values):
            d = _parse_label_to_date(label, ref_year)
            if not d:
                continue
            by_date.setdefault(d, {})[metric_key] = val

    rows = []
    for d in sorted(by_date.keys()):
        row = {
            "date": d.isoformat(),
            "dow": (d.weekday() + 1) % 7,  # 0=Sun
            "weight": by_date[d].get("weight", latest_fields.get("weight")),
            "sleep_total": by_date[d].get("sleep_total", latest_fields.get("sleep_total")),
            "sleep_deep": latest_fields.get("sleep_deep"),
            "sleep_rem": latest_fields.get("sleep_rem"),
            "hrv": by_date[d].get("hrv", latest_fields.get("hrv")),
            "rhr": latest_fields.get("rhr"),
            "steps": by_date[d].get("steps", latest_fields.get("steps")),
            "active_cal": latest_fields.get("active_cal"),
            "workout": None,
        }
        rows.append(row)
    return rows


def _attach_workouts(history, workouts):
    by_date = {}
    for w in workouts or []:
        date = w.get("date")
        if not date:
            continue
        existing = by_date.get(date)
        if existing is None or w.get("duration_min", 0) > existing.get("duration_min", 0):
            by_date[date] = {
                "type": w.get("name"),
                "duration_min": int(round(w.get("duration_min", 0))),
            }
    for row in history:
        if row["date"] in by_date:
            row["workout"] = by_date[row["date"]]
    return history


def _passthrough_if_pcc_shape(raw):
    if isinstance(raw, dict) and "history" in raw and "latest" in raw and "avg_30d" in raw:
        raw.setdefault("source", "live")
        raw.setdefault("updated_at", datetime.now(timezone.utc).isoformat())
        return raw
    return None


def load_health_data():
    """Read canonical lifeos health_data.json and adapt to PCC shape.

    Probes the local mirror FIRST (TCC-safe under launchd), then the iCloud
    canonical path. If both fail, returns deterministic mock so UI still renders.
    """
    src_file = None
    for candidate in (PCC_DATA_FILE, LIFEOS_DATA_FILE):
        try:
            if candidate.exists():
                src_file = candidate
                break
        except OSError:
            # iCloud fileprovider may raise on stat() under launchd; skip
            continue
    if src_file is None:
        return _mock_payload(reason="no health_data.json found in expected paths")

    try:
        raw = json.loads(src_file.read_text())
    except Exception as e:
        return _mock_payload(reason=f"parse error: {e}")

    pass_through = _passthrough_if_pcc_shape(raw)
    if pass_through is not None:
        return pass_through

    # Adapter: lifeos canonical shape -> PCC shape
    last_updated = _safe_get(raw, "meta", "last_updated", default=datetime.now(timezone.utc).isoformat())
    try:
        ref_year = datetime.fromisoformat(last_updated.replace("Z", "")).year
    except Exception:
        ref_year = datetime.now(timezone.utc).year

    vs = raw.get("vital_signs", {}) or {}
    rec = raw.get("recovery", {}) or {}
    rec_inputs = rec.get("inputs", {}) or {}
    sleep_inputs = rec_inputs.get("sleep", {}) or {}
    macros = raw.get("macros", {}) or {}

    latest = {
        "weight": _safe_get(vs, "weight", "value"),
        "body_fat": _safe_get(vs, "body_fat", "value"),
        "sleep_total": sleep_inputs.get("total") or _safe_get(vs, "sleep_avg", "value"),
        "sleep_deep": sleep_inputs.get("deep") or _safe_get(vs, "deep_sleep_avg", "value"),
        "sleep_rem": sleep_inputs.get("rem"),
        "hrv": _safe_get(rec_inputs, "hrv", "value") or _safe_get(vs, "hrv", "value"),
        "rhr": _safe_get(rec_inputs, "rhr", "value") or _safe_get(vs, "resting_heart_rate", "value"),
        "steps": _safe_get(vs, "steps_avg", "value"),
        "active_cal": None,
        "workout_today": None,
        "macros_today": {
            "calories": {
                "current": _safe_get(macros, "calories", "current"),
                "target": _safe_get(macros, "calories", "target"),
            },
            "protein": {
                "current": _safe_get(macros, "protein", "current"),
                "target": _safe_get(macros, "protein", "target"),
            },
            "carbs": {
                "current": _safe_get(macros, "carbs", "current"),
                "target": _safe_get(macros, "carbs", "target"),
            },
            "fat": {
                "current": _safe_get(macros, "fat", "current"),
                "target": _safe_get(macros, "fat", "target"),
            },
        },
        "recovery": {
            "score": rec.get("score"),
            "status": rec.get("status"),
            "color": rec.get("color"),
            "recommendation": rec.get("recommendation"),
        },
    }

    history = _build_history_from_trends(raw.get("trends", {}) or {}, ref_year, latest)
    history = _attach_workouts(history, raw.get("workouts"))

    today_iso = datetime.now().date().isoformat()
    today_workouts = [w for w in (raw.get("workouts") or []) if w.get("date") == today_iso]
    if today_workouts:
        primary = max(today_workouts, key=lambda w: w.get("duration_min", 0))
        latest["workout_today"] = {
            "type": primary.get("name"),
            "duration_min": int(round(primary.get("duration_min", 0))),
        }
        latest["active_cal"] = sum(int(w.get("active_cal", 0) or 0) for w in today_workouts)

    def avg(field):
        vals = [r.get(field) for r in history if r.get(field) is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    avg_30d = {
        "hrv": avg("hrv"),
        "sleep_total": avg("sleep_total"),
        "sleep_deep": _safe_get(raw, "sleep_intelligence", "summary", "avg_deep_sleep"),
    }

    return {
        "updated_at": last_updated,
        "source": "live",
        "source_file": str(src_file),
        "latest": latest,
        "avg_30d": avg_30d,
        "history": history,
        "training_plan": raw.get("training_plan"),
        "sleep_intelligence_summary": _safe_get(raw, "sleep_intelligence", "summary"),
    }


def _mock_payload(reason="mock"):
    today = datetime.now().date()
    history = []
    weight = 217.0
    for i in range(30):
        d = today - timedelta(days=29 - i)
        history.append({
            "date": d.isoformat(),
            "dow": (d.weekday() + 1) % 7,
            "weight": round(weight - i * 0.05, 1),
            "sleep_total": round(6.8 + (i % 5) * 0.1, 1),
            "sleep_deep": round(0.4 + (i % 3) * 0.1, 1),
            "sleep_rem": round(1.6 + (i % 4) * 0.1, 1),
            "hrv": 36 + (i % 6),
            "rhr": 68 + (i % 4),
            "steps": 9000 + (i * 173) % 4000,
            "active_cal": 250 + (i * 11) % 200,
            "workout": None,
        })
    last = history[-1]
    latest = {
        "weight": last["weight"],
        "body_fat": 19.5,
        "sleep_total": last["sleep_total"],
        "sleep_deep": last["sleep_deep"],
        "sleep_rem": last["sleep_rem"],
        "hrv": last["hrv"],
        "rhr": last["rhr"],
        "steps": last["steps"],
        "active_cal": last["active_cal"],
        "workout_today": None,
        "macros_today": {
            "calories": {"current": 0, "target": 2000},
            "protein":  {"current": 0, "target": 220},
            "carbs":    {"current": 0, "target": 130},
            "fat":      {"current": 0, "target": 80},
        },
        "recovery": {
            "score": 70,
            "status": "MODERATE",
            "color": "yellow",
            "recommendation": "Mock recovery — health_data.json not yet wired.",
        },
    }
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "mock",
        "mock_reason": reason,
        "latest": latest,
        "avg_30d": {"hrv": 38, "sleep_total": 6.9, "sleep_deep": 0.5},
        "history": history,
        "training_plan": None,
        "sleep_intelligence_summary": None,
    }


# --- scan write ---
def save_scan(payload):
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    SCANS_FILE.parent.mkdir(parents=True, exist_ok=True)

    scan_date = (payload.get("date") or datetime.now().date().isoformat())[:10]
    photos_today = PHOTO_DIR / scan_date
    photos_today.mkdir(parents=True, exist_ok=True)

    saved_photos = {}
    for slot in ("front", "side", "back"):
        b64 = (payload.get("photos") or {}).get(slot)
        if not b64:
            continue
        if b64.startswith("data:"):
            try:
                _, b64 = b64.split(",", 1)
            except ValueError:
                continue
        try:
            data = base64.b64decode(b64)
        except Exception:
            continue
        out = photos_today / f"{slot}.jpg"
        out.write_bytes(data)
        saved_photos[slot] = str(out)

    record = {
        "date": scan_date,
        "ts": datetime.now(timezone.utc).isoformat(),
        "phase": payload.get("phase"),
        "weight": payload.get("weight"),
        "body_fat": payload.get("body_fat"),
        "lean_mass": payload.get("lean_mass"),
        "fat_mass": payload.get("fat_mass"),
        "notes": payload.get("notes"),
        "photos": saved_photos,
    }

    history = []
    if SCANS_FILE.exists():
        try:
            history = json.loads(SCANS_FILE.read_text())
            if not isinstance(history, list):
                history = []
        except Exception:
            history = []
    history = [s for s in history if s.get("date") != record["date"]]
    history.append(record)
    history.sort(key=lambda s: s.get("date", ""))
    SCANS_FILE.write_text(json.dumps(history, indent=2))
    return record, history


def load_scans():
    if not SCANS_FILE.exists():
        return []
    try:
        data = json.loads(SCANS_FILE.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


# --- protocol-shape (HTML v2.2) helpers ---
def load_phase_state():
    """Return {'phase': str, 'history': [...]}. Default to Phase A if missing."""
    if not PHASE_STATE_FILE.exists():
        return {"phase": "A", "history": []}
    try:
        data = json.loads(PHASE_STATE_FILE.read_text())
        if not isinstance(data, dict) or "phase" not in data:
            return {"phase": "A", "history": []}
        data.setdefault("history", [])
        return data
    except Exception:
        return {"phase": "A", "history": []}


def save_phase_state(state):
    PHASE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PHASE_STATE_FILE.write_text(json.dumps(state, indent=2))


def load_canonical_health():
    """Return raw lifeos canonical health_data.json with phase override merged.

    The new HTML reads HEALTH.vital_signs.weight.value etc. directly, so we
    serve the canonical shape unmodified (mirror-first, iCloud fallback).
    Phase comes from phase_state.json (server-side override) — merged into
    the served document at protocol.phase so the dashboard sees it.
    """
    src_file = None
    for candidate in (PCC_DATA_FILE, LIFEOS_DATA_FILE):
        try:
            if candidate.exists():
                src_file = candidate
                break
        except OSError:
            continue
    if src_file is None:
        return {"meta": {"last_updated": datetime.now(timezone.utc).isoformat(),
                         "source": "missing"},
                "vital_signs": {}, "macros": {}, "workouts": [],
                "protocol": {"phase": load_phase_state().get("phase", "A")}}
    try:
        raw = json.loads(src_file.read_text())
    except Exception as e:
        return {"meta": {"last_updated": datetime.now(timezone.utc).isoformat(),
                         "source": f"parse-error: {e}"},
                "vital_signs": {}, "macros": {}, "workouts": [],
                "protocol": {"phase": load_phase_state().get("phase", "A")}}

    # merge phase override
    state = load_phase_state()
    proto = raw.get("protocol")
    if not isinstance(proto, dict):
        proto = {}
    proto["phase"] = state.get("phase", "A")
    proto["phase_history"] = state.get("history", [])
    raw["protocol"] = proto
    return raw


def save_protocol_scan(payload):
    """Append/replace a JSON-shape scan record in scans.json.

    The HTML v2.2 POSTs date/weight/bf_pct/fat_mass/lean_mass/skeletal_muscle/
    body_water_pct/visceral_fat/hct/notes (no photos in this payload — those
    arrive via /api/protocol/save_photo).
    """
    SCANS_FILE.parent.mkdir(parents=True, exist_ok=True)
    scan_date = (payload.get("date") or datetime.now().date().isoformat())[:10]

    record = {
        "date": scan_date,
        "ts": datetime.now(timezone.utc).isoformat(),
        "phase": load_phase_state().get("phase", "A"),
        "weight": payload.get("weight"),
        "bf_pct": payload.get("bf_pct"),
        "fat_mass": payload.get("fat_mass"),
        "lean_mass": payload.get("lean_mass"),
        "skeletal_muscle": payload.get("skeletal_muscle"),
        "body_water_pct": payload.get("body_water_pct"),
        "visceral_fat": payload.get("visceral_fat"),
        "hct": payload.get("hct"),
        "notes": payload.get("notes") or "",
    }

    history = load_scans()
    history = [s for s in history if s.get("date") != record["date"]]
    history.append(record)
    history.sort(key=lambda s: s.get("date", ""))
    SCANS_FILE.write_text(json.dumps(history, indent=2))
    return record, history


def save_protocol_photo(view, scan_date, ext, body):
    """Write a single photo to progress_photos/<date>/<view>.<ext>."""
    if view not in ("front", "side", "back"):
        raise ValueError(f"invalid view: {view}")
    scan_date = scan_date or datetime.now().date().isoformat()
    scan_date = scan_date[:10]
    target_dir = PHOTO_DIR / scan_date
    target_dir.mkdir(parents=True, exist_ok=True)
    if not ext:
        ext = "jpg"
    ext = ext.lstrip(".").lower()
    if ext not in ("jpg", "jpeg", "png", "heic", "heif", "webp"):
        ext = "jpg"
    out = target_dir / f"{view}.{ext}"
    out.write_bytes(body)
    return out


def advance_phase():
    """Bump phase A->B->C->M. Records history with timestamp."""
    state = load_phase_state()
    cur = state.get("phase", "A")
    try:
        nxt_idx = PHASE_ORDER.index(cur) + 1
    except ValueError:
        nxt_idx = 0
    if nxt_idx >= len(PHASE_ORDER):
        return state, False
    new_phase = PHASE_ORDER[nxt_idx]
    state["phase"] = new_phase
    state.setdefault("history", []).append({
        "phase": new_phase,
        "previous": cur,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    save_phase_state(state)
    return state, True


# --- minimal multipart/form-data parser (single-file uploads) ---
def parse_multipart(content_type, body):
    """Return {field_name: {'data': bytes, 'filename': str|None, 'ctype': str|None}}.

    Stdlib-only. Handles RFC 7578 form data with text + binary fields.
    Boundary extracted from the Content-Type header.
    """
    if not content_type or "multipart/form-data" not in content_type.lower():
        return {}
    marker = "boundary="
    idx = content_type.lower().find(marker)
    if idx < 0:
        return {}
    boundary = content_type[idx + len(marker):].strip()
    if ";" in boundary:
        boundary = boundary.split(";", 1)[0].strip()
    if boundary.startswith('"') and boundary.endswith('"'):
        boundary = boundary[1:-1]
    delim = ("--" + boundary).encode()
    parts = body.split(delim)
    out = {}
    for part in parts[1:-1]:
        # strip the leading \r\n and trailing \r\n
        if part.startswith(b"\r\n"):
            part = part[2:]
        if part.endswith(b"\r\n"):
            part = part[:-2]
        if not part:
            continue
        try:
            headers_blob, content = part.split(b"\r\n\r\n", 1)
        except ValueError:
            continue
        # remove trailing \r\n that precedes the next boundary
        if content.endswith(b"\r\n"):
            content = content[:-2]
        name = None
        filename = None
        ctype = None
        for line in headers_blob.decode("utf-8", errors="replace").split("\r\n"):
            low = line.lower()
            if low.startswith("content-disposition:"):
                for tok in line.split(";"):
                    tok = tok.strip()
                    if tok.lower().startswith("name="):
                        name = tok.split("=", 1)[1].strip().strip('"')
                    elif tok.lower().startswith("filename="):
                        filename = tok.split("=", 1)[1].strip().strip('"')
            elif low.startswith("content-type:"):
                ctype = line.split(":", 1)[1].strip()
        if name:
            out[name] = {"data": content, "filename": filename, "ctype": ctype}
    return out


def _ext_from_upload(field):
    """Derive a file extension from filename or content-type."""
    fn = (field or {}).get("filename") or ""
    if "." in fn:
        return fn.rsplit(".", 1)[1]
    ct = ((field or {}).get("ctype") or "").lower()
    if "jpeg" in ct or "jpg" in ct: return "jpg"
    if "png" in ct: return "png"
    if "heic" in ct or "heif" in ct: return "heic"
    if "webp" in ct: return "webp"
    return "jpg"


# --- insight via Claude CLI ---
INSIGHT_FALLBACK = (
    "OverwatchTDO insight unavailable (Claude CLI not reachable). "
    "Deterministic summary: review week-over-week LM and BF deltas; "
    "if LM dropped >=2 lb across 3 scans, flag RED."
)


def generate_insight(scans, health):
    """Compose a tight prompt and pipe through Claude CLI via stdin."""
    last_3 = scans[-3:] if isinstance(scans, list) else []
    latest_recovery = (health or {}).get("latest", {}).get("recovery") if health else None
    avg_trends = (health or {}).get("avg_30d", {}) if health else {}

    prompt = (
        "You are OverwatchTDO. Read this scan + recovery snapshot and return "
        "a 4-6 line weekly insight for the Commander.\n"
        "TRUTH ABOVE ALL — name the trend; if the body is regressing, say it.\n\n"
        "Recent scans (most recent last):\n"
        + json.dumps(last_3, indent=2)
        + "\n\nLatest recovery:\n"
        + json.dumps(latest_recovery, indent=2)
        + "\n\nAvg trends:\n"
        + json.dumps(avg_trends, indent=2)
        + "\n\nOutput: 4-6 lines, BLUF first. No preamble. No sign-off.\n"
    )

    try:
        proc = subprocess.run(
            [CLAUDE_CLI, "-p"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return {"source": "claude_cli", "text": proc.stdout.strip()}
        return {
            "source": "fallback",
            "text": INSIGHT_FALLBACK,
            "stderr": (proc.stderr or "")[:300],
        }
    except FileNotFoundError:
        return {"source": "fallback", "text": INSIGHT_FALLBACK, "error": "claude CLI not found"}
    except subprocess.TimeoutExpired:
        return {"source": "fallback", "text": INSIGHT_FALLBACK, "error": "claude CLI timeout"}
    except Exception as e:  # noqa: BLE001
        return {"source": "fallback", "text": INSIGHT_FALLBACK, "error": str(e)}


# --- HTTP handler ---
class PCCHandler(BaseHTTPRequestHandler):
    server_version = "PCC/2.0"

    def log_message(self, fmt, *args):
        sys.stderr.write(
            "[%s] %s - %s\n"
            % (datetime.now().isoformat(timespec="seconds"), self.address_string(), fmt % args)
        )

    def _send_json(self, body, status=200):
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path: Path, ctype: str):
        if not path.exists():
            self.send_error(404, f"{path.name} missing")
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html", "/pcc", "/protocol_command_center.html"):
            return self._send_file(PCC_HTML, "text/html; charset=utf-8")
        # New HTML v2.2 reads canonical lifeos shape directly
        if path == "/health/health_data.json":
            return self._send_json(load_canonical_health())
        if path == "/data/scans.json":
            return self._send_json(load_scans())
        if path == "/api/iron_discipline":
            try:
                p = DATA_DIR / "iron_discipline.json"
                if p.exists():
                    body = json.loads(p.read_text())
                    return self._send_json(body)
            except Exception:
                pass
            return self._send_json({"error": "iron_discipline.json missing"}, 404)
        # Legacy (kept for backward compat)
        if path == "/api/health_data":
            return self._send_json(load_health_data())
        if path == "/api/scans":
            return self._send_json({"scans": load_scans()})
        if path == "/healthz":
            return self._send_json({"ok": True, "ts": datetime.now(timezone.utc).isoformat()})
        if path.startswith("/fonts/") and path.endswith(".woff2"):
            font_path = (DASH_DIR / "fonts" / path[len("/fonts/"):]).resolve()
            try:
                font_path.relative_to((DASH_DIR / "fonts").resolve())
            except ValueError:
                self.send_error(403)
                return
            if not font_path.exists():
                self.send_error(404)
                return
            body = font_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "font/woff2")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
            return
        candidate = (DASH_DIR / path.lstrip("/")).resolve()
        try:
            candidate.relative_to(DASH_DIR.resolve())
        except ValueError:
            return self.send_error(404, "not found")
        if candidate.is_file():
            ctype = "application/octet-stream"
            suf = candidate.suffix.lower()
            if suf == ".js": ctype = "application/javascript"
            elif suf == ".css": ctype = "text/css"
            elif suf == ".svg": ctype = "image/svg+xml"
            elif suf == ".png": ctype = "image/png"
            elif suf in (".jpg", ".jpeg"): ctype = "image/jpeg"
            elif suf == ".html": ctype = "text/html"
            elif suf == ".json": ctype = "application/json"
            return self._send_file(candidate, ctype)
        self.send_error(404, "not found")

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        body_raw = self.rfile.read(length) if length else b""
        ctype = self.headers.get("Content-Type", "")

        # New protocol routes (HTML v2.2)
        if self.path == "/api/protocol/save_scan":
            try:
                payload = json.loads(body_raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                return self._send_json({"error": "invalid json"}, status=400)
            try:
                record, history = save_protocol_scan(payload)
                return self._send_json({"ok": True, "record": record, "count": len(history)})
            except Exception as e:  # noqa: BLE001
                return self._send_json({"ok": False, "error": str(e)}, status=500)

        if self.path == "/api/protocol/save_photo":
            try:
                fields = parse_multipart(ctype, body_raw)
                if not fields or "photo" not in fields:
                    return self._send_json({"ok": False, "error": "no photo field"}, status=400)
                view = (fields.get("view") or {}).get("data", b"").decode("utf-8", errors="replace") or "front"
                date = (fields.get("date") or {}).get("data", b"").decode("utf-8", errors="replace") or None
                photo = fields["photo"]
                ext = _ext_from_upload(photo)
                out = save_protocol_photo(view, date, ext, photo["data"])
                return self._send_json({"ok": True, "view": view, "date": date, "path": str(out)})
            except Exception as e:  # noqa: BLE001
                return self._send_json({"ok": False, "error": str(e)}, status=500)

        if self.path == "/api/protocol/advance_phase":
            try:
                state, advanced = advance_phase()
                return self._send_json({"ok": True, "advanced": advanced, "state": state})
            except Exception as e:  # noqa: BLE001
                return self._send_json({"ok": False, "error": str(e)}, status=500)

        if self.path == "/api/log_protein":
            try:
                body = json.loads(body_raw.decode("utf-8") or "{}")
                grams = float(body.get("grams", 0) or 0)
                ts = body.get("ts") or datetime.now(timezone.utc).isoformat()
                log_path = DATA_DIR / "protein_log.json"
                entries = []
                if log_path.exists():
                    try:
                        entries = json.loads(log_path.read_text())
                        if not isinstance(entries, list):
                            entries = []
                    except Exception:
                        entries = []
                entries.append({"grams": grams, "ts": ts})
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.write_text(json.dumps(entries, indent=2))
                return self._send_json({"ok": True, "logged_g": grams, "count": len(entries)})
            except Exception as e:  # noqa: BLE001
                return self._send_json({"ok": False, "error": str(e)}, status=500)

        if self.path == "/api/log_workout":
            try:
                body = json.loads(body_raw.decode("utf-8") or "{}")
                log_path = DATA_DIR / "workout_log.json"
                entries = []
                if log_path.exists():
                    try:
                        entries = json.loads(log_path.read_text())
                        if not isinstance(entries, list):
                            entries = []
                    except Exception:
                        entries = []
                record = dict(body)
                record["ts"] = datetime.now(timezone.utc).isoformat()
                entries.append(record)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.write_text(json.dumps(entries, indent=2))
                return self._send_json({"ok": True, "session_id": len(entries)})
            except Exception as e:  # noqa: BLE001
                return self._send_json({"ok": False, "error": str(e)}, status=500)

        # Legacy routes (JSON body required)
        try:
            payload = json.loads(body_raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return self._send_json({"error": "invalid json"}, status=400)

        if self.path == "/api/save_scan":
            try:
                record, history = save_scan(payload)
                return self._send_json({"ok": True, "record": record, "count": len(history)})
            except Exception as e:  # noqa: BLE001
                return self._send_json({"ok": False, "error": str(e)}, status=500)

        if self.path == "/api/insight":
            scans = load_scans()
            health = load_health_data()
            return self._send_json(generate_insight(scans, health))

        self.send_error(404, "not found")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8079)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    server = ThreadingHTTPServer((args.host, args.port), PCCHandler)
    sys.stderr.write(
        f"[PCC] serving on http://{args.host}:{args.port} pid={os.getpid()}\n"
    )
    sys.stderr.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
