#!/usr/bin/env python3
"""Task Health Monitor — checks freshness of scheduled task output files."""

import os
import time
from pathlib import Path

ICLOUD_BASE = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs"

# (filename, max_stale_days)
TASKS = [
    ("morning-sweep-latest.md", 2),
    ("eod-close-latest.md", 2),
    ("cop-sync-latest.md", 4),
    ("data-ingest-latest.md", 2),
]

def check_tasks():
    now = time.time()
    current = 0
    issues = []

    for filename, max_days in TASKS:
        filepath = ICLOUD_BASE / filename
        label = filename.replace("-latest.md", "")

        if not filepath.exists():
            issues.append(f"{label} (missing)")
            continue

        age_seconds = now - filepath.stat().st_mtime
        age_days = age_seconds / 86400

        if age_days > max_days:
            issues.append(f"{label} ({age_days:.0f}d)")
        else:
            current += 1

    total = len(TASKS)
    if issues:
        print(f"Tasks: {current}/{total} current | STALE: {', '.join(issues)}")
    else:
        print(f"Tasks: {total}/{total} current | All GREEN")

if __name__ == "__main__":
    check_tasks()
