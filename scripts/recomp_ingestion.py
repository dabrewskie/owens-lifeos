#!/usr/bin/env python3
"""
recomp_ingestion.py — Body Recomposition Data Engine

Ingests health export data, progress photos, and lab results to produce
recomp_data.json for the body recomp dashboard.

Runs daily at 0632 as part of the data-pipeline scheduled task.
Handles missing data gracefully — Health Auto Export may only have data
from ~Feb 2026 onward; earlier weeks will have null values.

Sources:
  - Health Auto Export JSONs (weight, body fat, BMI)
  - Progress photos with EXIF dates
  - Lab results (seed + manual overrides + PDF parsing)

Output: ~/Documents/S6_COMMS_TECH/dashboard/recomp_data.json
"""

import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
except ImportError:
    Image = None

# ── Configuration ──────────────────────────────────────────────────────────

HOME = Path.home()
HEALTH_EXPORT_PATH = HOME / "Library" / "Mobile Documents" / "iCloud~com~ifunography~HealthExport" / "Documents" / "Health Metrics"
PHOTO_PATH = HOME / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "MEDICAL_HEALTH_PERFORMANCE" / "Body_Recomp_Photos"
LAB_PATH = HOME / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "MEDICAL_HEALTH_PERFORMANCE" / "Lab_Results"
OUTPUT_PATH = HOME / "Documents" / "S6_COMMS_TECH" / "dashboard" / "recomp_data.json"
PHOTO_SERVE_PATH = HOME / "Documents" / "S6_COMMS_TECH" / "dashboard" / "recomp_photos"
MANUAL_LABS_PATH = HOME / "Documents" / "S6_COMMS_TECH" / "scripts" / "recomp_labs_manual.json"

TRT_START = datetime(2025, 9, 11)
TOTAL_WEEKS_TARGET = 80

PHASES = [
    {"name": "TRT Only", "start": "2025-09-11", "end": "2025-12-01", "color": "#2979ff"},
    {"name": "TRT + AI", "start": "2025-12-01", "end": "2026-03-13", "color": "#4caf50"},
    {"name": "TRT + AI + Peptides", "start": "2026-03-13", "end": None, "color": "#d4a55a"},
]

SEED_LABS = [
    {"date": "2025-08-01", "phase": "Pre-TRT", "source": "VA", "testosterone": 242, "estradiol": None, "hematocrit": None, "hemoglobin": None, "psa": None, "hba1c": 5.5, "ldl": 152, "hdl": 50.6, "triglycerides": 103, "ast": None, "alt": None, "igf1": None},
    {"date": "2025-10-01", "phase": "TRT Only", "source": "Posterity/Quest", "testosterone": 234, "estradiol": None, "hematocrit": 52.1, "hemoglobin": 17.2, "psa": None, "hba1c": None, "ldl": None, "hdl": None, "triglycerides": None, "ast": None, "alt": None, "igf1": None},
    {"date": "2025-12-01", "phase": "TRT + AI", "source": "Posterity/Quest", "testosterone": 767, "estradiol": 68, "hematocrit": 51.8, "hemoglobin": 16.8, "psa": 0.64, "hba1c": None, "ldl": None, "hdl": None, "triglycerides": None, "ast": None, "alt": None, "igf1": None},
    {"date": "2026-03-01", "phase": "TRT + AI", "source": "Posterity/Quest", "testosterone": 799, "estradiol": 50, "hematocrit": 53.4, "hemoglobin": 17.5, "psa": 1.12, "hba1c": 5.7, "ldl": 144, "hdl": 39, "triglycerides": 101, "ast": 23, "alt": 23, "igf1": None},
]

# Body comp metric names as they appear in Health Auto Export
BODY_COMP_METRICS = {
    "weight_body_mass": "weight",
    "body_fat_percentage": "body_fat",
    "body_mass_index": "bmi",
}

# Lab marker regex patterns for Quest PDF parsing
LAB_PATTERNS = {
    "testosterone": r"testosterone[,\s]*total[:\s]+(\d+\.?\d*)",
    "estradiol": r"estradiol[:\s]+(\d+\.?\d*)",
    "hematocrit": r"hematocrit[:\s]+(\d+\.?\d*)",
    "hemoglobin": r"hemoglobin[:\s]+(\d+\.?\d*)",
    "psa": r"psa[,\s]*total[:\s]+(\d+\.?\d*)",
    "hba1c": r"(?:hba1c|hemoglobin a1c|a1c)[:\s]+(\d+\.?\d*)",
    "ldl": r"ldl[- ]?(?:cholesterol)?[:\s]+(\d+\.?\d*)",
    "hdl": r"hdl[- ]?(?:cholesterol)?[:\s]+(\d+\.?\d*)",
    "triglycerides": r"triglycerides?[:\s]+(\d+\.?\d*)",
    "ast": r"ast[:\s]+(\d+\.?\d*)",
    "alt": r"alt[:\s]+(\d+\.?\d*)",
    "igf1": r"igf[- ]?1[:\s]+(\d+\.?\d*)",
}


# ── Utility Functions ──────────────────────────────────────────────────────

def get_phase(date_str):
    """Returns protocol phase name for a date string (YYYY-MM-DD)."""
    d = datetime.strptime(date_str[:10], "%Y-%m-%d")
    if d < TRT_START:
        return "Pre-TRT"
    for phase in reversed(PHASES):
        phase_start = datetime.strptime(phase["start"], "%Y-%m-%d")
        if d >= phase_start:
            return phase["name"]
    return "Pre-TRT"


def week_number(date_str):
    """Returns week number since TRT_START (week 1 = first week)."""
    d = datetime.strptime(date_str[:10], "%Y-%m-%d")
    delta = (d - TRT_START).days
    if delta < 0:
        return 0
    return (delta // 7) + 1


def week_start_date(week_num):
    """Returns the Monday-anchored start date for a given week number."""
    return TRT_START + timedelta(weeks=week_num - 1)


def nearest_wednesday(dt):
    """Returns the nearest Wednesday to a datetime."""
    # Wednesday = 2
    days_off = (dt.weekday() - 2) % 7
    if days_off > 3:
        days_off -= 7
    return dt - timedelta(days=days_off)


# ── Data Ingestion ─────────────────────────────────────────────────────────

def ingest_health_data():
    """
    Scans Health Auto Export JSONs, extracts body comp metrics,
    groups by week, computes weekly averages and lean mass.

    Returns dict keyed by week number with averaged body comp values.
    """
    weekly = defaultdict(lambda: defaultdict(list))

    if not HEALTH_EXPORT_PATH.is_dir():
        print(f"  WARNING: Health export path not found: {HEALTH_EXPORT_PATH}")
        return {}

    json_files = sorted(HEALTH_EXPORT_PATH.glob("HealthAutoExport-*.json"))
    if not json_files:
        print("  WARNING: No Health Auto Export JSON files found")
        return {}

    files_with_data = 0
    for fpath in json_files:
        # Extract date from filename
        fname = fpath.stem  # HealthAutoExport-YYYY-MM-DD
        date_part = fname.replace("HealthAutoExport-", "")
        # Validate date format
        if len(date_part) != 10:
            continue
        try:
            datetime.strptime(date_part, "%Y-%m-%d")
        except ValueError:
            continue

        wk = week_number(date_part)
        if wk < 1:
            continue  # Pre-TRT data, skip

        # Parse the JSON
        try:
            with open(fpath) as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"  WARNING: Failed to read {fpath.name}: {e}", file=sys.stderr)
            continue

        raw_metrics = []
        if isinstance(data, dict):
            if "data" in data and "metrics" in data["data"]:
                raw_metrics = data["data"]["metrics"]
            elif "metrics" in data:
                raw_metrics = data["metrics"]

        day_has_data = False
        for m in raw_metrics:
            metric_name = m.get("name", "")
            if metric_name in BODY_COMP_METRICS:
                key = BODY_COMP_METRICS[metric_name]
                for entry in m.get("data", []):
                    qty = entry.get("qty")
                    if qty is not None:
                        try:
                            val = float(qty)
                            if val > 0:
                                weekly[wk][key].append(val)
                                day_has_data = True
                        except (TypeError, ValueError):
                            pass

        if day_has_data:
            files_with_data += 1

    print(f"  Health export: {len(json_files)} files scanned, {files_with_data} with body comp data")

    # Compute weekly averages
    result = {}
    for wk, metrics in sorted(weekly.items()):
        entry = {
            "week": wk,
            "week_start": week_start_date(wk).strftime("%Y-%m-%d"),
            "phase": get_phase(week_start_date(wk).strftime("%Y-%m-%d")),
            "weight": None,
            "body_fat": None,
            "bmi": None,
            "lean_mass": None,
        }

        if "weight" in metrics and metrics["weight"]:
            entry["weight"] = round(sum(metrics["weight"]) / len(metrics["weight"]), 1)
        if "body_fat" in metrics and metrics["body_fat"]:
            entry["body_fat"] = round(sum(metrics["body_fat"]) / len(metrics["body_fat"]), 1)
        if "bmi" in metrics and metrics["bmi"]:
            entry["bmi"] = round(sum(metrics["bmi"]) / len(metrics["bmi"]), 1)

        # Compute lean mass if we have both weight and body fat
        if entry["weight"] is not None and entry["body_fat"] is not None:
            fat_mass = entry["weight"] * (entry["body_fat"] / 100.0)
            entry["lean_mass"] = round(entry["weight"] - fat_mass, 1)

        result[wk] = entry

    return result


def ingest_photos():
    """
    Scans photo directory for progress images, reads EXIF dates,
    assigns to nearest Wednesday/week, copies to serve directory.

    Returns list of photo entries with week assignments.
    """
    photos = []

    if not PHOTO_PATH.is_dir():
        print(f"  Photos: directory not found ({PHOTO_PATH}), creating...")
        PHOTO_PATH.mkdir(parents=True, exist_ok=True)
        return photos

    # Ensure serve directory exists
    PHOTO_SERVE_PATH.mkdir(parents=True, exist_ok=True)

    # Trust the album — everything in Body_Recomp_Photos/ was put there deliberately
    image_extensions = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
    image_files = [f for f in PHOTO_PATH.iterdir() if f.suffix.lower() in image_extensions and not f.name.startswith(".")]

    if not image_files:
        print("  Photos: no images found")
        return photos

    # Photo sync script handles HEIC→JPEG conversion to PHOTO_SERVE_PATH.
    # We read from PHOTO_SERVE_PATH for serve paths (browser-compatible JPEGs).
    for img_path in sorted(image_files):
        dt = None

        # Try parsing date from standardized filename (YYYY-MM-DD_photo_N.ext)
        name_match = re.match(r"(\d{4}-\d{2}-\d{2})_photo_", img_path.name)
        if name_match:
            try:
                dt = datetime.strptime(name_match.group(1), "%Y-%m-%d")
            except ValueError:
                pass

        # Try EXIF DateTimeOriginal
        if dt is None and Image is not None and img_path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            try:
                with Image.open(img_path) as img:
                    exif_data = img._getexif()
                    if exif_data and 36867 in exif_data:
                        dt = datetime.strptime(exif_data[36867], "%Y:%m:%d %H:%M:%S")
            except Exception:
                pass

        # Fallback to file mtime
        if dt is None:
            dt = datetime.fromtimestamp(img_path.stat().st_mtime)

        wk = week_number(dt.strftime("%Y-%m-%d"))
        if wk < 1:
            continue  # Skip pre-TRT photos entirely

        # Serve path uses .jpg (HEIC/PNG converted by photo_sync)
        serve_name = img_path.stem + ".jpg" if img_path.suffix.lower() in {".heic", ".heif", ".png"} else img_path.name

        photos.append({
            "filename": img_path.name,
            "date": dt.strftime("%Y-%m-%d"),
            "week": wk,
            "phase": get_phase(dt.strftime("%Y-%m-%d")),
            "serve_path": "recomp_photos/" + serve_name,
        })

    print(f"  Photos: {len(photos)} images indexed")
    return photos


def parse_lab_pdf(pdf_path):
    """
    Parses a Quest-format lab PDF using pdfplumber + regex.
    Returns a dict of lab markers found, or None if parsing fails.
    """
    if pdfplumber is None:
        return None

    try:
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

        if not text.strip():
            return None

        text_lower = text.lower()
        results = {}

        for marker, pattern in LAB_PATTERNS.items():
            match = re.search(pattern, text_lower)
            if match:
                try:
                    results[marker] = float(match.group(1))
                except ValueError:
                    pass

        # Try to extract date from PDF
        date_match = re.search(r"(?:collected|date)[:\s]*(\d{1,2}/\d{1,2}/\d{4})", text_lower)
        if date_match:
            try:
                results["date"] = datetime.strptime(date_match.group(1), "%m/%d/%Y").strftime("%Y-%m-%d")
            except ValueError:
                pass

        return results if results else None

    except Exception as e:
        print(f"  WARNING: Failed to parse {pdf_path.name}: {e}", file=sys.stderr)
        return None


def ingest_labs():
    """
    Merges seed labs + manual overrides + PDF-parsed labs.
    Returns sorted list of lab entries.
    """
    # Start with seed data
    labs = [dict(entry) for entry in SEED_LABS]
    seed_dates = {entry["date"] for entry in labs}
    print(f"  Labs: {len(SEED_LABS)} seed entries loaded")

    # Check for manual overrides
    if MANUAL_LABS_PATH.is_file():
        try:
            with open(MANUAL_LABS_PATH) as f:
                manual = json.load(f)
            if isinstance(manual, list):
                for entry in manual:
                    date = entry.get("date")
                    if date:
                        # Override existing or add new
                        existing = next((l for l in labs if l["date"] == date), None)
                        if existing:
                            existing.update(entry)
                        else:
                            labs.append(entry)
                print(f"  Labs: {len(manual)} manual override(s) applied")
        except (json.JSONDecodeError, IOError) as e:
            print(f"  WARNING: Failed to read manual labs: {e}", file=sys.stderr)
    else:
        print(f"  Labs: no manual overrides file ({MANUAL_LABS_PATH.name})")

    # Scan for new PDFs
    if LAB_PATH.is_dir():
        pdf_files = sorted(LAB_PATH.glob("*.pdf"))
        parsed_count = 0
        for pdf_path in pdf_files:
            parsed = parse_lab_pdf(pdf_path)
            if parsed and "date" in parsed:
                if parsed["date"] not in seed_dates:
                    lab_entry = {
                        "date": parsed["date"],
                        "phase": get_phase(parsed["date"]),
                        "source": f"PDF:{pdf_path.name}",
                    }
                    for marker in LAB_PATTERNS:
                        lab_entry[marker] = parsed.get(marker)
                    labs.append(lab_entry)
                    parsed_count += 1
        if pdf_files:
            print(f"  Labs: {len(pdf_files)} PDFs scanned, {parsed_count} new entries parsed")
    else:
        print(f"  Labs: lab directory not found ({LAB_PATH})")

    # Sort by date
    labs.sort(key=lambda x: x.get("date", ""))

    # Ensure all entries have phase
    for entry in labs:
        if "phase" not in entry or not entry["phase"]:
            entry["phase"] = get_phase(entry["date"])

    return labs


# ── KPI Computation ────────────────────────────────────────────────────────

def compute_kpis(weekly_data, labs_data):
    """
    Computes first vs latest values for all KPIs.
    Returns dict with current values, deltas, and trajectories.
    """
    kpis = {
        "current_week": 0,
        "total_weeks_target": TOTAL_WEEKS_TARGET,
        "weeks_remaining": TOTAL_WEEKS_TARGET,
        "trt_start": TRT_START.strftime("%Y-%m-%d"),
        "current_phase": get_phase(datetime.now().strftime("%Y-%m-%d")),
        "body_comp": {},
        "labs": {},
    }

    # Current week
    now = datetime.now()
    current_wk = week_number(now.strftime("%Y-%m-%d"))
    kpis["current_week"] = current_wk
    kpis["weeks_remaining"] = max(0, TOTAL_WEEKS_TARGET - current_wk)
    kpis["progress_pct"] = round((current_wk / TOTAL_WEEKS_TARGET) * 100, 1)

    # Body comp KPIs — find first and latest weeks with data
    weeks_with_weight = sorted([wk for wk, d in weekly_data.items() if d.get("weight") is not None])

    if weeks_with_weight:
        first_wk = weeks_with_weight[0]
        latest_wk = weeks_with_weight[-1]
        first = weekly_data[first_wk]
        latest = weekly_data[latest_wk]

        kpis["body_comp"] = {
            "first_week": first_wk,
            "latest_week": latest_wk,
            "weight": {
                "first": first.get("weight"),
                "latest": latest.get("weight"),
                "delta": round(latest["weight"] - first["weight"], 1) if first.get("weight") and latest.get("weight") else None,
            },
            "body_fat": {
                "first": first.get("body_fat"),
                "latest": latest.get("body_fat"),
                "delta": round(latest["body_fat"] - first["body_fat"], 1) if first.get("body_fat") and latest.get("body_fat") else None,
            },
            "lean_mass": {
                "first": first.get("lean_mass"),
                "latest": latest.get("lean_mass"),
                "delta": round(latest["lean_mass"] - first["lean_mass"], 1) if first.get("lean_mass") and latest.get("lean_mass") else None,
            },
        }
    else:
        kpis["body_comp"] = {
            "first_week": None,
            "latest_week": None,
            "weight": {"first": None, "latest": None, "delta": None},
            "body_fat": {"first": None, "latest": None, "delta": None},
            "lean_mass": {"first": None, "latest": None, "delta": None},
        }

    # Lab KPIs — first vs latest for key markers
    lab_markers = ["testosterone", "estradiol", "hematocrit", "hemoglobin", "psa", "hba1c", "ldl", "hdl", "triglycerides", "ast", "alt", "igf1"]
    lab_kpis = {}
    for marker in lab_markers:
        entries_with_marker = [l for l in labs_data if l.get(marker) is not None]
        if entries_with_marker:
            first_lab = entries_with_marker[0]
            latest_lab = entries_with_marker[-1]
            lab_kpis[marker] = {
                "first": first_lab[marker],
                "first_date": first_lab["date"],
                "latest": latest_lab[marker],
                "latest_date": latest_lab["date"],
                "delta": round(latest_lab[marker] - first_lab[marker], 2) if first_lab[marker] is not None and latest_lab[marker] is not None else None,
            }
        else:
            lab_kpis[marker] = {"first": None, "latest": None, "delta": None}

    kpis["labs"] = lab_kpis
    return kpis


def compute_phase_deltas(weekly_data, phases):
    """
    Computes per-phase body comp changes (start vs end of each phase).
    Returns list of phase delta entries.
    """
    phase_deltas = []

    for phase in phases:
        phase_name = phase["name"]
        phase_start = datetime.strptime(phase["start"], "%Y-%m-%d")
        phase_end = datetime.strptime(phase["end"], "%Y-%m-%d") if phase["end"] else datetime.now()

        start_wk = week_number(phase_start.strftime("%Y-%m-%d"))
        end_wk = week_number(phase_end.strftime("%Y-%m-%d"))

        # Find weeks in this phase with data
        phase_weeks = sorted([
            wk for wk, d in weekly_data.items()
            if start_wk <= wk <= end_wk and d.get("weight") is not None
        ])

        delta_entry = {
            "phase": phase_name,
            "start_date": phase["start"],
            "end_date": phase["end"] or "ongoing",
            "color": phase["color"],
            "weeks": len(phase_weeks),
            "weight_delta": None,
            "body_fat_delta": None,
            "lean_mass_delta": None,
        }

        if len(phase_weeks) >= 2:
            first = weekly_data[phase_weeks[0]]
            last = weekly_data[phase_weeks[-1]]

            if first.get("weight") is not None and last.get("weight") is not None:
                delta_entry["weight_delta"] = round(last["weight"] - first["weight"], 1)
            if first.get("body_fat") is not None and last.get("body_fat") is not None:
                delta_entry["body_fat_delta"] = round(last["body_fat"] - first["body_fat"], 1)
            if first.get("lean_mass") is not None and last.get("lean_mass") is not None:
                delta_entry["lean_mass_delta"] = round(last["lean_mass"] - first["lean_mass"], 1)

        phase_deltas.append(delta_entry)

    return phase_deltas


# ── Main Orchestration ─────────────────────────────────────────────────────

def main():
    """Orchestrates all ingestion, writes JSON, prints summary."""
    print("=" * 60)
    print("BODY RECOMP INGESTION ENGINE")
    print(f"Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    now = datetime.now()
    current_wk = week_number(now.strftime("%Y-%m-%d"))
    current_phase = get_phase(now.strftime("%Y-%m-%d"))
    print(f"\n  Week {current_wk} of {TOTAL_WEEKS_TARGET} | Phase: {current_phase}")
    print(f"  TRT Start: {TRT_START.strftime('%Y-%m-%d')} | Target end: {(TRT_START + timedelta(weeks=TOTAL_WEEKS_TARGET)).strftime('%Y-%m-%d')}")
    print()

    # ── Ingest Health Data ──
    print("── Health Data ──")
    weekly_data = ingest_health_data()
    print(f"  Result: {len(weekly_data)} weeks with body comp data")
    print()

    # ── Sync Photos from Apple Photos album ──
    try:
        import importlib.util
        sync_path = Path(__file__).parent / "recomp_photo_sync.py"
        if sync_path.exists():
            spec = importlib.util.spec_from_file_location("recomp_photo_sync", sync_path)
            sync_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(sync_mod)
            sync_mod.main()
            print()
    except Exception as e:
        print(f"  WARNING: Photo sync failed: {e}")
        print()

    # ── Ingest Photos ──
    print("── Progress Photos ──")
    photos = ingest_photos()
    print()

    # ── Ingest Labs ──
    print("── Lab Results ──")
    labs = ingest_labs()
    print(f"  Result: {len(labs)} total lab entries")
    print()

    # ── Compute KPIs ──
    print("── Computing KPIs ──")
    kpis = compute_kpis(weekly_data, labs)
    print(f"  Current week: {kpis['current_week']} | Progress: {kpis.get('progress_pct', 0)}%")

    bc = kpis.get("body_comp", {})
    w = bc.get("weight", {})
    bf = bc.get("body_fat", {})
    lm = bc.get("lean_mass", {})
    if w.get("latest"):
        print(f"  Weight: {w['latest']} lb (delta: {w.get('delta', 'N/A')})")
    if bf.get("latest"):
        print(f"  Body fat: {bf['latest']}% (delta: {bf.get('delta', 'N/A')})")
    if lm.get("latest"):
        print(f"  Lean mass: {lm['latest']} lb (delta: {lm.get('delta', 'N/A')})")

    lab_kpis = kpis.get("labs", {})
    t = lab_kpis.get("testosterone", {})
    if t.get("latest"):
        print(f"  Testosterone: {t['first']} -> {t['latest']} ng/dL (delta: {t.get('delta')})")
    print()

    # ── Compute Phase Deltas ──
    print("── Phase Analysis ──")
    phase_deltas = compute_phase_deltas(weekly_data, PHASES)
    for pd_entry in phase_deltas:
        wk_count = pd_entry["weeks"]
        wd = pd_entry["weight_delta"]
        print(f"  {pd_entry['phase']}: {wk_count} weeks with data, weight delta: {wd if wd is not None else 'N/A'} lb")
    print()

    # ── Build Weekly Timeline ──
    # Create entries for all weeks, filling in nulls where no data exists
    weekly_timeline = []
    for wk in range(1, current_wk + 1):
        if wk in weekly_data:
            entry = dict(weekly_data[wk])
        else:
            ws = week_start_date(wk)
            entry = {
                "week": wk,
                "week_start": ws.strftime("%Y-%m-%d"),
                "phase": get_phase(ws.strftime("%Y-%m-%d")),
                "weight": None,
                "body_fat": None,
                "bmi": None,
                "lean_mass": None,
            }

        # Attach photos for this week
        entry["photos"] = [p for p in photos if p["week"] == wk]
        weekly_timeline.append(entry)

    # ── Build spec-compliant KPIs ──
    bc = kpis.get("body_comp", {})
    lab_k = kpis.get("labs", {})
    spec_kpis = {
        "weight": {"current": bc.get("weight", {}).get("latest"), "start": bc.get("weight", {}).get("first"), "delta": bc.get("weight", {}).get("delta"), "unit": "lbs"},
        "body_fat": {"current": bc.get("body_fat", {}).get("latest"), "start": bc.get("body_fat", {}).get("first"), "delta": bc.get("body_fat", {}).get("delta"), "unit": "%"},
        "lean_mass": {"current": bc.get("lean_mass", {}).get("latest"), "start": bc.get("lean_mass", {}).get("first"), "delta": bc.get("lean_mass", {}).get("delta"), "unit": "lbs"},
        "bmi": {"current": bc.get("weight", {}).get("latest"), "start": bc.get("weight", {}).get("first"), "delta": None, "unit": ""},
        "testosterone": {"current": lab_k.get("testosterone", {}).get("latest"), "start": lab_k.get("testosterone", {}).get("first"), "delta": lab_k.get("testosterone", {}).get("delta"), "unit": "ng/dL"},
    }
    # Fix BMI from actual BMI data if available
    weeks_with_bmi = sorted([wk for wk, d in weekly_data.items() if d.get("bmi") is not None])
    if weeks_with_bmi:
        spec_kpis["bmi"]["current"] = weekly_data[weeks_with_bmi[-1]]["bmi"]
        spec_kpis["bmi"]["start"] = weekly_data[weeks_with_bmi[0]]["bmi"]
        spec_kpis["bmi"]["delta"] = round(spec_kpis["bmi"]["current"] - spec_kpis["bmi"]["start"], 1) if spec_kpis["bmi"]["current"] and spec_kpis["bmi"]["start"] else None

    # ── Build spec-compliant weekly array ──
    spec_weekly = []
    for entry in weekly_timeline:
        spec_weekly.append({
            "week": entry["week"],
            "date": entry["week_start"],
            "weight": entry.get("weight"),
            "bf_pct": entry.get("body_fat"),
            "lean_mass": entry.get("lean_mass"),
            "bmi": entry.get("bmi"),
            "phase": entry.get("phase"),
        })

    # ── Build spec-compliant photos array ──
    spec_photos = []
    photos_by_week = {}
    for p in photos:
        wk = p["week"]
        if wk not in photos_by_week:
            photos_by_week[wk] = {"week": wk, "date": p["date"], "files": []}
        photos_by_week[wk]["files"].append(p["serve_path"])
    spec_photos = sorted(photos_by_week.values(), key=lambda x: x["week"])

    # ── Build spec-compliant phases with deltas ──
    spec_phases = []
    for phase, pd_entry in zip(PHASES, phase_deltas):
        spec_phases.append({
            "name": phase["name"],
            "start": phase["start"],
            "end": phase["end"],
            "color": phase["color"],
            "deltas": {
                "weight": pd_entry.get("weight_delta"),
                "bf_pct": pd_entry.get("body_fat_delta"),
                "lean_mass": pd_entry.get("lean_mass_delta"),
            }
        })

    # ── Assemble Output (spec-compliant schema) ──
    output = {
        "meta": {
            "start_date": TRT_START.strftime("%Y-%m-%d"),
            "current_week": current_wk,
            "total_weeks_target": TOTAL_WEEKS_TARGET,
            "last_updated": now.strftime("%Y-%m-%dT%H:%M:%S"),
            "phases": [{"name": p["name"], "start": p["start"], "end": p["end"], "color": p["color"]} for p in PHASES],
        },
        "kpis": spec_kpis,
        "weekly": spec_weekly,
        "photos": spec_photos,
        "labs": labs,
        "phases": spec_phases,
        # Keep extended data for skill/agent consumption
        "_extended": {
            "current_phase": current_phase,
            "progress_pct": kpis.get("progress_pct", 0),
            "lab_kpis": lab_k,
            "phase_deltas_raw": phase_deltas,
        },
    }

    # ── Write Output ──
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2, default=str)

    file_size = OUTPUT_PATH.stat().st_size
    print(f"── Output Written ──")
    print(f"  Path: {OUTPUT_PATH}")
    print(f"  Size: {file_size:,} bytes")
    print(f"  Timeline: {len(weekly_timeline)} weeks")
    print(f"  Labs: {len(labs)} entries")
    print(f"  Photos: {len(photos)} images")
    print()
    print("INGESTION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
