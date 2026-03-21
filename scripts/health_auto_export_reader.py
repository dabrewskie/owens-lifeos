#!/usr/bin/env python3
"""
health_auto_export_reader.py

Reads health data from Health Auto Export app's iCloud container.
Actual path: ~/Library/Mobile Documents/iCloud~com~ifunography~HealthExport/Documents/Health Metrics/
Format: Daily JSON files (HealthAutoExport-YYYY-MM-DD.json)
Structure: {"data": {"metrics": [{"name": "...", "units": "...", "data": [...]}]}}

Outputs a summary for the Life OS morning sweep, COP sync, and health checks.

Updated: 2026-03-09 — Fixed path and format to match actual Health Auto Export app output.
"""

import json
import os
import glob
import sys
from datetime import datetime, timedelta
from collections import defaultdict

# CORRECT path — Health Auto Export app's own iCloud container
HAE_JSON_DIR = os.path.expanduser(
    "~/Library/Mobile Documents/iCloud~com~ifunography~HealthExport/Documents/Health Metrics"
)

# Fallback paths (legacy)
HAE_CSV_DIR = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/Health/health_auto_export"
)
APPLE_HEALTH_XML = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/apple_health_export/export.xml"
)

MACRO_TARGETS = {
    "protein": 210,
    "carbs": 130,
    "fat": 71,
    "calories": 2000,
}


def find_json_files(days_back=7):
    """Find Health Auto Export daily JSON files from the last N days."""
    if not os.path.isdir(HAE_JSON_DIR):
        return []

    files = sorted(glob.glob(os.path.join(HAE_JSON_DIR, "HealthAutoExport-*.json")))
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    result = []
    for f in files:
        basename = os.path.basename(f)
        # Extract date from filename: HealthAutoExport-YYYY-MM-DD.json
        date_part = basename.replace("HealthAutoExport-", "").replace(".json", "")
        if len(date_part) == 10 and date_part >= cutoff:  # YYYY-MM-DD format
            result.append((date_part, f))

    return sorted(result, key=lambda x: x[0])


def parse_daily_json(filepath):
    """Parse a single day's Health Auto Export JSON file."""
    try:
        with open(filepath) as f:
            data = json.load(f)
        metrics = {}
        raw_metrics = []
        if isinstance(data, dict):
            if "data" in data and "metrics" in data["data"]:
                raw_metrics = data["data"]["metrics"]
            elif "metrics" in data:
                raw_metrics = data["metrics"]

        for m in raw_metrics:
            name = m.get("name", "")
            metrics[name] = {
                "units": m.get("units", ""),
                "data": m.get("data", []),
            }
        return metrics
    except Exception as e:
        print(f"  ⚠ Error reading {filepath}: {e}", file=sys.stderr)
        return {}


def extract_macros(metrics):
    """Extract macro totals from a day's metrics."""
    name_map = {
        "dietary_energy": "calories",
        "protein": "protein",
        "carbohydrates": "carbs",
        "total_fat": "fat",
    }
    totals = defaultdict(float)
    for metric_name, macro_key in name_map.items():
        if metric_name in metrics:
            for entry in metrics[metric_name]["data"]:
                qty = entry.get("qty", 0)
                try:
                    totals[macro_key] += float(qty)
                except (TypeError, ValueError):
                    pass
    return totals


def extract_sleep(metrics):
    """Extract sleep data. Sleep uses special fields, not 'qty'."""
    if "sleep_analysis" not in metrics:
        return None
    data = metrics["sleep_analysis"]["data"]
    if not data:
        return None
    # Use the latest sleep entry
    latest = data[-1]
    return {
        "total": latest.get("totalSleep", 0),
        "rem": latest.get("rem", 0),
        "core": latest.get("core", 0),
        "deep": latest.get("deep", 0),
        "awake": latest.get("awake", 0),
        "start": latest.get("sleepStart", ""),
        "end": latest.get("sleepEnd", ""),
    }


def extract_vitals(metrics):
    """Extract vital signs from a day's metrics."""
    vitals = {}

    # Resting heart rate
    if "resting_heart_rate" in metrics:
        pts = metrics["resting_heart_rate"]["data"]
        if pts:
            vitals["rhr"] = pts[-1].get("qty", 0)

    # Heart rate variability (average)
    if "heart_rate_variability" in metrics:
        pts = metrics["heart_rate_variability"]["data"]
        if pts:
            vitals["hrv"] = sum(p.get("qty", 0) for p in pts) / len(pts)

    # Blood oxygen (average)
    if "blood_oxygen_saturation" in metrics:
        pts = metrics["blood_oxygen_saturation"]["data"]
        if pts:
            vitals["spo2"] = sum(p.get("qty", 0) for p in pts) / len(pts)

    # Respiratory rate (average)
    if "respiratory_rate" in metrics:
        pts = metrics["respiratory_rate"]["data"]
        if pts:
            vitals["resp_rate"] = sum(p.get("qty", 0) for p in pts) / len(pts)

    # Wrist temperature
    if "apple_sleeping_wrist_temperature" in metrics:
        pts = metrics["apple_sleeping_wrist_temperature"]["data"]
        if pts:
            vitals["wrist_temp"] = pts[-1].get("qty", 0)

    return vitals


def extract_activity(metrics):
    """Extract activity metrics from a day's data."""
    activity = {}

    # Steps
    if "step_count" in metrics:
        pts = metrics["step_count"]["data"]
        activity["steps"] = sum(p.get("qty", 0) for p in pts)

    # Active energy
    if "active_energy" in metrics:
        pts = metrics["active_energy"]["data"]
        activity["active_cal"] = sum(p.get("qty", 0) for p in pts)

    # Exercise time
    if "apple_exercise_time" in metrics:
        pts = metrics["apple_exercise_time"]["data"]
        activity["exercise_min"] = sum(p.get("qty", 0) for p in pts)

    # Flights climbed
    if "flights_climbed" in metrics:
        pts = metrics["flights_climbed"]["data"]
        activity["flights"] = sum(p.get("qty", 0) for p in pts)

    # Walking distance
    if "walking_running_distance" in metrics:
        pts = metrics["walking_running_distance"]["data"]
        activity["distance_mi"] = sum(p.get("qty", 0) for p in pts)

    return activity


def extract_weight(metrics):
    """Extract weight/body comp data."""
    weight = {}
    if "weight_body_mass" in metrics:
        pts = metrics["weight_body_mass"]["data"]
        if pts:
            weight["weight"] = pts[-1].get("qty", 0)
            weight["unit"] = metrics["weight_body_mass"].get("units", "lb")
    if "body_fat_percentage" in metrics:
        pts = metrics["body_fat_percentage"]["data"]
        if pts:
            weight["body_fat"] = pts[-1].get("qty", 0)
    return weight


def fmt_delta(v):
    """Format a delta value with +/- sign."""
    return f"+{v:.0f}" if v >= 0 else f"{v:.0f}"


def report_full(days_back=7):
    """Generate full health report from Health Auto Export JSON data."""
    files = find_json_files(days_back=days_back)

    if not files:
        print("  ⚠ No Health Auto Export JSON files found")
        print(f"  Expected at: {HAE_JSON_DIR}")
        print("  Action: Export from Health Auto Export app on iPhone")
        return False

    latest_date = files[-1][0]
    latest_file = files[-1][1]
    file_age = (datetime.now() - datetime.strptime(latest_date, "%Y-%m-%d")).days

    print(f"  Source: Health Auto Export JSON ({len(files)} days)")
    print(f"  Latest: {latest_date} ({file_age}d ago)")
    if file_age > 3:
        print(f"  ⚠ DATA STALE ({file_age} days) — export from iPhone needed")
    print()

    # === MACRO COMPLIANCE ===
    print("  ── MACRO COMPLIANCE ──")
    all_macros = {}
    for date, fpath in files:
        metrics = parse_daily_json(fpath)
        macros = extract_macros(metrics)
        if any(macros.values()):
            all_macros[date] = macros

    if all_macros:
        dates = sorted(all_macros.keys(), reverse=True)
        # Latest day with data
        latest_macro_date = dates[0]
        d = all_macros[latest_macro_date]
        p, c, f_val, cal = d.get("protein", 0), d.get("carbs", 0), d.get("fat", 0), d.get("calories", 0)

        dp = p - MACRO_TARGETS["protein"]
        dc = c - MACRO_TARGETS["carbs"]
        df = f_val - MACRO_TARGETS["fat"]
        dcal = cal - MACRO_TARGETS["calories"]

        print(f"  Latest ({latest_macro_date}): {p:.0f}g P / {c:.0f}g C / {f_val:.0f}g F = {cal:.0f} kcal")
        print(f"    vs targets: P {fmt_delta(dp)}g | C {fmt_delta(dc)}g | F {fmt_delta(df)}g | cal {fmt_delta(dcal)}")

        # Multi-day averages
        days_with_data = [d for d in dates if any(all_macros[d].values())]
        n = min(7, len(days_with_data))
        if n >= 3:
            avg_p = sum(all_macros[d].get("protein", 0) for d in days_with_data[:n]) / n
            avg_c = sum(all_macros[d].get("carbs", 0) for d in days_with_data[:n]) / n
            avg_f = sum(all_macros[d].get("fat", 0) for d in days_with_data[:n]) / n
            avg_cal = sum(all_macros[d].get("calories", 0) for d in days_with_data[:n]) / n
            p_pct = (avg_p / MACRO_TARGETS["protein"]) * 100
            print(f"    {n}-day avg: {avg_p:.0f}g P ({p_pct:.0f}%) / {avg_c:.0f}g C / {avg_f:.0f}g F / {avg_cal:.0f} kcal")

            # Count days hitting protein target (within 10%)
            hits = sum(1 for d in days_with_data[:n] if all_macros[d].get("protein", 0) >= MACRO_TARGETS["protein"] * 0.9)
            print(f"    Protein compliance: {hits}/{n} days at ≥90% target")
    else:
        print("  No macro data (Cronometer not logging?)")

    print()

    # === SLEEP ===
    print("  ── SLEEP ──")
    sleep_data = []
    for date, fpath in files[-7:]:
        metrics = parse_daily_json(fpath)
        sleep = extract_sleep(metrics)
        if sleep and sleep["total"] > 0:
            sleep_data.append((date, sleep))

    if sleep_data:
        latest_sleep = sleep_data[-1]
        s = latest_sleep[1]
        print(f"  Latest ({latest_sleep[0]}): {s['total']:.1f}h total | {s['deep']:.1f}h deep | {s['rem']:.1f}h REM | {s['core']:.1f}h core")
        if len(sleep_data) >= 3:
            avg_total = sum(s[1]["total"] for s in sleep_data) / len(sleep_data)
            avg_deep = sum(s[1]["deep"] for s in sleep_data) / len(sleep_data)
            print(f"    {len(sleep_data)}-day avg: {avg_total:.1f}h total | {avg_deep:.1f}h deep")
    else:
        print("  No sleep data in export")

    print()

    # === VITALS ===
    print("  ── VITALS ──")
    latest_metrics = parse_daily_json(files[-1][1])
    # Use second-to-last if today's file has no vitals yet
    if len(files) >= 2:
        yesterday_metrics = parse_daily_json(files[-2][1])
        vitals = extract_vitals(yesterday_metrics)
        vitals_date = files[-2][0]
    else:
        vitals = extract_vitals(latest_metrics)
        vitals_date = files[-1][0]

    if vitals:
        parts = []
        if "rhr" in vitals:
            parts.append(f"RHR {vitals['rhr']:.0f}")
        if "hrv" in vitals:
            parts.append(f"HRV {vitals['hrv']:.0f}ms")
        if "spo2" in vitals:
            parts.append(f"SpO2 {vitals['spo2']:.0f}%")
        if "resp_rate" in vitals:
            parts.append(f"Resp {vitals['resp_rate']:.1f}/min")
        if "wrist_temp" in vitals:
            parts.append(f"Temp {vitals['wrist_temp']:.1f}°F")
        print(f"  Latest ({vitals_date}): {' | '.join(parts)}")

        # HRV trend
        hrv_data = []
        for date, fpath in files[-7:]:
            m = parse_daily_json(fpath)
            v = extract_vitals(m)
            if "hrv" in v:
                hrv_data.append((date, v["hrv"]))
        if len(hrv_data) >= 3:
            avg_hrv = sum(h[1] for h in hrv_data) / len(hrv_data)
            trend = "↑" if hrv_data[-1][1] > avg_hrv else "↓" if hrv_data[-1][1] < avg_hrv * 0.9 else "→"
            print(f"    HRV trend: {avg_hrv:.0f}ms avg ({len(hrv_data)}d) {trend}")
    else:
        print("  No vitals data")

    print()

    # === ACTIVITY ===
    print("  ── ACTIVITY ──")
    activity_data = []
    for date, fpath in files[-7:]:
        m = parse_daily_json(fpath)
        act = extract_activity(m)
        if act.get("steps", 0) > 0:
            activity_data.append((date, act))

    if activity_data:
        latest_act = activity_data[-1]
        a = latest_act[1]
        parts = []
        if "steps" in a:
            parts.append(f"{a['steps']:.0f} steps")
        if "active_cal" in a:
            parts.append(f"{a['active_cal']:.0f} active cal")
        if "exercise_min" in a:
            parts.append(f"{a['exercise_min']:.0f} exercise min")
        if "distance_mi" in a:
            parts.append(f"{a['distance_mi']:.1f} mi")
        print(f"  Latest ({latest_act[0]}): {' | '.join(parts)}")

        if len(activity_data) >= 3:
            avg_steps = sum(a[1].get("steps", 0) for a in activity_data) / len(activity_data)
            avg_cal = sum(a[1].get("active_cal", 0) for a in activity_data) / len(activity_data)
            print(f"    {len(activity_data)}-day avg: {avg_steps:.0f} steps | {avg_cal:.0f} active cal")
    else:
        print("  No activity data")

    print()

    # === WEIGHT / BODY COMP ===
    print("  ── BODY COMPOSITION ──")
    weight_found = False
    for date, fpath in reversed(files):
        m = parse_daily_json(fpath)
        w = extract_weight(m)
        if w.get("weight"):
            print(f"  Latest ({date}): {w['weight']:.1f} lbs", end="")
            if w.get("body_fat"):
                print(f" | {w['body_fat']:.1f}% BF", end="")
            print()
            weight_found = True
            break
    if not weight_found:
        print("  No weight data in recent exports")

    print()
    return True


def main():
    print("💊 HEALTH OPS DATA PULL")
    print("=" * 40)

    # Check data freshness
    files = find_json_files(days_back=30)
    if files:
        latest_date = files[-1][0]
        file_age = (datetime.now() - datetime.strptime(latest_date, "%Y-%m-%d")).days
        status = "GREEN" if file_age <= 1 else "AMBER" if file_age <= 3 else "RED"
        print(f"  Data freshness: {status} (latest: {latest_date}, {file_age}d ago)")
        if file_age > 3:
            print(f"  ⚠ STALE — Commander: export from Health Auto Export on iPhone")
    else:
        print("  Data freshness: RED (no data found)")
        print(f"  Expected at: {HAE_JSON_DIR}")
        return

    print()
    report_full(days_back=14)


if __name__ == "__main__":
    main()
