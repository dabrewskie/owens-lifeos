#!/usr/bin/env python3
"""
state_synthesizer.py — Pure-Python aggregator for Overwatch + Prophet input.

Architecture (deployed 2026-04-30):
    Old: Each Overwatch/Prophet run loaded many discrete files inline in the
    LLM prompt, then synthesized across them in a single call. Duration trend
    623s → 742s → consistent 720s TIMEOUT. File gathering is mechanical and
    cheap in Python, but synthesis is expensive in LLM. Doing both together
    pushed inference past the 720s envelope.

    New: This module gathers EVERY state file Overwatch + Prophet would
    otherwise read individually, in <5s of pure Python with no LLM calls.
    Output is one consolidated JSON file at:
        ~/Documents/S6_COMMS_TECH/dashboard/overwatch_input.json

    Both Overwatch and Pattern Prophet read EXACTLY ONE FILE:
    overwatch_input.json. They differ only in PROMPT (focus) and OUTPUT
    (write target). "Prophet and Overwatch see all" — same snapshot.

Usage:
    python3 state_synthesizer.py            # write to default path
    python3 state_synthesizer.py --no-write # print JSON to stdout
    python3 state_synthesizer.py --pretty   # indent=2 (default already)

Constraints:
    - Pure Python, std library only.
    - NO LLM calls.
    - Schema must contain ALL required top-level keys even on missing data
      (graceful degrade — None/empty rather than missing).
    - Total runtime <5s.

Schema: see SCHEMA_VERSION block in synthesize() docstring.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = "1.0"

# ── Paths (canonical) ────────────────────────────────────────────────
HOME = Path.home()
DASHBOARD_DIR = HOME / "Documents" / "S6_COMMS_TECH" / "dashboard"
SCRIPTS_DIR = HOME / "Documents" / "S6_COMMS_TECH" / "scripts"
ICLOUD = HOME / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
OWENS_LIFEOS_DATA = HOME / "owens-lifeos" / "data"

# Output target
OUT_PATH = DASHBOARD_DIR / "overwatch_input.json"

# Source files
COP_PATH = DASHBOARD_DIR / "cop_data.json"
CCIR_PATH = DASHBOARD_DIR / "ccir_cards.json"
ACTION_QUEUE_PATH = DASHBOARD_DIR / "action_queue.json"
PENDING_PATH = DASHBOARD_DIR / "pending_actions.json"
TASK_HEALTH_PATH = DASHBOARD_DIR / "task_health.json"
HEALTH_DATA_CANONICAL = DASHBOARD_DIR / "health" / "health_data.json"
HEALTH_DATA_MIRROR = OWENS_LIFEOS_DATA / "health_data.json"
IRON_DISCIPLINE_PATH = OWENS_LIFEOS_DATA / "iron_discipline.json"
SCANS_PATH = OWENS_LIFEOS_DATA / "scans.json"
PROTEIN_LOG_PATH = OWENS_LIFEOS_DATA / "protein_log.json"
FORMATION_LOG_PATH = DASHBOARD_DIR / "formation_log.json"
SUPERAGENT_STATE_PATH = DASHBOARD_DIR / "superagent_state.json"
JOURNAL_PATH = DASHBOARD_DIR / "superagent_journal.md"
GUI_STATE_PATH = DASHBOARD_DIR / "gui_state.json"
CALENDAR_MIRROR_PATH = DASHBOARD_DIR / "calendar_mirror_log.json"
ORCHESTRATOR_LOG_PATH = SCRIPTS_DIR / "cleanup_logs" / "orchestrator.log"
RELATIONSHIP_INTEL_PATH = DASHBOARD_DIR / "relationship_intel.json"
ROCKET_MONEY_DIR = HOME / "Downloads"

# iCloud battle rhythm artifacts
OVERWATCH_LATEST = ICLOUD / "overwatch-latest.md"
MORNING_SWEEP_LATEST = ICLOUD / "morning-sweep-latest.md"
COP_SYNC_LATEST = ICLOUD / "cop-sync-latest.md"
EOD_CLOSE_LATEST = ICLOUD / "eod-close-latest.md"

# Agent freshness mapping: dashboard JSON → conceptual agent name
AGENT_OUTPUT_FILES = {
    "patrol_horizon": DASHBOARD_DIR / "life_horizons.json",
    "patrol_relationship": DASHBOARD_DIR / "relationship_intel.json",
    "patrol_opportunity": DASHBOARD_DIR / "opportunities.json",
    "evolution_engine": DASHBOARD_DIR / "evolution_data.json",
    "accountability_tracker": DASHBOARD_DIR / "accountability_report.json",
    "pattern_prophet": DASHBOARD_DIR / "pattern_prophet_output.json",
}

BATTLE_RHYTHM_FILES = {
    "morning-sweep-latest.md": MORNING_SWEEP_LATEST,
    "cop-sync-latest.md": COP_SYNC_LATEST,
    "eod-close-latest.md": EOD_CLOSE_LATEST,
    "overwatch-latest.md": OVERWATCH_LATEST,
}

# Caps to keep output under target (~110 KB target, 150 KB soft ceiling)
# EE-Cycle11 2026-05-01: reduced from 200KB target. Root cause: 150KB file at 3.3s/KB
# token rate → 495s overwatch_morning inference (exceeded 480s runner TIMEOUT).
# action_queue was 41KB (30 items); orchestrator_log was 9.7KB (200 lines).
# Cap reduction targets ~115KB → ~380s inference, well within 600s runner limit.
ACTION_QUEUE_ACTIVE_CAP = 12   # was 30; 12 items covers all urgent + near-term actions
JOURNAL_RECENT_CHAR_CAP = 3000
JOURNAL_RECENT_ENTRY_COUNT = 5
PREVIOUS_OVERWATCH_CHAR_CAP = 3000
ORCHESTRATOR_LOG_TAIL_LINES = 100  # was 200; 100 lines = ~3 orchestrator cycles (sufficient)
FORMATION_RECENT_COUNT = 5


# ── Helpers ──────────────────────────────────────────────────────────
def safe_load_json(path: Path, default: Any = None) -> Any:
    """Load JSON file, return default on any failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def file_age_hours(path: Path) -> float:
    """Hours since file last modified, or +inf if missing."""
    try:
        if not path.exists():
            return float("inf")
        return (time.time() - path.stat().st_mtime) / 3600.0
    except Exception:
        return float("inf")


def safe_age_hours(path: Path) -> Optional[float]:
    """JSON-safe version: returns None instead of inf for missing."""
    age = file_age_hours(path)
    if age == float("inf"):
        return None
    return round(age, 2)


def tail_text(path: Path, max_chars: int) -> str:
    """Return last max_chars of file, empty string if missing."""
    try:
        if not path.exists():
            return ""
        txt = path.read_text(encoding="utf-8", errors="ignore")
        return txt[-max_chars:] if len(txt) > max_chars else txt
    except Exception:
        return ""


def tail_lines(path: Path, n: int) -> str:
    """Efficient tail-N-lines on a possibly large file."""
    try:
        if not path.exists():
            return ""
        with open(path, "rb") as f:
            f.seek(0, 2)
            end = f.tell()
            block = 4096
            data = b""
            while end > 0 and data.count(b"\n") <= n:
                read = min(block, end)
                f.seek(end - read)
                data = f.read(read) + data
                end -= read
            text = data.decode("utf-8", errors="ignore")
        lines = text.split("\n")
        return "\n".join(lines[-n:])
    except Exception:
        return ""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def local_now_iso() -> str:
    return datetime.now().isoformat()


# ── Section builders ─────────────────────────────────────────────────
def build_today() -> dict:
    now = datetime.now()
    weekdays = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    return {
        "iso_date": now.strftime("%Y-%m-%d"),
        "day_of_week": weekdays[now.weekday()],
        "hour_24": now.hour,
    }


def build_action_queue() -> dict:
    """Read action_queue.json, summarize counts, cap active list."""
    raw = safe_load_json(ACTION_QUEUE_PATH, default={"cards": []})
    cards = raw.get("cards", []) if isinstance(raw, dict) else []
    if not isinstance(cards, list):
        cards = []
    active = [c for c in cards if isinstance(c, dict) and c.get("state") == "active"]
    deferred = [c for c in cards if isinstance(c, dict) and c.get("state") == "deferred"]
    today_iso = datetime.now().strftime("%Y-%m-%d")
    resolved_today = [
        c for c in cards
        if isinstance(c, dict)
        and c.get("state") in ("resolved", "done")
        and isinstance(c.get("resolved_at"), str)
        and c.get("resolved_at", "").startswith(today_iso)
    ]
    return {
        "active_count": len(active),
        "deferred_count": len(deferred),
        "resolved_today_count": len(resolved_today),
        "active": active[:ACTION_QUEUE_ACTIVE_CAP],
        "deferred": deferred,
    }


def build_task_health() -> dict:
    """Summarize task_health.json by status, surface RED/AMBER, keep all."""
    raw = safe_load_json(TASK_HEALTH_PATH, default={"tasks": {}})
    tasks = raw.get("tasks", {}) if isinstance(raw, dict) else {}
    if not isinstance(tasks, dict):
        tasks = {}
    summary = {"green": 0, "amber": 0, "red": 0, "retired": 0, "unknown": 0}
    red_or_amber = []
    for name, t in tasks.items():
        if not isinstance(t, dict):
            summary["unknown"] += 1
            continue
        status = (t.get("status") or "UNKNOWN").upper()
        key = status.lower()
        if key in summary:
            summary[key] += 1
        else:
            summary["unknown"] += 1
        if status in ("RED", "AMBER"):
            red_or_amber.append({
                "name": name,
                "status": status,
                "last_run": t.get("last_run"),
                "last_success": t.get("last_success"),
                "last_error": t.get("last_error"),
                "consecutive_failures": t.get("consecutive_failures"),
                "last_duration": t.get("last_duration"),
            })
    # EE-Cycle11 2026-05-01: exclude RETIRED/ARCHIVED tasks from "all" to reduce file size.
    # Overwatch doesn't need retired task details; RED/AMBER already captured above.
    active_tasks = {
        k: v for k, v in tasks.items()
        if isinstance(v, dict) and v.get("status", "").upper() not in ("RETIRED", "ARCHIVED")
    }
    return {
        "summary": summary,
        "red_or_amber": red_or_amber,
        "all": active_tasks,  # Active tasks only (~5KB savings from excluding 15 RETIRED tasks)
    }


def build_health_vitals() -> dict:
    """Pull vital_signs from canonical health_data.json (fallback to mirror)."""
    raw = safe_load_json(HEALTH_DATA_CANONICAL)
    if raw is None:
        raw = safe_load_json(HEALTH_DATA_MIRROR, default={})
    if not isinstance(raw, dict):
        return {}
    vitals = raw.get("vital_signs", {}) if isinstance(raw.get("vital_signs"), dict) else {}
    keys = ["weight", "body_fat", "sleep_avg", "deep_sleep_avg", "hrv",
            "spo2", "resting_heart_rate", "steps_avg"]
    out = {}
    for k in keys:
        out[k] = vitals.get(k) if isinstance(vitals.get(k), dict) else vitals.get(k)
    return out


def build_macros_today(iron: Optional[dict]) -> dict:
    """Pull today's macro targets + actual eaten chips from protein_log."""
    out = {
        "kcal_eaten": None,
        "kcal_target": None,
        "protein_eaten_g": None,
        "protein_target_g": None,
        "logged_chip_grams_today": 0.0,
    }
    # Targets from iron_discipline based on today's day type
    if isinstance(iron, dict):
        weekdays = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        dow = weekdays[datetime.now().weekday()]
        weekly = iron.get("weekly_structure", {})
        if isinstance(weekly, dict):
            day_struct = weekly.get(dow, {})
            if isinstance(day_struct, dict):
                day_type = day_struct.get("type")
                macros = iron.get("macros", {})
                if isinstance(macros, dict) and day_type and isinstance(macros.get(day_type), dict):
                    out["kcal_target"] = macros[day_type].get("kcal")
                    out["protein_target_g"] = macros[day_type].get("protein_g")
    # Eaten — sum protein_log entries dated today (chip = 30g protein default)
    plog = safe_load_json(PROTEIN_LOG_PATH, default=[])
    if isinstance(plog, list):
        today_iso = datetime.now().strftime("%Y-%m-%d")
        total_grams = 0.0
        for entry in plog:
            if not isinstance(entry, dict):
                continue
            ts = entry.get("ts", "")
            if isinstance(ts, str) and ts.startswith(today_iso):
                grams = entry.get("grams")
                if isinstance(grams, (int, float)):
                    total_grams += float(grams)
        out["logged_chip_grams_today"] = round(total_grams, 1)
    return out


def build_iron_discipline() -> dict:
    """Iron Discipline state: week, session today, scans, macros."""
    raw = safe_load_json(IRON_DISCIPLINE_PATH)
    if not isinstance(raw, dict):
        return {
            "program": None,
            "current_week": None,
            "total_weeks": None,
            "weeks_remaining": None,
            "plan_end": None,
            "today_session": None,
            "today_macros": None,
            "scans_logged": 0,
            "scans_missed": [],
            "scan_due_today": False,
        }
    meta = raw.get("meta", {}) if isinstance(raw.get("meta"), dict) else {}
    program = meta.get("program")
    total_weeks = meta.get("total_weeks")
    start_date = meta.get("start_date")
    end_date = meta.get("end_date")
    # Compute current_week from start_date
    current_week = None
    weeks_remaining = None
    if isinstance(start_date, str):
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            today = datetime.now().date()
            days_in = (today - start).days
            if days_in >= 0:
                current_week = (days_in // 7) + 1
        except Exception:
            current_week = None
    if isinstance(total_weeks, int) and isinstance(current_week, int):
        weeks_remaining = max(0, total_weeks - current_week + 1)
    # Today's session
    weekdays = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    dow = weekdays[datetime.now().weekday()]
    weekly = raw.get("weekly_structure", {})
    today_session = None
    today_macros = None
    if isinstance(weekly, dict):
        day_struct = weekly.get(dow)
        if isinstance(day_struct, dict):
            session_type = day_struct.get("type")
            focus = day_struct.get("focus")
            # Look up matching session in raw["sessions"]
            sessions = raw.get("sessions", {}) if isinstance(raw.get("sessions"), dict) else {}
            session_obj = None
            for sname, sval in sessions.items():
                if isinstance(sval, dict) and sval.get("day") == dow:
                    session_obj = sval
                    break
            if session_obj:
                today_session = {
                    "name": session_obj.get("name", focus),
                    "type": session_type,
                    "exercises": session_obj.get("exercises", []),
                }
            elif session_type:
                today_session = {
                    "name": focus,
                    "type": session_type,
                    "exercises": [],
                }
            macros_block = raw.get("macros", {}) if isinstance(raw.get("macros"), dict) else {}
            if session_type and isinstance(macros_block.get(session_type), dict):
                today_macros = macros_block[session_type]
    # Scans tracking
    scans = safe_load_json(SCANS_PATH, default=[])
    if not isinstance(scans, list):
        scans = []
    scans_logged = len(scans)
    # Scan-due heuristic: if scans schedule is week-based at week starts (Mon)
    # we approximate by checking if today is Monday and current week % 1 == 0
    scan_due_today = (datetime.now().weekday() == 0)  # Monday
    # Missed scans: weeks that should have had a scan but didn't
    scans_missed: list = []
    if isinstance(current_week, int) and current_week > 1:
        scanned_weeks = set()
        for s in scans:
            if isinstance(s, dict):
                w = s.get("week")
                if isinstance(w, int):
                    scanned_weeks.add(w)
        for w in range(1, current_week + 1):
            if w not in scanned_weeks:
                # Project the date this scan was due (week start = Monday)
                if isinstance(start_date, str):
                    try:
                        start = datetime.strptime(start_date, "%Y-%m-%d").date()
                        # week N starts on day (N-1)*7 from start
                        from datetime import timedelta
                        scan_date = start + timedelta(days=(w - 1) * 7)
                        scans_missed.append(scan_date.isoformat())
                    except Exception:
                        pass
    return {
        "program": program,
        "current_week": current_week,
        "total_weeks": total_weeks,
        "weeks_remaining": weeks_remaining,
        "plan_end": end_date,
        "today_session": today_session,
        "today_macros": today_macros,
        "scans_logged": scans_logged,
        "scans_missed": scans_missed,
        "scan_due_today": scan_due_today,
    }


def build_formation() -> dict:
    """Formation log v2 sends/replies with recent samples."""
    raw = safe_load_json(FORMATION_LOG_PATH, default={})
    if not isinstance(raw, dict):
        raw = {}
    v2_sends = raw.get("v2_sends", []) if isinstance(raw.get("v2_sends"), list) else []
    v2_replies = raw.get("v2_replies", []) if isinstance(raw.get("v2_replies"), list) else []
    last_send = v2_sends[-1].get("at") if v2_sends and isinstance(v2_sends[-1], dict) else None
    last_reply = v2_replies[-1].get("at") if v2_replies and isinstance(v2_replies[-1], dict) else None
    return {
        "v2_sends_count": len(v2_sends),
        "v2_replies_count": len(v2_replies),
        "last_send_at": last_send,
        "last_reply_at": last_reply,
        "v2_sends_recent_5": v2_sends[-FORMATION_RECENT_COUNT:],
        "v2_replies_recent_5": v2_replies[-FORMATION_RECENT_COUNT:],
    }


def build_watchdog_drift() -> tuple[Any, list]:
    """Read gui_state.json watchdog + drift sections."""
    raw = safe_load_json(GUI_STATE_PATH, default={})
    if not isinstance(raw, dict):
        return None, []
    watchdog = raw.get("watchdog")
    drift = raw.get("drift")
    if not isinstance(drift, list):
        drift = []
    return watchdog, drift


def build_active_concerns() -> list:
    """Pull active_concerns from superagent_state.json (full list)."""
    raw = safe_load_json(SUPERAGENT_STATE_PATH, default={})
    if not isinstance(raw, dict):
        return []
    concerns = raw.get("active_concerns")
    if not isinstance(concerns, list):
        return []
    return concerns


def build_journal_recent() -> str:
    """Last N entries (~3000 chars cap) from superagent_journal.md."""
    text = tail_text(JOURNAL_PATH, JOURNAL_RECENT_CHAR_CAP)
    return text


def build_orchestrator_log_recent() -> str:
    return tail_lines(ORCHESTRATOR_LOG_PATH, ORCHESTRATOR_LOG_TAIL_LINES)


def build_battle_rhythm_freshness() -> dict:
    out = {}
    for name, p in BATTLE_RHYTHM_FILES.items():
        out[name] = {
            "path": str(p),
            "age_hours": safe_age_hours(p),
        }
    return out


def build_agent_freshness(task_health_all: dict) -> dict:
    """Per-agent freshness: file mtime + matching task_health record."""
    out = {}
    for agent_name, path in AGENT_OUTPUT_FILES.items():
        age = safe_age_hours(path)
        # Find matching task in task_health by partial name
        status = None
        last_run = None
        for tname, t in (task_health_all or {}).items():
            if not isinstance(t, dict):
                continue
            # Match patrol_horizon → task name contains "horizon" etc.
            stub = agent_name.replace("patrol_", "").lower()
            if stub in tname.lower():
                status = t.get("status")
                last_run = t.get("last_run")
                break
        out[agent_name] = {
            "status": status,
            "last_run": last_run,
            "age_hours": age,
        }
    return out


def build_financial_snapshot(cop: Any) -> Any:
    if not isinstance(cop, dict):
        return None
    return cop.get("financial_snapshot")


def build_family_pulse(cop: Any) -> dict:
    """Pull family pulse fields from COP + relationship intel if available."""
    out = {
        "rylan_last_1on1_iso": None,
        "harlan_bond_status": None,
        "emory_last_1on1_iso": None,
        "lindsey_recent_concern": None,
    }
    if isinstance(cop, dict):
        staff = cop.get("staff_sections", {})
        if isinstance(staff, dict):
            family_section = staff.get("S1_PERSONNEL_FAMILY") or staff.get("family") or {}
            if isinstance(family_section, dict):
                # Try to extract last_1on1 and bond per child
                for child_key in ("rylan", "harlan", "emory"):
                    child = family_section.get(child_key)
                    if isinstance(child, dict):
                        if child_key == "rylan":
                            out["rylan_last_1on1_iso"] = child.get("last_1on1") or child.get("last_1_on_1")
                        elif child_key == "harlan":
                            out["harlan_bond_status"] = child.get("bond_status") or child.get("status")
                        elif child_key == "emory":
                            out["emory_last_1on1_iso"] = child.get("last_1on1") or child.get("last_1_on_1")
                spouse = family_section.get("lindsey")
                if isinstance(spouse, dict):
                    out["lindsey_recent_concern"] = spouse.get("recent_concern") or spouse.get("note")
    # Fallback: relationship_intel.json
    rel = safe_load_json(RELATIONSHIP_INTEL_PATH, default={})
    if isinstance(rel, dict):
        bonds = rel.get("bonds", {}) or rel.get("relationships", {})
        if isinstance(bonds, dict):
            for key, slot in [("rylan", "rylan_last_1on1_iso"),
                              ("harlan", "harlan_bond_status"),
                              ("emory", "emory_last_1on1_iso")]:
                if out[slot] is None:
                    b = bonds.get(key)
                    if isinstance(b, dict):
                        out[slot] = b.get("last_1on1") or b.get("status") or b.get("bond_status")
    return out


def build_calendar_peek() -> list:
    """Next 24h events from calendar_mirror_log if present."""
    raw = safe_load_json(CALENDAR_MIRROR_PATH, default=None)
    if raw is None:
        return []
    # Schema unknown; try a few patterns
    events = []
    if isinstance(raw, dict):
        events = raw.get("events") or raw.get("next_24h") or raw.get("upcoming") or []
    elif isinstance(raw, list):
        events = raw
    if not isinstance(events, list):
        return []
    # Filter to next 24h if events have a parseable date/time
    now = datetime.now()
    cutoff_ts = now.timestamp() + 86400
    filtered = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        # Try common time keys
        t_str = ev.get("start") or ev.get("when") or ev.get("time") or ev.get("start_time")
        if isinstance(t_str, str):
            try:
                # Strip Z and try fromisoformat
                tnorm = t_str.replace("Z", "+00:00")
                t = datetime.fromisoformat(tnorm)
                if t.tzinfo is not None:
                    t_local_ts = t.timestamp()
                else:
                    t_local_ts = t.timestamp()
                if now.timestamp() <= t_local_ts <= cutoff_ts:
                    filtered.append(ev)
            except Exception:
                # If we can't parse, include it conservatively
                filtered.append(ev)
        else:
            filtered.append(ev)
    return filtered[:20]


def build_rocket_money() -> dict:
    """Find newest Rocket Money CSV in Downloads, age + status."""
    out = {"csv_age_hours": None, "csv_status": "MISSING"}
    try:
        if not ROCKET_MONEY_DIR.exists():
            return out
        candidates = []
        # Match common patterns: rocket_money_*.csv, rocketmoney_*.csv, transactions*.csv
        patterns = [r"rocket.?money", r"transactions"]
        for p in ROCKET_MONEY_DIR.iterdir():
            if not p.is_file() or p.suffix.lower() != ".csv":
                continue
            name_lower = p.name.lower()
            if any(re.search(pat, name_lower) for pat in patterns):
                candidates.append(p)
        if not candidates:
            return out
        newest = max(candidates, key=lambda x: x.stat().st_mtime)
        age = file_age_hours(newest)
        out["csv_age_hours"] = round(age, 2)
        days = age / 24
        if days < 1:
            out["csv_status"] = "GREEN"
        elif days < 3:
            out["csv_status"] = f"AMBER-{int(days)}d"
        else:
            out["csv_status"] = f"STALE-{int(days)}d"
    except Exception:
        pass
    return out


# ── Main synthesizer ────────────────────────────────────────────────
def synthesize() -> dict:
    """Build the consolidated snapshot. Pure function — returns dict.

    Schema (24 required top-level keys, always present even if degraded):
        generated_at, synthesizer_version, host_clock, today, cop, ccir,
        action_queue, pending_actions, task_health, health_vitals,
        macros_today, iron_discipline, scans, formation, watchdog, drift,
        active_concerns, previous_overwatch_brief, journal_recent,
        orchestrator_log_recent, battle_rhythm_freshness, agent_freshness,
        financial_snapshot, family_pulse, calendar_peek_24h, rocket_money,
        iss_size_bytes, input_size_targets
    """
    cop = safe_load_json(COP_PATH)
    ccir = safe_load_json(CCIR_PATH)
    iron = safe_load_json(IRON_DISCIPLINE_PATH)
    scans = safe_load_json(SCANS_PATH, default=[])
    if not isinstance(scans, list):
        scans = []
    pending_raw = safe_load_json(PENDING_PATH, default={})
    if isinstance(pending_raw, dict):
        pending_items = pending_raw.get("actions") or pending_raw.get("items") or []
    elif isinstance(pending_raw, list):
        pending_items = pending_raw
    else:
        pending_items = []
    if not isinstance(pending_items, list):
        pending_items = []

    task_health = build_task_health()
    watchdog, drift = build_watchdog_drift()

    out: dict = {
        "generated_at": utc_now_iso(),
        "synthesizer_version": SCHEMA_VERSION,
        "host_clock": local_now_iso(),
        "today": build_today(),
        "cop": cop,
        "ccir": ccir,
        "action_queue": build_action_queue(),
        "pending_actions": pending_items,
        "task_health": task_health,
        "health_vitals": build_health_vitals(),
        "macros_today": build_macros_today(iron),
        "iron_discipline": build_iron_discipline(),
        "scans": scans,
        "formation": build_formation(),
        "watchdog": watchdog,
        "drift": drift,
        "active_concerns": build_active_concerns(),
        "previous_overwatch_brief": tail_text(OVERWATCH_LATEST, PREVIOUS_OVERWATCH_CHAR_CAP),
        "journal_recent": build_journal_recent(),
        "orchestrator_log_recent": build_orchestrator_log_recent(),
        "battle_rhythm_freshness": build_battle_rhythm_freshness(),
        "agent_freshness": build_agent_freshness(task_health.get("all", {})),
        "financial_snapshot": build_financial_snapshot(cop),
        "family_pulse": build_family_pulse(cop),
        "calendar_peek_24h": build_calendar_peek(),
        "rocket_money": build_rocket_money(),
        "iss_size_bytes": None,
        "input_size_targets": "Stay under 200 KB. 250 KB OK. 500 KB push.",
    }
    return out


# ── CLI ──────────────────────────────────────────────────────────────
def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="State synthesizer for Overwatch + Prophet")
    parser.add_argument("--no-write", action="store_true",
                        help="Print JSON to stdout instead of writing file")
    parser.add_argument("--pretty", action="store_true",
                        help="Indent JSON output (default already does)")
    args = parser.parse_args(argv)

    out = synthesize()

    if args.no_write:
        print(json.dumps(out, indent=2, default=str))
        return 0

    # Ensure directory exists
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # First write
    OUT_PATH.write_text(json.dumps(out, indent=2, default=str))
    # Update self-size and rewrite (so iss_size_bytes is accurate)
    try:
        out["iss_size_bytes"] = OUT_PATH.stat().st_size
        OUT_PATH.write_text(json.dumps(out, indent=2, default=str))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
