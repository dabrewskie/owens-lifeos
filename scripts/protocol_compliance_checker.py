#!/usr/bin/env python3
"""Health protocol compliance checker — reads yesterday's Health Auto Export JSON
and checks protein, calories, deep sleep, and steps against targets."""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

def main():
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    base_dir = os.path.expanduser(
        "~/Library/Mobile Documents/iCloud~com~ifunography~HealthExport/Documents/Health Metrics"
    )
    json_path = os.path.join(base_dir, f"HealthAutoExport-{yesterday}.json")

    if not os.path.exists(json_path):
        print(f"Protocol: No data for yesterday ({yesterday})")
        return

    try:
        with open(json_path, "r") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, IOError):
        print(f"Protocol: No data for yesterday ({yesterday})")
        return

    metrics_list = raw.get("data", {}).get("metrics", [])
    metrics = {}
    for m in metrics_list:
        name = m.get("name", "")
        metrics[name] = m.get("data", [])

    # --- Extract values ---
    # Protein (dietary_protein, qty, sum for day)
    protein = None
    for key in metrics:
        if "dietary_protein" in key.lower() or key == "dietary_protein":
            entries = metrics[key]
            if entries:
                protein = sum(e.get("qty", 0) for e in entries)
            break
    if protein is None:
        for key in metrics:
            if "protein" in key.lower():
                entries = metrics[key]
                if entries:
                    protein = sum(e.get("qty", 0) for e in entries)
                break

    # Calories (dietary_energy, qty, sum for day)
    calories = None
    for key in metrics:
        if "dietary_energy" in key.lower() or key == "dietary_energy":
            entries = metrics[key]
            if entries:
                calories = sum(e.get("qty", 0) for e in entries)
            break
    if calories is None:
        for key in metrics:
            if "energy" in key.lower() and "dietary" in key.lower():
                entries = metrics[key]
                if entries:
                    calories = sum(e.get("qty", 0) for e in entries)
                break

    # Deep sleep (look for sleep metric, use "deep" field in minutes -> hours)
    deep_sleep_hrs = None
    for key in metrics:
        if "sleep" in key.lower():
            entries = metrics[key]
            if entries:
                # Sum deep sleep across all entries; field is in minutes
                total_deep_min = 0
                found_deep = False
                for e in entries:
                    if "deep" in e:
                        total_deep_min += e["deep"]
                        found_deep = True
                if found_deep:
                    deep_sleep_hrs = total_deep_min / 60.0
            break

    # Steps (step_count, qty, sum for day)
    steps = None
    for key in metrics:
        if "step_count" in key.lower() or key == "step_count":
            entries = metrics[key]
            if entries:
                steps = sum(e.get("qty", 0) for e in entries)
            break
    if steps is None:
        for key in metrics:
            if "step" in key.lower():
                entries = metrics[key]
                if entries:
                    steps = sum(e.get("qty", 0) for e in entries)
                break

    # --- Check compliance ---
    checks = []
    misses = []

    # Protein >= 190g
    if protein is not None:
        if protein >= 190:
            checks.append(True)
        else:
            checks.append(False)
            misses.append(f"protein ({int(protein)}g/210g)")
    else:
        checks.append(False)
        misses.append("protein (no data)")

    # Calories 1800-2200
    if calories is not None:
        if 1800 <= calories <= 2200:
            checks.append(True)
        else:
            checks.append(False)
            misses.append(f"calories ({int(calories)}/2000)")
    else:
        checks.append(False)
        misses.append("calories (no data)")

    # Deep sleep >= 1.0h
    if deep_sleep_hrs is not None:
        if deep_sleep_hrs >= 1.0:
            checks.append(True)
        else:
            checks.append(False)
            misses.append(f"deep sleep ({deep_sleep_hrs:.1f}h/1.0h)")
    else:
        checks.append(False)
        misses.append("deep sleep (no data)")

    # Steps >= 7000
    if steps is not None:
        if steps >= 7000:
            checks.append(True)
        else:
            checks.append(False)
            misses.append(f"steps ({int(steps)}/7000)")
    else:
        checks.append(False)
        misses.append("steps (no data)")

    compliant = sum(checks)
    total = len(checks)

    if compliant == total:
        print(f"Protocol: {compliant}/{total} compliant | All targets met")
    else:
        print(f"Protocol: {compliant}/{total} compliant | MISS: {', '.join(misses)}")


if __name__ == "__main__":
    main()
