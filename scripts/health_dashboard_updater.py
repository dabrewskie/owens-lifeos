#!/usr/bin/env python3
"""
HEALTH DASHBOARD UPDATER — Owens Life OS
=========================================
Reads health data from multiple sources and updates health_data.json
for the Health Intelligence Dashboard.

Sources:
  1. Health Auto Export (daily JSON from iPhone)
  2. Function Health (cached biomarker data)
  3. Manual entries in health_data.json (preserved)

Usage:
  python3 health_dashboard_updater.py              # Full update
  python3 health_dashboard_updater.py --vitals      # Vitals only
  python3 health_dashboard_updater.py --dry-run     # Preview changes
  python3 health_dashboard_updater.py --verbose      # Detailed output
"""

import json
import os
import sys
import glob
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from copy import deepcopy

# ── Paths ──────────────────────────────────────────────────────────────
HEALTH_EXPORT_DIR = os.path.expanduser(
    "~/Library/Mobile Documents/iCloud~com~ifunography~HealthExport/Documents/Health Metrics/"
)
FUNCTION_HEALTH_CACHE = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/Health/function_health_cache.json"
)
DASHBOARD_DATA = os.path.expanduser(
    "~/Documents/S6_COMMS_TECH/dashboard/health/health_data.json"
)

# ── Metric name mappings (Health Auto Export → dashboard keys) ──────
# Metrics where we take the LAST data point (single daily value)
METRIC_MAP_LAST = {
    "weight_body_mass":       "weight",
    "body_fat_percentage":    "body_fat",
    "resting_heart_rate":     "resting_heart_rate",
}

# Metrics where we SUM all data points (accumulated throughout the day)
METRIC_MAP_SUM = {
    "step_count":             "steps_avg",
}

# Metrics where we AVERAGE all data points (multiple readings per day)
METRIC_MAP_AVG = {
    "heart_rate_variability": "hrv",
    "blood_oxygen_saturation": "spo2",
}

SLEEP_METRIC = "sleep_analysis"


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")


def load_json(path):
    """Load a JSON file, return None if missing or invalid."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        log(f"Cannot load {path}: {e}", "WARN")
        return None


def save_json(path, data):
    """Atomically write JSON data."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)
    log(f"Wrote {path}")


def find_latest_export_files(days=7):
    """Find the most recent Health Auto Export JSON files.

    Only returns files with YYYY-MM-DD date format in the filename,
    filtering out non-daily files (e.g. monthly aggregates).
    """
    if not os.path.isdir(HEALTH_EXPORT_DIR):
        log(f"Health export directory not found: {HEALTH_EXPORT_DIR}", "WARN")
        return []

    pattern = os.path.join(HEALTH_EXPORT_DIR, "HealthAutoExport-*.json")
    all_files = sorted(glob.glob(pattern), reverse=True)

    if not all_files:
        log("No Health Auto Export files found", "WARN")
        return []

    # Only include files with valid YYYY-MM-DD date format
    daily_files = []
    for f in all_files:
        basename = os.path.basename(f)
        date_part = basename.replace("HealthAutoExport-", "").replace(".json", "")
        if len(date_part) == 10:  # YYYY-MM-DD is exactly 10 chars
            daily_files.append(f)

    # Return up to `days` most recent daily files
    return daily_files[:days]


def extract_metric_last(metrics_list, metric_name):
    """Extract the last data point value for a metric (e.g. weight, RHR)."""
    for metric in metrics_list:
        if metric.get("name") == metric_name:
            data_points = metric.get("data", [])
            if data_points:
                latest = data_points[-1]
                return latest.get("qty", latest.get("value"))
    return None


def extract_metric_sum(metrics_list, metric_name):
    """Sum all data point values for a metric (e.g. step_count).

    Step count has many per-minute entries that must be summed for a daily total.
    """
    for metric in metrics_list:
        if metric.get("name") == metric_name:
            data_points = metric.get("data", [])
            if data_points:
                total = sum(p.get("qty", 0) for p in data_points)
                return total if total > 0 else None
    return None


def extract_metric_avg(metrics_list, metric_name):
    """Average all data point values for a metric (e.g. HRV, SpO2).

    HRV has multiple readings throughout the day that should be averaged.
    """
    for metric in metrics_list:
        if metric.get("name") == metric_name:
            data_points = metric.get("data", [])
            if data_points:
                values = [p.get("qty", 0) for p in data_points]
                return sum(values) / len(values) if values else None
    return None


def extract_sleep_data(metrics_list):
    """Extract sleep data with special field handling.

    Sleep uses totalSleep, rem, core, deep, awake fields (NOT qty).
    Values are already in hours — do NOT divide by 60.
    """
    for metric in metrics_list:
        if metric.get("name") == SLEEP_METRIC:
            data_points = metric.get("data", [])
            if data_points:
                latest = data_points[-1]
                return {
                    "total": latest.get("totalSleep", 0),
                    "rem": latest.get("rem", 0),
                    "core": latest.get("core", 0),
                    "deep": latest.get("deep", 0),
                    "awake": latest.get("awake", 0),
                }
    return None


def compute_averages(export_files, verbose=False):
    """Compute rolling averages from multiple export files.

    Uses the correct aggregation method per metric type:
    - LAST: weight, body_fat, RHR (single daily value, take last entry)
    - SUM: step_count (many per-minute entries, sum for daily total)
    - AVG: HRV, SpO2 (multiple readings, average for daily value)
    - Sleep: special fields (totalSleep, deep, etc.), already in hours
    """
    all_dash_keys = set()
    for m in (METRIC_MAP_LAST, METRIC_MAP_SUM, METRIC_MAP_AVG):
        all_dash_keys.update(m.values())
    aggregated = {k: [] for k in all_dash_keys}
    aggregated["sleep_total"] = []
    aggregated["deep_sleep"] = []

    for fpath in export_files:
        data = load_json(fpath)
        if not data:
            continue

        metrics = []
        if "data" in data and "metrics" in data["data"]:
            metrics = data["data"]["metrics"]
        elif "metrics" in data:
            metrics = data["metrics"]

        # Extract LAST-value metrics (weight, body fat, RHR)
        for export_name, dash_key in METRIC_MAP_LAST.items():
            val = extract_metric_last(metrics, export_name)
            if val is not None:
                try:
                    aggregated[dash_key].append(float(val))
                    if verbose:
                        log(f"  {dash_key}: {val} from {os.path.basename(fpath)}", "DEBUG")
                except (ValueError, TypeError):
                    pass

        # Extract SUM metrics (steps — sum all per-minute entries)
        for export_name, dash_key in METRIC_MAP_SUM.items():
            val = extract_metric_sum(metrics, export_name)
            if val is not None:
                try:
                    aggregated[dash_key].append(float(val))
                    if verbose:
                        log(f"  {dash_key}: {val} from {os.path.basename(fpath)}", "DEBUG")
                except (ValueError, TypeError):
                    pass

        # Extract AVG metrics (HRV, SpO2 — average multiple readings)
        for export_name, dash_key in METRIC_MAP_AVG.items():
            val = extract_metric_avg(metrics, export_name)
            if val is not None:
                try:
                    aggregated[dash_key].append(float(val))
                    if verbose:
                        log(f"  {dash_key}: {val} from {os.path.basename(fpath)}", "DEBUG")
                except (ValueError, TypeError):
                    pass

        # Extract sleep — values are ALREADY in hours, do NOT divide by 60
        sleep = extract_sleep_data(metrics)
        if sleep:
            if sleep["total"]:
                aggregated["sleep_total"].append(float(sleep["total"]))
            if sleep["deep"]:
                aggregated["deep_sleep"].append(float(sleep["deep"]))

    # Compute averages across days
    averages = {}
    for key, values in aggregated.items():
        if values:
            averages[key] = round(sum(values) / len(values), 1)

    return averages


def determine_trend(current, previous):
    """Determine trend direction."""
    if previous is None or current is None:
        return "stable"
    diff = current - previous
    threshold = abs(previous) * 0.02 if previous != 0 else 0.5
    if diff > threshold:
        return "up"
    elif diff < -threshold:
        return "down"
    return "stable"


def update_vitals(dashboard, averages, verbose=False):
    """Update vital signs in dashboard data."""
    vs = dashboard.get("vital_signs", {})
    today = datetime.now().strftime("%Y-%m-%d")

    mapping = {
        "weight":             ("weight", "lbs"),
        "body_fat":           ("body_fat", "%"),
        "resting_heart_rate": ("resting_heart_rate", "bpm"),
        "hrv":                ("hrv", "ms"),
        "spo2":               ("spo2", "%"),
        "steps_avg":          ("steps_avg", "steps"),
    }

    for avg_key, (vs_key, unit) in mapping.items():
        if avg_key in averages:
            old_val = vs.get(vs_key, {}).get("value")
            new_val = averages[avg_key]
            trend = determine_trend(new_val, old_val)

            if vs_key not in vs:
                vs[vs_key] = {}

            vs[vs_key]["value"] = new_val
            vs[vs_key]["unit"] = unit
            vs[vs_key]["trend"] = trend
            vs[vs_key]["date"] = today

            if verbose:
                log(f"  {vs_key}: {old_val} -> {new_val} ({trend})")

    # Sleep
    if "sleep_total" in averages:
        old_val = vs.get("sleep_avg", {}).get("value")
        vs.setdefault("sleep_avg", {})
        vs["sleep_avg"]["value"] = averages["sleep_total"]
        vs["sleep_avg"]["unit"] = "hrs"
        vs["sleep_avg"]["trend"] = determine_trend(averages["sleep_total"], old_val)
        vs["sleep_avg"]["date"] = today

    if "deep_sleep" in averages:
        old_val = vs.get("deep_sleep_avg", {}).get("value")
        new_val = averages["deep_sleep"]
        vs.setdefault("deep_sleep_avg", {})
        vs["deep_sleep_avg"]["value"] = new_val
        vs["deep_sleep_avg"]["unit"] = "hrs"
        vs["deep_sleep_avg"]["trend"] = determine_trend(new_val, old_val)
        vs["deep_sleep_avg"]["date"] = today
        # Flag deep sleep < 1.0h as red
        vs["deep_sleep_avg"]["status"] = "red" if new_val < 1.0 else "green"

    dashboard["vital_signs"] = vs
    return dashboard


def update_trends(dashboard, export_files, verbose=False):
    """Update trend chart data from recent exports."""
    if len(export_files) < 2:
        log("Not enough data points for trend update", "WARN")
        return dashboard

    trends = dashboard.get("trends", {})

    # Collect daily values
    daily_weight = []
    daily_hrv = []
    daily_sleep = []
    daily_steps = []

    for fpath in reversed(export_files):  # oldest first
        data = load_json(fpath)
        if not data:
            continue

        # Extract date from filename
        basename = os.path.basename(fpath)
        try:
            date_str = basename.replace("HealthAutoExport-", "").replace(".json", "")
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            label = dt.strftime("%b %d")
        except ValueError:
            continue

        metrics = []
        if "data" in data and "metrics" in data["data"]:
            metrics = data["data"]["metrics"]
        elif "metrics" in data:
            metrics = data["metrics"]

        w = extract_metric_last(metrics, "weight_body_mass")
        if w: daily_weight.append((label, round(float(w), 1)))

        h = extract_metric_avg(metrics, "heart_rate_variability")
        if h: daily_hrv.append((label, round(float(h), 1)))

        s = extract_sleep_data(metrics)
        if s and s.get("total"):
            daily_sleep.append((label, round(float(s["total"]), 1)))  # already in hours

        st = extract_metric_sum(metrics, "step_count")
        if st: daily_steps.append((label, int(float(st))))

    # Only update trends if we have data
    if daily_weight:
        trends["weight"] = {
            "labels": [d[0] for d in daily_weight],
            "values": [d[1] for d in daily_weight]
        }
    if daily_hrv:
        trends["hrv"] = {
            "labels": [d[0] for d in daily_hrv],
            "values": [d[1] for d in daily_hrv]
        }
    if daily_sleep:
        trends["sleep"] = {
            "labels": [d[0] for d in daily_sleep],
            "values": [d[1] for d in daily_sleep]
        }
    if daily_steps:
        trends["steps"] = {
            "labels": [d[0] for d in daily_steps],
            "values": [d[1] for d in daily_steps]
        }

    dashboard["trends"] = trends
    return dashboard


def update_biomarkers(dashboard, verbose=False):
    """Update biomarker data from Function Health cache if available."""
    fh_data = load_json(FUNCTION_HEALTH_CACHE)
    if not fh_data:
        log("Function Health cache not found — biomarkers unchanged", "WARN")
        return dashboard

    bio = dashboard.get("biomarkers", {})

    # Map Function Health categories to dashboard keys
    category_map = {
        "heart": "heart",
        "metabolic": "metabolic",
        "male_health": "male_health",
        "thyroid": "thyroid",
        "nutrients": "nutrients",
        "liver": "liver",
        "kidney": "kidney",
        "blood": "blood",
    }

    categories = fh_data.get("categories", fh_data.get("biomarker_categories", {}))
    for fh_key, dash_key in category_map.items():
        if fh_key in categories:
            cat = categories[fh_key]
            in_range = cat.get("in_range", cat.get("optimal", 0))
            total = cat.get("total", cat.get("tested", 0))

            if total > 0:
                pct = in_range / total
                status = "green" if pct >= 0.8 else "amber" if pct >= 0.5 else "red"

                bio.setdefault(dash_key, {})
                bio[dash_key]["in_range"] = in_range
                bio[dash_key]["total"] = total
                bio[dash_key]["status"] = status

                if verbose:
                    log(f"  {dash_key}: {in_range}/{total} ({status})")

    dashboard["biomarkers"] = bio
    return dashboard


def update_timestamp(dashboard):
    """Update the last-updated timestamp."""
    dashboard.setdefault("meta", {})
    dashboard["meta"]["last_updated"] = datetime.now().astimezone().isoformat()
    return dashboard


def main():
    parser = argparse.ArgumentParser(description="Health Dashboard Updater — Owens Life OS")
    parser.add_argument("--vitals", action="store_true", help="Update vitals only")
    parser.add_argument("--biomarkers", action="store_true", help="Update biomarkers only")
    parser.add_argument("--trends", action="store_true", help="Update trends only")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--verbose", action="store_true", help="Detailed output")
    parser.add_argument("--days", type=int, default=7, help="Number of days to average (default: 7)")
    args = parser.parse_args()

    update_all = not (args.vitals or args.biomarkers or args.trends)

    log("=" * 60)
    log("HEALTH DASHBOARD UPDATER — Starting")
    log("=" * 60)

    # Load existing dashboard data
    dashboard = load_json(DASHBOARD_DATA)
    if not dashboard:
        log("Dashboard data file not found — using empty template", "WARN")
        dashboard = {
            "meta": {"version": "1.0.0", "sources": []},
            "vital_signs": {},
            "biomarkers": {},
            "macros": {},
            "medications": [],
            "recommendations": {"supplements": [], "lifestyle": []},
            "monitoring": {"labs_due": [], "appointments": []},
            "trends": {}
        }

    original = deepcopy(dashboard)

    # Find export files
    export_files = find_latest_export_files(days=args.days)
    log(f"Found {len(export_files)} Health Auto Export files")

    # Update sections
    if update_all or args.vitals:
        log("Updating vital signs...")
        averages = compute_averages(export_files, verbose=args.verbose)
        if averages:
            dashboard = update_vitals(dashboard, averages, verbose=args.verbose)
            log(f"  Updated {len(averages)} metrics from {len(export_files)} files")
        else:
            log("  No new vital data available — keeping existing values", "WARN")

    if update_all or args.trends:
        log("Updating trend charts...")
        dashboard = update_trends(dashboard, export_files, verbose=args.verbose)

    if update_all or args.biomarkers:
        log("Updating biomarkers from Function Health...")
        dashboard = update_biomarkers(dashboard, verbose=args.verbose)

    # Always update timestamp
    dashboard = update_timestamp(dashboard)

    # Summary of changes
    changes = 0
    for key in ["vital_signs", "biomarkers", "trends"]:
        if dashboard.get(key) != original.get(key):
            changes += 1

    if args.dry_run:
        log("DRY RUN — Changes would be:", "INFO")
        log(f"  Sections modified: {changes}")
        log(json.dumps(dashboard.get("vital_signs", {}), indent=2))
    else:
        save_json(DASHBOARD_DATA, dashboard)
        log(f"Dashboard updated — {changes} sections modified")

    log("=" * 60)
    log("HEALTH DASHBOARD UPDATER — Complete")
    log("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
