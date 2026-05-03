#!/usr/bin/env python3
"""
QRF Watchdog — auto-dispatch QRF when any monitored surface is offline >30 min.

Mandate (Commander, 2026-05-01):
  "If something is offline more than 30 min, the QRF should fix."

Runs every 15 min via the orchestrator. For each registered surface:
  1. Check freshness / health
  2. If stale > threshold_min, dispatch QRF (subject to cooldown_min)
  3. Log every action to alert_history.json + qrf_watchdog_log.json
  4. iMessage the Commander on PRIORITY dispatches

Per CLAUDE.md SO #10 (Act and Report), every dispatch is reported, never silent.
Per CLAUDE.md SO #14, the watchdog itself documents WHY it dispatched (the
specific staleness or schema fault) so QRF can do RCA, not symptom-fixing.

Detected failure classes the orchestrator alone misses:
  - SILENT ROT: script exit 0 but produced bad content (e.g. parse_error: True)
  - STALE OUTPUT: cadence-based JSON not regenerated past expected interval
  - SCHEMA FAULT: required keys empty (e.g. stock_profiles == {})
  - DASHBOARD DOWN: HTTP probe fails on localhost:8077
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

# ── Paths ────────────────────────────────────────────────────────────────
HOME = Path.home()
SCRIPTS_DIR = HOME / "Documents" / "S6_COMMS_TECH" / "scripts"
DASHBOARD_DIR = HOME / "Documents" / "S6_COMMS_TECH" / "dashboard"
STATE_FILE = DASHBOARD_DIR / "qrf_watchdog_state.json"
LOG_FILE = DASHBOARD_DIR / "qrf_watchdog_log.json"
ALERT_HISTORY = DASHBOARD_DIR / "alert_history.json"
TASK_HEALTH = DASHBOARD_DIR / "task_health.json"

OFFLINE_THRESHOLD_MIN = 30        # Commander mandate
DEFAULT_COOLDOWN_MIN = 60         # Don't re-dispatch the same surface inside this window
DASHBOARD_URL = "http://localhost:8077/lifeos-dashboard.html"
LIFEOS_DATA_URL = "http://localhost:8077/lifeos_data.json"


# ── Surface definition ────────────────────────────────────────────────────

@dataclass
class Surface:
    """A monitored surface. check() returns (healthy, summary, age_min).

    playbook is a list of subprocess argv lists. Each is run in order; the first
    one whose exit==0 is treated as the repair. If all fail OR no playbook is
    defined, the watchdog escalates to the QRF agent via claude -p.
    """
    name: str
    check: Callable
    fix_hint: str
    threshold_min: int = OFFLINE_THRESHOLD_MIN
    cooldown_min: int = DEFAULT_COOLDOWN_MIN
    classification: str = "PRIORITY"  # PRIORITY → iMessage, ROUTINE → log only
    playbook: list[list[str]] = field(default_factory=list)
    playbook_timeout: int = 360


def _file_age_minutes(path: Path) -> float | None:
    if not path.exists():
        return None
    return (time.time() - path.stat().st_mtime) / 60.0


def _http_ok(url: str, timeout: float = 4.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return 200 <= r.status < 400
    except Exception:
        return False


def _read_json(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


# ── Check functions ──────────────────────────────────────────────────────

def check_json_freshness(path: Path, max_age_min: int):
    """Return checker that fails when JSON file is missing or older than max_age_min."""
    def _check():
        age = _file_age_minutes(path)
        if age is None:
            return False, f"{path.name} MISSING", None
        if age > max_age_min:
            return False, f"{path.name} stale {age:.0f} min (cap {max_age_min})", age
        return True, f"{path.name} fresh ({age:.0f} min)", age
    return _check


def check_dashboard_http():
    if not _http_ok(DASHBOARD_URL):
        return False, "dashboard HTTP probe failed (port 8077)", None
    return True, "dashboard 200 on :8077", 0


def check_unified_state_api():
    if not _http_ok(LIFEOS_DATA_URL):
        return False, "lifeos_data.json HTTP fetch failed", None
    return True, "lifeos_data.json reachable", 0


def check_invest_intel_quality():
    """Silent-rot detector: AI parse_error or empty stock_profiles past threshold."""
    data = _read_json(DASHBOARD_DIR / "invest_intel_data.json")
    if not data:
        return False, "invest_intel_data.json unreadable or missing", None
    age = _file_age_minutes(DASHBOARD_DIR / "invest_intel_data.json")
    ai = data.get("ai_analysis") or {}
    profiles = data.get("stock_profiles") or {}
    faults = []
    if ai.get("parse_error"):
        faults.append("ai_analysis.parse_error=True")
    if not profiles:
        faults.append("stock_profiles is empty")
    if not data.get("watchlist"):
        faults.append("watchlist is empty")
    # Only treat as failure if the data has had time to be regenerated post-fix.
    if faults and age is not None and age > OFFLINE_THRESHOLD_MIN:
        return False, "invest_intel content faults: " + ", ".join(faults), age
    if faults:
        return True, f"invest_intel faults present but file young ({age:.0f}m); waiting", age
    return True, f"invest_intel content healthy ({age:.0f}m)", age


def check_orchestrator_task(task_name: str):
    """Fail when an orchestrator task has been RED for longer than threshold."""
    def _check():
        d = _read_json(TASK_HEALTH) or {}
        th = (d.get("tasks") or {}).get(task_name)
        if not th:
            return False, f"task_health missing entry for {task_name}", None
        status = th.get("status")
        last_success = th.get("last_success")
        if status in ("GREEN", "DEFERRED"):
            return True, f"{task_name} {status}", 0
        if status == "RED":
            if not last_success:
                return False, f"{task_name} RED, no last_success ever", None
            try:
                ls = datetime.fromisoformat(last_success)
                age_min = (datetime.now() - ls).total_seconds() / 60.0
            except Exception:
                return False, f"{task_name} RED, last_success unparseable", None
            if age_min > OFFLINE_THRESHOLD_MIN:
                return False, f"{task_name} RED for {age_min:.0f} min", age_min
            return True, f"{task_name} RED but inside grace window", age_min
        return True, f"{task_name} status={status}", 0
    return _check


# ── Surface registry ─────────────────────────────────────────────────────

PYTHON = "/Library/Developer/CommandLineTools/usr/bin/python3"

SURFACES: list[Surface] = [
    Surface(
        name="dashboard_http",
        check=check_dashboard_http,
        fix_hint="Restart dashboard server: bash start_dashboard.sh",
        classification="PRIORITY",
        playbook=[["bash", str(DASHBOARD_DIR / "start_dashboard.sh")]],
    ),
    Surface(
        name="cop_data_fresh",
        check=check_json_freshness(DASHBOARD_DIR / "cop_data.json", 90),
        fix_hint="Run dashboard_updater.py to rebuild cop_data.json",
        threshold_min=90,
        classification="PRIORITY",
        playbook=[[PYTHON, str(SCRIPTS_DIR / "dashboard_updater.py")]],
    ),
    Surface(
        name="lifeos_data_fresh",
        check=check_json_freshness(DASHBOARD_DIR / "lifeos_data.json", 60),
        fix_hint="Run lifeos_data_sync.py to regenerate lifeos_data.json",
        threshold_min=60,
        classification="PRIORITY",
        # EE-Cycle13 2026-05-03: Prior playbook ran state_aggregator.py + state_synthesizer.py
        # which write unified_state.json and overwatch_input.json respectively — NOT lifeos_data.json.
        # Both scripts exited=0 but recheck always ESCALATED because the wrong file was written.
        # This generated 10+ PRIORITY ESCALATED alerts on 5/2. Correct writer: lifeos_data_sync.py.
        playbook=[
            [PYTHON, str(SCRIPTS_DIR / "lifeos_data_sync.py")],
        ],
    ),
    Surface(
        name="invest_intel_fresh",
        check=check_json_freshness(DASHBOARD_DIR / "invest_intel_data.json", 720),
        fix_hint="Run invest_intel_updater.py manually",
        threshold_min=720,
        classification="ROUTINE",
        playbook=[[PYTHON, str(SCRIPTS_DIR / "invest_intel_updater.py")]],
        playbook_timeout=600,
    ),
    Surface(
        name="invest_intel_quality",
        check=check_invest_intel_quality,
        fix_hint=(
            "AI/profiles silent-rot. Re-run invest_intel_updater.py; "
            "if it still fails, RCA run_ai_analysis or run_stock_profiles."
        ),
        classification="PRIORITY",
        playbook=[[PYTHON, str(SCRIPTS_DIR / "invest_intel_updater.py")]],
        playbook_timeout=600,
    ),
    Surface(
        name="prediction_data_fresh",
        check=check_json_freshness(DASHBOARD_DIR / "prediction_data.json", 720),
        fix_hint="Run predictive_engine/synthesis_engine.py via stock_analyst.py",
        threshold_min=720,
        classification="ROUTINE",
        playbook=[[PYTHON, str(SCRIPTS_DIR / "predictive_engine" / "stock_analyst.py")]],
        playbook_timeout=600,
    ),
    # task_* surfaces re-run the underlying script directly. We can't invoke
    # the orchestrator's --run from inside an orchestrator-driven watchdog
    # because the parent process already holds the orchestrator lock — a
    # nested --run would silently no-op. After a successful direct run, the
    # watchdog updates task_health for the affected task (mark_task_green).
    Surface(
        name="task_invest_intel",
        check=check_orchestrator_task("invest_intel"),
        fix_hint="invest_intel orchestrator task RED — re-run updater",
        classification="PRIORITY",
        playbook=[[PYTHON, str(SCRIPTS_DIR / "invest_intel_updater.py")]],
        playbook_timeout=600,
    ),
    Surface(
        name="task_stock_analyst",
        check=check_orchestrator_task("stock_analyst"),
        fix_hint="stock_analyst RED — likely None price on bad ticker (null-guarded 2026-05-01)",
        classification="PRIORITY",
        playbook=[[PYTHON, str(SCRIPTS_DIR / "predictive_engine" / "stock_analyst.py")]],
        playbook_timeout=600,
    ),
    Surface(
        name="task_cop_dashboard",
        check=check_orchestrator_task("cop_dashboard"),
        fix_hint="cop_dashboard generator failing — likely upstream JSON",
        classification="PRIORITY",
        playbook=[[PYTHON, str(SCRIPTS_DIR / "dashboard_updater.py")]],
    ),
]


# ── Discovered surfaces (data-driven extension) ──────────────────────────
# qrf_coverage_audit.py writes new surfaces here weekly. The watchdog reads
# them at startup so coverage grows without rewriting this file.
EXTRA_SURFACES_FILE = DASHBOARD_DIR / "qrf_extra_surfaces.json"

def _mcp_initialize_check(url: str, timeout: float = 4.0):
    """Probe a Streamable-HTTP MCP server with a proper JSON-RPC initialize.

    A bare GET/HEAD on an MCP endpoint returns 400/406 even when the server is
    healthy — the protocol requires a POST with `Accept: application/json,
    text/event-stream` and a valid initialize request. Plain http_get can't
    distinguish "MCP server alive but rejecting our header" from "process
    crashed." This check sends the real handshake."""
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "qrf-watchdog", "version": "1.0"},
        },
    }).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = r.read(2000).decode("utf-8", errors="replace")
            if r.status == 200 and '"protocolVersion"' in payload:
                return True, f"{url} MCP initialize ok", 0
            return False, f"{url} MCP {r.status} but no protocolVersion in response", None
    except Exception as e:
        return False, f"{url} MCP initialize failed: {e}", None


_KIND_TO_CHECK = {
    "json_freshness": lambda spec: check_json_freshness(
        Path(spec["path"]).expanduser(), int(spec.get("max_age_min", 60))
    ),
    "http_get": lambda spec: (lambda url=spec["url"]: (
        (True, f"{url} reachable", 0) if _http_ok(url)
        else (False, f"{url} unreachable", None)
    )),
    "orchestrator_task": lambda spec: check_orchestrator_task(spec["task_name"]),
    "mcp_initialize": lambda spec: (
        lambda url=spec["url"]: _mcp_initialize_check(url)
    ),
}


def _load_extra_surfaces() -> list[Surface]:
    """Build Surface objects from the JSON registry. Bad entries are skipped
    with a printed warning so a malformed audit can't take down the watchdog."""
    if not EXTRA_SURFACES_FILE.exists():
        return []
    try:
        data = json.loads(EXTRA_SURFACES_FILE.read_text())
    except Exception as e:
        print(f"[qrf_watchdog] WARN: extra surfaces file unreadable: {e}")
        return []
    out: list[Surface] = []
    for s in data.get("surfaces", []):
        try:
            kind = s.get("check_kind")
            builder = _KIND_TO_CHECK.get(kind)
            if not builder:
                print(f"[qrf_watchdog] WARN: unknown check_kind {kind!r} in extra surface {s.get('name')}")
                continue
            check = builder(s)
            playbook = [list(cmd) for cmd in (s.get("playbook") or [])]
            out.append(Surface(
                name=s["name"],
                check=check,
                fix_hint=s.get("fix_hint", ""),
                threshold_min=int(s.get("threshold_min", OFFLINE_THRESHOLD_MIN)),
                cooldown_min=int(s.get("cooldown_min", DEFAULT_COOLDOWN_MIN)),
                classification=s.get("classification", "PRIORITY"),
                playbook=playbook,
                playbook_timeout=int(s.get("playbook_timeout", 360)),
            ))
        except Exception as e:
            print(f"[qrf_watchdog] WARN: skipping malformed extra surface {s.get('name')!r}: {e}")
    return out


SURFACES.extend(_load_extra_surfaces())


# ── State + logging ──────────────────────────────────────────────────────

def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {"surfaces": {}}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {"surfaces": {}}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _append_log(entry: dict) -> None:
    if LOG_FILE.exists():
        try:
            log = json.loads(LOG_FILE.read_text())
        except Exception:
            log = {"events": []}
    else:
        log = {"events": []}
    log.setdefault("events", []).append(entry)
    log["events"] = log["events"][-500:]  # cap retention
    LOG_FILE.write_text(json.dumps(log, indent=2))


def _append_alert_history(entry: dict) -> None:
    if ALERT_HISTORY.exists():
        try:
            hist = json.loads(ALERT_HISTORY.read_text())
        except Exception:
            hist = {"alerts": []}
    else:
        hist = {"alerts": []}
    hist.setdefault("alerts", []).append(entry)
    hist["alerts"] = hist["alerts"][-500:]
    ALERT_HISTORY.write_text(json.dumps(hist, indent=2))


def _imessage(summary: str) -> None:
    """Send an iMessage via s6_alert.py (best-effort, don't crash watchdog).

    s6_alert.alert(severity, subject, body) — severity must be CRITICAL/HIGH/MEDIUM.
    """
    try:
        sys.path.insert(0, str(SCRIPTS_DIR))
        from s6_alert import alert, HIGH  # type: ignore
        alert(HIGH, "QRF Watchdog", summary)
    except Exception:
        try:
            subprocess.run(
                ["python3", str(SCRIPTS_DIR / "s6_alert.py"),
                 "HIGH", "QRF Watchdog", summary],
                check=False, timeout=10,
            )
        except Exception:
            pass


# ── Dispatch ─────────────────────────────────────────────────────────────

def _within_cooldown(surface_state: dict, cooldown_min: int) -> bool:
    last = surface_state.get("last_dispatch")
    if not last:
        return False
    try:
        t = datetime.fromisoformat(last)
    except Exception:
        return False
    return datetime.now() - t < timedelta(minutes=cooldown_min)


def _mark_task_green(task_name: str) -> bool:
    """Best-effort: update task_health.json to GREEN after a successful direct
    repair. Without this, a `task_*` surface stays RED in task_health (because
    the orchestrator's run_task wrapper didn't touch it) and the watchdog
    would re-dispatch the same fix on the next tick. Cooldown still applies."""
    try:
        d = _read_json(TASK_HEALTH) or {}
        tasks = d.setdefault("tasks", {})
        th = tasks.setdefault(task_name, {})
        th["status"] = "GREEN"
        th["last_success"] = datetime.now().isoformat(timespec="seconds")
        th["last_error"] = None
        th["consecutive_failures"] = 0
        th["last_repaired_by"] = "qrf_watchdog"
        TASK_HEALTH.write_text(json.dumps(d, indent=2))
        return True
    except Exception:
        return False


def _run_playbook(surface: Surface) -> tuple[bool, str]:
    """Execute the surface's playbook. Returns (fixed, transcript).

    Stops after the first command that exits 0 AND restores the surface
    health on re-check. We re-run the surface check after each command so a
    successful repair short-circuits the rest of the playbook."""
    if not surface.playbook:
        return False, "no playbook"
    transcript_lines = []
    for cmd in surface.playbook:
        try:
            r = subprocess.run(
                cmd,
                cwd=str(SCRIPTS_DIR),
                capture_output=True,
                text=True,
                timeout=surface.playbook_timeout,
            )
            tail = (r.stdout or "")[-300:] + (r.stderr or "")[-300:]
            transcript_lines.append(f"[exit={r.returncode}] {' '.join(cmd)} :: {tail}")
            if r.returncode == 0:
                # For task_* surfaces, the direct script run won't update
                # task_health.json — write it back so the recheck sees GREEN.
                if surface.name.startswith("task_"):
                    inner = surface.name[len("task_"):]
                    if _mark_task_green(inner):
                        transcript_lines.append(f"[task_health] marked {inner} GREEN")
                # Re-check the surface after a successful command.
                try:
                    ok, summary, _ = surface.check()
                except Exception as e:
                    ok, summary = False, f"recheck raised: {e}"
                transcript_lines.append(f"[recheck] ok={ok} :: {summary}")
                if ok:
                    return True, "\n".join(transcript_lines)
        except subprocess.TimeoutExpired:
            transcript_lines.append(f"[TIMEOUT after {surface.playbook_timeout}s] {' '.join(cmd)}")
        except Exception as e:
            transcript_lines.append(f"[EXC] {' '.join(cmd)}: {e}")
    return False, "\n".join(transcript_lines)


def dispatch_qrf(surface: Surface, summary: str) -> dict:
    """Try the deterministic playbook first. Only escalate to the QRF agent
    (queue for next agent-capable cycle) if the playbook can't restore health.

    Per Commander mandate (2026-05-01): "If something is offline >30 min, the
    QRF should fix." We attempt the fix immediately rather than just queueing —
    silent rot is the failure class this defends against."""
    now = datetime.now().isoformat(timespec="seconds")
    fixed, transcript = _run_playbook(surface)
    record = {
        "timestamp": now,
        "surface": surface.name,
        "classification": surface.classification,
        "reason": summary,
        "fix_hint": surface.fix_hint,
        "threshold_min": surface.threshold_min,
        "dispatched_by": "qrf_watchdog",
        "playbook_attempted": bool(surface.playbook),
        "playbook_transcript_tail": transcript[-1000:],
        "status": "FIXED" if fixed else ("ESCALATED" if surface.playbook else "QUEUED"),
    }
    _append_log(record)
    _append_alert_history({
        **record,
        "agent": "qrf-watchdog",
        "action": (
            f"playbook FIXED {surface.name}" if fixed
            else f"playbook FAILED, escalate {surface.name}" if surface.playbook
            else f"queue QRF for {surface.name}"
        ),
    })
    if surface.classification == "PRIORITY":
        prefix = "🟢 QRF FIXED" if fixed else "🟠 QRF ESCALATED"
        _imessage(f"{prefix} — {surface.name}: {summary[:140]}")
    return record


# ── Main ─────────────────────────────────────────────────────────────────

def run_once(verbose: bool = False) -> dict:
    state = _load_state()
    surfaces_state = state.setdefault("surfaces", {})
    state["last_run"] = datetime.now().isoformat(timespec="seconds")

    healthy = []
    failed = []
    queued = []
    skipped_cooldown = []

    for s in SURFACES:
        check_age = None
        try:
            ok, summary, check_age = s.check()
        except Exception as e:
            ok, summary = False, f"check raised: {e}"

        ss = surfaces_state.setdefault(s.name, {})
        ss["last_check"] = state["last_run"]
        ss["last_summary"] = summary
        ss["last_ok"] = ok

        if ok:
            healthy.append(s.name)
            ss.pop("offline_since", None)
            continue

        # Offline duration: prefer the age the check itself computed (e.g. file
        # mtime age, task_health.last_success age — the *real* outage). Fall
        # back to first-observation time only when the check can't compute it.
        if "offline_since" not in ss:
            ss["offline_since"] = state["last_run"]
        if isinstance(check_age, (int, float)) and check_age >= 0:
            offline_min = float(check_age)
        else:
            try:
                offline_since = datetime.fromisoformat(ss["offline_since"])
                offline_min = (datetime.now() - offline_since).total_seconds() / 60.0
            except Exception:
                offline_min = 0.0

        failed.append({"name": s.name, "summary": summary, "offline_min": offline_min})

        if offline_min < s.threshold_min:
            continue
        if _within_cooldown(ss, s.cooldown_min):
            skipped_cooldown.append(s.name)
            continue

        # Dispatch
        result = dispatch_qrf(s, summary + f" (offline {offline_min:.0f} min)")
        ss["last_dispatch"] = state["last_run"]
        ss["last_dispatch_status"] = result.get("status")
        queued.append(s.name)

    _save_state(state)

    summary_obj = {
        "ts": state["last_run"],
        "healthy": healthy,
        "failed": failed,
        "queued": queued,
        "skipped_cooldown": skipped_cooldown,
    }

    if verbose:
        print(json.dumps(summary_obj, indent=2))
    else:
        print(
            f"QRF Watchdog: {len(healthy)} healthy, {len(failed)} failed, "
            f"{len(queued)} dispatched, {len(skipped_cooldown)} cooldown"
        )
        for f in failed:
            print(f"  FAIL  {f['name']}: {f['summary']} (off {f['offline_min']:.0f}m)")
        for q in queued:
            print(f"  QRF   queued for {q}")

    return summary_obj


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    if "--list" in sys.argv:
        for s in SURFACES:
            print(f"{s.name:30} thr={s.threshold_min}m cd={s.cooldown_min}m {s.classification}")
        return
    run_once(verbose=verbose)


if __name__ == "__main__":
    main()
