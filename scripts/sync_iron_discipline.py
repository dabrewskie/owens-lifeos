#!/usr/bin/env python3
"""
sync_iron_discipline.py — sync Iron Discipline plan to data/iron_discipline.json.

V1: rewrites last_synced timestamp on the existing canonical JSON.
    The xlsx parser is a follow-up — for now this is the source-of-truth
    write path. The plan body was hand-curated from the Drive xlsx
    (file_id 1uvxwHWQXCpDReDZEPnkLqAq7SE-ItDpm).

V2 (future): pull the xlsx via Drive API, parse the sheets, regenerate.
    Hook the Drive client off lifeos_mcp_server.py credentials.

Usage:
    python3 sync_iron_discipline.py            # bump last_synced timestamp
    python3 sync_iron_discipline.py --check    # validate schema only
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.home() / "owens-lifeos"
DATA_DIR = REPO / "data"
PLAN_FILE = DATA_DIR / "iron_discipline.json"

REQUIRED_TOP_KEYS = {
    "meta", "weekly_structure", "macros", "weekly_avg",
    "rep_scheme", "progressive_overload_rule", "sessions", "weekly_progress",
}
REQUIRED_DAY_TYPES = {"TRAINING", "ACTIVE_RECOVERY", "FULL_REST"}
SCAN_WEEKDAY = 2  # Wednesday — PCC banner hardcodes "Wednesday is scan day"
WEEKDAY_NAME = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]


def validate(plan: dict) -> list[str]:
    """Return list of validation errors (empty if valid)."""
    errors = []
    missing = REQUIRED_TOP_KEYS - set(plan.keys())
    if missing:
        errors.append(f"missing top-level keys: {sorted(missing)}")
    macros = plan.get("macros") or {}
    missing_dt = REQUIRED_DAY_TYPES - set(macros.keys())
    if missing_dt:
        errors.append(f"missing macro day-types: {sorted(missing_dt)}")
    sessions = plan.get("sessions") or {}
    if not sessions:
        errors.append("no sessions defined")
    for sid, sess in sessions.items():
        if "exercises" not in sess or not sess["exercises"]:
            errors.append(f"session {sid} has no exercises")
    meta = plan.get("meta") or {}
    for k in ("program", "start_date", "end_date", "total_weeks"):
        if k not in meta:
            errors.append(f"meta missing {k}")
    weeks = (plan.get("weekly_progress") or {}).get("weeks") or []
    for w in weeks:
        sd = w.get("scan_date")
        if not sd:
            continue
        try:
            dt = datetime.strptime(sd, "%Y-%m-%d").date()
        except ValueError:
            errors.append(f"week {w.get('week')} scan_date not YYYY-MM-DD: {sd!r}")
            continue
        if dt.weekday() != SCAN_WEEKDAY:
            errors.append(
                f"week {w.get('week')} scan_date {sd} is {WEEKDAY_NAME[dt.weekday()]}, "
                f"expected {WEEKDAY_NAME[SCAN_WEEKDAY]} — PCC banner hardcodes Wed scan day"
            )
    return errors


def sync(check_only: bool = False) -> int:
    if not PLAN_FILE.exists():
        print(f"[ERR] plan file not found: {PLAN_FILE}", file=sys.stderr)
        return 1
    try:
        plan = json.loads(PLAN_FILE.read_text())
    except json.JSONDecodeError as e:
        print(f"[ERR] plan file invalid JSON: {e}", file=sys.stderr)
        return 1

    errors = validate(plan)
    if errors:
        for e in errors:
            print(f"[ERR] {e}", file=sys.stderr)
        return 2

    if check_only:
        print(f"[OK] plan valid · {plan['meta']['total_weeks']}wk · "
              f"{len(plan['sessions'])} sessions · "
              f"{plan['meta']['start_date']} -> {plan['meta']['end_date']}")
        return 0

    plan["meta"]["last_synced"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    PLAN_FILE.write_text(json.dumps(plan, indent=2) + "\n")
    print(f"[OK] last_synced = {plan['meta']['last_synced']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Iron Discipline plan")
    parser.add_argument("--check", action="store_true", help="validate only; do not write")
    args = parser.parse_args()
    return sync(check_only=args.check)


if __name__ == "__main__":
    sys.exit(main())
