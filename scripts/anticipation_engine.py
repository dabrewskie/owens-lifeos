#!/usr/bin/env python3
"""
Anticipation Engine — Predicts what Tory needs before he asks.

Runs at SessionStart (after memory_expander.py). Pure file I/O, no API calls.
Completes in <15 seconds.

Three phases:
  1. State Snapshot (5s) — read JSONs on disk
  2. Pattern Detection (5s) — 15 deterministic rules
  3. Brief Generation (2s) — output ONLY when findings exist

Usage:
  python3 anticipation_engine.py          # Normal run (stdout brief)
  python3 anticipation_engine.py --test   # Verbose test with all rules
  python3 anticipation_engine.py --json   # Output pending_actions.json only
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

from remediation_tracker import track_findings

# ── Paths ─────────────────────────────────────────────────────────────
DASHBOARD_DIR = Path.home() / "Documents" / "S6_COMMS_TECH" / "dashboard"
SCRIPTS_DIR = Path.home() / "Documents" / "S6_COMMS_TECH" / "scripts"
ICLOUD = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
HEALTH_DIR = Path.home() / "Library" / "Mobile Documents" / "iCloud~com~ifunography~HealthExport" / "Documents" / "Health Metrics"
WORKOUT_DIR = Path.home() / "Library" / "Mobile Documents" / "iCloud~com~ifunography~HealthExport" / "Documents" / "Health Metrics Medications"
HISTORY_FILE = ICLOUD / "TORY_OWENS_HISTORY.md"
COP_FILE = ICLOUD / "COP.md"

LIFEOS_JSON = DASHBOARD_DIR / "lifeos_data.json"
TASK_HEALTH = DASHBOARD_DIR / "task_health.json"
HEALTH_HISTORY = DASHBOARD_DIR / "health_history.json"
MARKET_DATA = DASHBOARD_DIR / "market_data.json"
PENDING_ACTIONS = DASHBOARD_DIR / "pending_actions.json"

# Battle rhythm output files
BR_FILES = {
    "morning-sweep": ICLOUD / "morning-sweep-latest.md",
    "eod-close": ICLOUD / "eod-close-latest.md",
    "cop-sync": ICLOUD / "cop-sync-latest.md",
    "data-ingest": ICLOUD / "data-ingest-latest.md",
}

VERBOSE = "--test" in sys.argv
NOW = datetime.now()


# ── Phase 1: State Snapshot ───────────────────────────────────────────

def load_json_safe(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {}


def load_state() -> dict:
    """Read all state from disk."""
    state = {
        "lifeos": load_json_safe(LIFEOS_JSON),
        "task_health": load_json_safe(TASK_HEALTH),
        "health_history": load_json_safe(HEALTH_HISTORY),
        "market": load_json_safe(MARKET_DATA),
        "now": NOW,
        "weekday": NOW.strftime("%A"),
        "hour": NOW.hour,
    }

    # Battle rhythm file ages
    state["br_ages"] = {}
    for name, path in BR_FILES.items():
        if path.exists():
            age_h = (NOW.timestamp() - path.stat().st_mtime) / 3600
            state["br_ages"][name] = round(age_h, 1)
        else:
            state["br_ages"][name] = None  # missing

    # COP age
    if COP_FILE.exists():
        state["cop_age_h"] = round(
            (NOW.timestamp() - COP_FILE.stat().st_mtime) / 3600, 1
        )
    else:
        state["cop_age_h"] = None

    # Latest health export
    state["latest_health"] = _find_latest_health()

    return state


def _find_latest_health() -> dict:
    """Find the most recent health export file and extract key metrics."""
    if not HEALTH_DIR.exists():
        return {"available": False}

    # Only consider files with YYYY-MM-DD format
    files = sorted(
        [f for f in HEALTH_DIR.glob("HealthAutoExport-*.json")
         if len(f.stem.replace("HealthAutoExport-", "")) == 10],
        reverse=True
    )
    if not files:
        return {"available": False}

    latest = files[0]
    age_h = (NOW.timestamp() - latest.stat().st_mtime) / 3600

    result = {"available": True, "file": latest.name, "age_h": round(age_h, 1)}

    try:
        data = json.loads(latest.read_text())
        metrics = data.get("data", {}).get("metrics", [])
        for m in metrics:
            name = m.get("name", "")
            vals = m.get("data", [])
            if not vals:
                continue
            if name == "weight_body_mass":
                result["weight"] = vals[-1].get("qty")
            elif name == "body_fat_percentage":
                result["body_fat"] = vals[-1].get("qty")
            elif name == "protein":
                result["protein"] = sum(v.get("qty", 0) for v in vals)
            elif name == "dietary_energy":
                result["calories"] = sum(v.get("qty", 0) for v in vals)
            elif name == "heart_rate_variability":
                result["hrv"] = round(sum(v.get("qty", 0) for v in vals) / len(vals), 1)
            elif name == "sleep_analysis":
                # Use totalSleep field (already in hours), NOT qty
                entry = vals[-1]
                total_sleep = entry.get("totalSleep", 0)
                result["sleep_hours"] = round(total_sleep, 1) if total_sleep else None
                result["deep_sleep"] = round(entry.get("deep", 0), 1)
    except Exception:
        pass

    # Workout data from .hae files in AutoSync/Workouts
    try:
        hae_dir = WORKOUT_DIR.parent / "AutoSync" / "Workouts"
        if hae_dir.exists():
            cutoff = (NOW - timedelta(days=14)).strftime("%Y%m%d")
            training_days = set()
            total_sessions = 0
            for hae_file in hae_dir.glob("*.hae"):
                parts = hae_file.stem.split("_")
                for part in parts:
                    if len(part) == 8 and part.isdigit() and part >= cutoff:
                        training_days.add(part)
                        total_sessions += 1
                        break
            result["training_days_14d"] = len(training_days)
            result["training_sessions_14d"] = total_sessions
    except Exception:
        pass

    return result


# ── Phase 2: Pattern Detection ────────────────────────────────────────

def detect_patterns(state: dict) -> list:
    """Run 15 deterministic rules. Returns list of findings."""
    findings = []

    # ── Calendar Rules ────────────────────────────────────────────────
    _check_calendar_prep(state, findings)
    _check_overdue_actions(state, findings)

    # ── Financial Rules ───────────────────────────────────────────────
    _check_efund_milestone(state, findings)
    _check_pay_schedule(state, findings)

    # ── Health Rules ──────────────────────────────────────────────────
    _check_protein_streak(state, findings)
    _check_calorie_deficit(state, findings)
    _check_health_data_gap(state, findings)
    _check_overtraining(state, findings)

    # ── System Rules ──────────────────────────────────────────────────
    _check_battle_rhythm(state, findings)
    _check_task_failures(state, findings)
    _check_task_never_succeeds(state, findings)
    _check_high_failure_rate(state, findings)
    _check_standing_patrol_coverage(state, findings)
    _check_alert_outbox(state, findings)
    _check_cop_staleness(state, findings)
    _check_evolve_timeout_risk(state, findings)
    _check_overwatch_input_size(state, findings)             # NEW 2026-05-01 EE-Cycle11
    _check_claude_version_integrity(findings)
    _check_evolution_engine_dark(state, findings)       # NEW 2026-04-21
    _check_systemic_task_cliff(state, findings)         # NEW 2026-04-21
    _check_infrastructure_service_down(state, findings) # NEW 2026-04-21
    _check_api_infrastructure_errors(state, findings)   # NEW 2026-04-22
    _check_overwatch_coverage_gap(state, findings)      # NEW 2026-04-22
    _check_auth_cascade_signature(state, findings)      # NEW 2026-04-24
    _check_phantom_task_entries(state, findings)        # NEW 2026-04-24
    _check_subscription_cap_exhaustion(state, findings) # NEW 2026-04-29

    # ── Cross-Domain Rules ────────────────────────────────────────────
    _check_stress_cascade(state, findings)
    _check_mask_indicators(state, findings)
    _check_substance_recovery(findings)

    return findings


def _check_calendar_prep(state, findings):
    """Events needing prep within 48h."""
    lifeos = state["lifeos"]
    actions = lifeos.get("action_items", [])
    for a in actions:
        due = a.get("due", "")
        if not due or due in ("TBD", "ASAP"):
            continue
        try:
            due_dt = datetime.strptime(due, "%Y-%m-%d")
            days_until = (due_dt - NOW).days
            status = a.get("status", "")
            if 0 <= days_until <= 2 and "COMPLETE" not in status:
                findings.append({
                    "category": "NEXT_48H",
                    "message": f"{a['action']} — due {due} ({days_until}d)",
                    "priority": "HIGH" if days_until == 0 else "MEDIUM",
                })
        except ValueError:
            pass


def _check_overdue_actions(state, findings):
    """Count overdue action items."""
    actions = state["lifeos"].get("action_items", [])
    overdue = [
        a for a in actions
        if "OVERDUE" in a.get("status", "") or "⚠️" in a.get("status", "")
    ]
    if len(overdue) >= 3:
        items = ", ".join(
            a.get("action", "?")[:40] for a in overdue[:3]
        )
        findings.append({
            "category": "PATTERN",
            "message": f"{len(overdue)} action items overdue: {items}",
            "priority": "HIGH",
        })


def _check_efund_milestone(state, findings):
    """E-fund approaching milestone."""
    fin = state["lifeos"].get("domains", {}).get("financial", {})
    milestones = fin.get("milestones", {})
    efund = milestones.get("emergency_fund", {})
    current = efund.get("current", 0)
    target = efund.get("target", 47286)

    if current and target:
        pct = current / target * 100
        # Alert at 25%, 50%, 75% milestones
        for milestone in [25, 50, 75]:
            if pct >= milestone - 2 and pct <= milestone + 2:
                findings.append({
                    "category": "PATTERN",
                    "message": f"E-fund at {pct:.0f}% (${current:,.0f}/${target:,.0f}) — approaching {milestone}% milestone",
                    "priority": "LOW",
                })


def _check_pay_schedule(state, findings):
    """Flag 3-paycheck months approaching."""
    # Biweekly pay — 3-paycheck months happen ~every 3 months
    # Check if this month has 3 Fridays that are pay dates
    # Simplified: just check if day of month > 28 and it's a Friday
    if NOW.weekday() == 4 and NOW.day >= 28:
        findings.append({
            "category": "NEXT_48H",
            "message": "3-paycheck week this month — extra $2,638 (Tory) routes to E-fund",
            "priority": "MEDIUM",
        })


def _check_protein_streak(state, findings):
    """Protein below target for 3+ days."""
    health = state.get("latest_health", {})
    protein = health.get("protein")
    if protein and protein < 170:  # 80% of 210g target
        findings.append({
            "category": "PATTERN",
            "message": f"Protein at {protein:.0f}g yesterday (target 210g, {protein/210*100:.0f}%)",
            "priority": "MEDIUM",
        })


def _check_calorie_deficit(state, findings):
    """Calories significantly below target."""
    health = state.get("latest_health", {})
    calories = health.get("calories")
    if calories and calories < 1600:
        findings.append({
            "category": "PATTERN",
            "message": f"Calories at {calories:.0f} yesterday (target 2,000) — under-eating impairs recovery",
            "priority": "HIGH",
        })


def _check_health_data_gap(state, findings):
    """Health data export gap > 3 days."""
    health = state.get("latest_health", {})
    if not health.get("available"):
        findings.append({
            "category": "SYSTEM",
            "message": "No health export data found",
            "priority": "HIGH",
        })
    elif health.get("age_h", 0) > 72:
        days = health["age_h"] / 24
        findings.append({
            "category": "SYSTEM",
            "message": f"Health data is {days:.0f} days old — export stale",
            "priority": "HIGH" if days > 7 else "MEDIUM",
        })


def _check_battle_rhythm(state, findings):
    """Battle rhythm output staleness."""
    br = state.get("br_ages", {})
    stale = []
    for name, age_h in br.items():
        if age_h is None:
            stale.append(f"{name} (missing)")
        elif age_h > 48:
            stale.append(f"{name} ({age_h/24:.0f}d)")

    total = len(br)
    current = total - len(stale)
    pct = current / total * 100 if total else 0

    if stale:
        findings.append({
            "category": "SYSTEM",
            "message": f"Battle rhythm {current}/{total} ({pct:.0f}%): stale — {', '.join(stale)}",
            "priority": "HIGH" if pct < 50 else "MEDIUM",
        })


def _check_task_failures(state, findings):
    """Orchestrator task failures."""
    tasks = state.get("task_health", {}).get("tasks", {})
    failed = [
        name for name, t in tasks.items()
        if t.get("consecutive_failures", 0) >= 2
        and not t.get("archived")  # Skip archived/phantom tasks
        and (t.get("status") or "").upper() not in ("RETIRED", "ARCHIVED")  # EE-Cycle11
    ]
    if failed:
        findings.append({
            "category": "SYSTEM",
            "message": f"Orchestrator: {len(failed)} tasks failing — {', '.join(failed)}",
            "priority": "HIGH",
        })

    # Exclude UNKNOWN and ARCHIVED tasks from health count
    known_tasks = {n: t for n, t in tasks.items()
                   if t.get("status") not in ("UNKNOWN", "ARCHIVED")}
    total_known = len(known_tasks)
    green = sum(1 for t in known_tasks.values() if t.get("status") == "GREEN")
    unknown_count = sum(1 for t in tasks.values() if t.get("status") == "UNKNOWN")
    archived_count = sum(1 for t in tasks.values() if t.get("archived"))
    if total_known > 0:
        note = f" ({unknown_count} UNKNOWN/new)" if unknown_count > 0 else ""
        if archived_count > 0:
            note += f" ({archived_count} ARCHIVED/retired)"
        findings.append({
            "category": "SYSTEM",
            "message": f"Orchestrator: {green}/{total_known} known tasks GREEN{note}",
            "priority": "LOW" if green == total_known else "MEDIUM",
        })


def _check_task_never_succeeds(state, findings):
    """Tasks that have run 3+ times with 0 successes — structural failure, not transient."""
    tasks = state.get("task_health", {}).get("tasks", {})
    broken = []
    for name, t in tasks.items():
        status = (t.get("status") or "").upper()
        if t.get("archived") or status in ("RETIRED", "ARCHIVED"):  # EE-Cycle11: skip retired
            continue
        runs = t.get("total_runs", 0)
        failures = t.get("total_failures", 0)
        last_success = t.get("last_success")
        if runs >= 3 and failures == runs and not last_success:
            broken.append(name)
    if broken:
        findings.append({
            "category": "SYSTEM",
            "message": f"Tasks with 100% failure rate (never succeeded): {', '.join(broken)} — needs architecture fix, not restart",
            "priority": "HIGH",
        })


def _check_standing_patrol_coverage(state, findings):
    """Standing patrol outputs missing or >24h stale — Overwatch running blind.

    2026-04-30 Evolution Cycle 10: Skip outputs from RETIRED tasks.
    patrol_horizon (→life_horizons), patrol_relationship (→relationship_intel),
    patrol_opportunity (→opportunities) were retired 2026-04-23 per Commander
    directive. Their output files are intentionally stale — not a coverage gap.
    Cross-check task_health status before flagging staleness.
    """
    dashboard = Path.home() / "Documents" / "S6_COMMS_TECH" / "dashboard"
    # Maps output filename → (display agent name, task_health key for retirement check)
    patrol_files = {
        "life_horizons.json": ("life-horizon-scanner", "patrol_horizon"),
        "relationship_intel.json": ("relationship-intel", "patrol_relationship"),
        "opportunities.json": ("opportunity-hunter", "patrol_opportunity"),
        "accountability_report.json": ("accountability-tracker", None),
        "pattern_prophet_output.json": ("pattern-prophet", None),
    }
    tasks = state.get("task_health", {}).get("tasks", {})
    missing = []
    stale = []
    skipped_retired = []
    now = datetime.now()
    for fname, (agent, task_key) in patrol_files.items():
        # Skip outputs from retired tasks — intentionally dark, not a gap
        if task_key:
            task_info = tasks.get(task_key, {})
            if task_info.get("status") in ("RETIRED", "ARCHIVED") or task_info.get("archived"):
                skipped_retired.append(agent)
                continue
        fpath = dashboard / fname
        if not fpath.exists():
            missing.append(f"{agent} (missing)")
        else:
            age_h = (now.timestamp() - fpath.stat().st_mtime) / 3600
            if age_h > 24:
                stale.append(f"{agent} ({age_h:.0f}h)")

    issues = missing + stale
    active_count = 5 - len(skipped_retired)
    if len(issues) >= 2:
        findings.append({
            "category": "SYSTEM",
            "message": f"Standing patrol coverage gap: {len(issues)}/{active_count} outputs missing or stale — {', '.join(issues[:3])}",
            "priority": "HIGH" if len(missing) >= 3 else "MEDIUM",
        })
    elif len(issues) == 1:
        findings.append({
            "category": "SYSTEM",
            "message": f"Standing patrol gap: {issues[0]}",
            "priority": "LOW",
        })


def _check_evolve_timeout_risk(state, findings):
    """Warn if evolution engine is approaching its runner timeout budget.

    Evolution engine grows over time as more data accumulates. If last_duration
    exceeds 80% of the 900s runner timeout (720s), flag it before it starts failing.
    Threshold: 720s = 80% of 900s runner timeout.
    Updated 2026-04-22: runner increased from 750→900s (empirical 724s = 96.6% utilization).
    """
    tasks = state.get("task_health", {}).get("tasks", {})
    evolve = tasks.get("evolve_daily", {})
    last_duration = evolve.get("last_duration", 0)
    if last_duration and last_duration > 720:
        findings.append({
            "category": "SYSTEM",
            "message": f"evolve_daily approaching timeout: {last_duration:.0f}s (>80% of 900s runner budget) — increase timeout or reduce scope",
            "priority": "MEDIUM",
        })


def _check_overwatch_input_size(state, findings):
    """Monitor overwatch_input.json size to prevent overwatch_morning TIMEOUT.

    EE-Cycle11 2026-05-01: Observed 150KB file at ~3.3s/KB token rate → 495.5s empirical
    duration, exceeding the 480s runner TIMEOUT (upgraded to 600s same cycle).
    Cap reduction in state_synthesizer targets ~115KB → ~380s steady state.
    This rule fires if file grows back toward the danger zone despite caps.

    Thresholds (calibrated post-EE-Cycle11 cap reduction, target state = ~115KB):
      MEDIUM → >130KB (cap drift detected, approaching danger zone — review synthesizer)
      HIGH   → >145KB (TIMEOUT risk: at 3.3s/KB this maps to ~479s, near 600s runner limit)
    """
    import os
    try:
        dashboard = os.path.expanduser("~/Documents/S6_COMMS_TECH/dashboard")
        input_path = os.path.join(dashboard, "overwatch_input.json")
        if not os.path.exists(input_path):
            return
        size_kb = os.path.getsize(input_path) / 1024
        if size_kb > 145:
            findings.append({
                "category": "SYSTEM",
                "message": (
                    f"overwatch_input.json is {size_kb:.0f}KB — HIGH TIMEOUT RISK. "
                    f"At ~3.3s/KB, this maps to ~{size_kb*3.3:.0f}s inference time (runner limit 600s). "
                    f"Review state_synthesizer.py ACTION_QUEUE_ACTIVE_CAP / ORCHESTRATOR_LOG_TAIL_LINES."
                ),
                "priority": "HIGH",
            })
        elif size_kb > 130:
            findings.append({
                "category": "SYSTEM",
                "message": (
                    f"overwatch_input.json is {size_kb:.0f}KB (growing toward 145KB TIMEOUT threshold). "
                    f"Target is ~115KB. Check state_synthesizer.py cap constants — ACTION_QUEUE_ACTIVE_CAP={12}, "
                    f"ORCHESTRATOR_LOG_TAIL_LINES={100}."
                ),
                "priority": "MEDIUM",
            })
    except Exception:
        pass


def _check_alert_outbox(state, findings):
    """Alert outbox check — queued unsent iMessages from daemon context.

    s6_alert.py uses an outbox queue (alert_outbox.json) when launchd processes
    can't deliver via AppleScript GUI. If messages are queued here, the Commander
    has NOT been notified of those events. Flag immediately — this is a Commander
    awareness gap, not just a system issue.

    Added 2026-03-24: root cause of 2-day iMessage blackout (QRF repair qrf_001).
    """
    outbox_path = Path.home() / "Documents" / "S6_COMMS_TECH" / "dashboard" / "alert_outbox.json"
    if not outbox_path.exists():
        return
    try:
        with open(outbox_path) as f:
            outbox = json.load(f)
        pending = outbox if isinstance(outbox, list) else outbox.get("pending", [])
        count = len(pending)
        if count > 0:
            oldest = pending[0].get("timestamp", "unknown") if pending else "unknown"
            findings.append({
                "category": "SYSTEM",
                "message": f"Alert outbox has {count} queued unsent iMessage(s) — Commander NOT notified of these events. Oldest: {oldest}",
                "priority": "HIGH",
            })
    except Exception:
        pass  # If outbox is malformed, don't crash the engine


def _check_high_failure_rate(state, findings):
    """Flag tasks with >40% failure rate and 5+ total runs — chronic degradation pattern.

    Distinct from _check_task_never_succeeds (100% failure, structural).
    This catches tasks that sometimes work but fail too often to be reliable.
    Threshold: 5+ runs (enough data), >40% failure rate (not just random variance).

    Added 2026-03-24: battle_cop_sync showed 55% failure rate (5/9 runs).
    """
    tasks = state.get("task_health", {}).get("tasks", {})
    degraded = []
    for name, t in tasks.items():
        status = (t.get("status") or "").upper()
        if t.get("archived") or status in ("RETIRED", "ARCHIVED"):  # Skip retired/archived tasks
            continue
        runs = t.get("total_runs", 0)
        failures = t.get("total_failures", 0)
        if runs >= 5 and failures > 0:
            rate = failures / runs
            if rate > 0.40:
                degraded.append(f"{name} ({failures}/{runs} = {rate:.0%})")
    if degraded:
        findings.append({
            "category": "SYSTEM",
            "message": f"High failure rate tasks (>40%, 5+ runs): {', '.join(degraded)} — investigate root cause",
            "priority": "MEDIUM",
        })


def _check_cop_staleness(state, findings):
    """COP.md staleness."""
    age = state.get("cop_age_h")
    if age and age > 72:
        findings.append({
            "category": "SYSTEM",
            "message": f"COP.md is {age/24:.0f} days old — needs refresh",
            "priority": "HIGH",
        })


def _check_stress_cascade(state, findings):
    """Cross-domain stress: health down + multiple overdue items."""
    health = state.get("latest_health", {})
    actions = state["lifeos"].get("action_items", [])
    overdue_count = sum(1 for a in actions if "OVERDUE" in a.get("status", ""))

    # Health stress indicators
    health_stress = False
    calories = health.get("calories", 2000)
    protein = health.get("protein", 210)
    if calories and calories < 1600:
        health_stress = True
    if protein and protein < 150:
        health_stress = True

    if health_stress and overdue_count >= 3:
        findings.append({
            "category": "PATTERN",
            "message": "Stress cascade: health metrics declining + multiple overdue items — system overload signal",
            "priority": "HIGH",
        })


def _check_overtraining(state, findings):
    """Overtraining risk: high training frequency + declining HRV/recovery."""
    health = state.get("latest_health", {})
    training_days = health.get("training_days_14d", 0)
    hrv = health.get("hrv")
    deep = health.get("deep_sleep")

    if training_days >= 12:
        risk_signals = []
        if hrv is not None and hrv < 40:
            risk_signals.append(f"HRV {hrv}ms (<40)")
        if deep is not None and deep < 1.0:
            risk_signals.append(f"deep sleep {deep}h (<1.0)")

        if risk_signals:
            findings.append({
                "category": "PATTERN",
                "message": f"Overtraining risk: {training_days}/14 training days + {' + '.join(risk_signals)} — recovery insufficient for volume",
                "priority": "HIGH",
            })
        elif training_days >= 13:
            findings.append({
                "category": "PATTERN",
                "message": f"Training volume very high: {training_days}/14 days — ensure at least 2 rest days per week",
                "priority": "MEDIUM",
            })


def _check_substance_recovery(findings):
    """Flag if substances logged yesterday evening — impacts today's recovery context."""
    substance_file = DASHBOARD_DIR / "substance_tracker.json"
    if not substance_file.exists():
        return
    try:
        data = json.loads(substance_file.read_text())
        entries = data.get("entries", [])
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        evening_entries = [
            e for e in entries
            if e.get("date") == yesterday and e.get("time", "00:00") >= "17:00"
        ]
        if evening_entries:
            substances = sorted({e["substance"] for e in evening_entries})  # sorted() ensures deterministic order for stable finding IDs
            findings.append({
                "category": "PATTERN",
                "message": f"Substance logged yesterday evening ({', '.join(substances)}) — may reduce deep sleep quality today",
                "priority": "MEDIUM",
                "suggested_action": "Monitor recovery score. Adjust training intensity if sleep score low.",
            })
    except Exception:
        pass


def _check_claude_version_integrity(findings):
    """
    Detect claude CLI version changes that may break headless tasks.
    qrf_003 (2026-03-25): v2.1.83 auto-updated silently, broke all tasks for 6h.
    Reads claude_version_state.json written by claude_version_guard.py.
    Fires when: (a) a rollback has occurred since last check, or (b) version changed
    but guard hasn't run yet (based on symlink mtime vs state file mtime).
    """
    import os
    state_file = DASHBOARD_DIR / "claude_version_state.json"
    claude_symlink = Path(os.path.expanduser("~/.local/bin/claude"))

    # If guard hasn't run yet (state file missing), detect raw symlink change
    if not state_file.exists():
        try:
            target = os.readlink(str(claude_symlink))
            active = Path(target).name
            # Flag that version guard hasn't been bootstrapped
            findings.append({
                "category": "SYSTEM",
                "message": f"Claude version guard not yet bootstrapped — active version {active} unverified. Run claude_version_guard.py manually to initialize.",
                "priority": "MEDIUM",
            })
        except (OSError, FileNotFoundError):
            pass
        return

    try:
        state = json.loads(state_file.read_text())
    except Exception:
        return

    rollbacks = state.get("rollbacks", [])
    known_good = state.get("known_good_version")
    active = state.get("active_version")

    # Check for recent rollback (within last 24h)
    if rollbacks:
        latest_rollback = rollbacks[-1]
        try:
            rollback_time = datetime.fromisoformat(latest_rollback["timestamp"])
            age_hours = (datetime.now() - rollback_time).total_seconds() / 3600
            if age_hours < 24:
                findings.append({
                    "category": "SYSTEM",
                    "message": (
                        f"Claude CLI rollback executed {age_hours:.1f}h ago: "
                        f"{latest_rollback['broken_version']} → {latest_rollback['rolled_back_to']} "
                        f"(smoke test failed). Monitor headless task recovery."
                    ),
                    "priority": "HIGH",
                })
        except (ValueError, KeyError):
            pass

    # Check if active version != known_good (unresolved version drift)
    if active and known_good and active != known_good:
        findings.append({
            "category": "SYSTEM",
            "message": f"Claude CLI version mismatch: active={active}, known-good={known_good}. Guard may need to run.",
            "priority": "MEDIUM",
        })


def _check_evolution_engine_dark(state, findings):
    """Evolution engine failure — uniquely dangerous: it IS the self-correction mechanism.

    When evolve_daily goes dark, system failures accumulate with no detection or repair.
    Every day without evolution is a day of uncorrected drift — calibration gaps widen,
    new failure classes go unclassified, and the anticipation engine gets no new rules.

    This rule fires when evolve_daily has consecutive failures, even just 1. The
    severity escalates based on how long it has been dark — a 7-day gap is CRITICAL
    because a full week of patterns have been missed.

    Added 2026-04-21 (Cycle 6): evolve_daily was dark for 25 days (last_success
    2026-03-26 → 2026-04-21). No evolution ran during a period when 14+ tasks broke,
    the Development Portal went offline, and Formation Intelligence went dark for 27d.
    The self-correction mechanism must have its own escalation path.
    """
    tasks = state.get("task_health", {}).get("tasks", {})
    evolve = tasks.get("evolve_daily", {})
    cf = evolve.get("consecutive_failures", 0)
    last_success = evolve.get("last_success")

    if cf < 1:
        return

    if last_success:
        try:
            last_dt = datetime.fromisoformat(last_success)
            days_dark = (datetime.now() - last_dt).days
            priority = "HIGH" if days_dark < 7 else "HIGH"  # Always HIGH — escalate to CRITICAL in message
            severity_label = "CRITICAL" if days_dark >= 7 else "HIGH"
            findings.append({
                "category": "SYSTEM",
                "message": (
                    f"{severity_label}: Evolution engine DARK {days_dark}d (last success {last_success[:10]}) "
                    f"— {cf} consecutive failures. Self-correction offline. "
                    f"Pattern drift accumulating. Manual override required."
                ),
                "priority": "HIGH",
            })
        except ValueError:
            findings.append({
                "category": "SYSTEM",
                "message": f"Evolution engine failing ({cf} consecutive) — self-correction mechanism offline.",
                "priority": "HIGH",
            })
    else:
        findings.append({
            "category": "SYSTEM",
            "message": "Evolution engine has NEVER succeeded — self-correction mechanism never operational.",
            "priority": "HIGH",
        })


def _check_systemic_task_cliff(state, findings):
    """Detect mass simultaneous task failure — systemic regression event.

    When 8+ currently-RED tasks all share the same last_success date (within
    a 24-hour window), this is NOT random variance — it's a systemic event:
    a CLI regression, API auth change, model deprecation, or infrastructure failure.
    Systemic events require QRF investigation, not individual task restarts.

    Precedents:
    - qrf_003 (2026-03-25): v2.1.83 regression — 7 tasks in 6 hours
    - The 3/27 Cliff (2026-03-27 → 2026-04-21): 14 tasks, 25+ days

    Added 2026-04-21 (Cycle 6): The 3/27 cliff was not caught because evolve_daily
    was itself broken. This rule runs in the anticipation engine (every 15 min)
    so it fires within hours of a cliff event, not weeks later.
    """
    from collections import Counter
    tasks = state.get("task_health", {}).get("tasks", {})
    red_tasks = {n: t for n, t in tasks.items() if t.get("status") == "RED"}

    if len(red_tasks) < 8:
        return

    # Group RED tasks by their last_success date
    date_counts: Counter = Counter()
    for name, t in red_tasks.items():
        ls = t.get("last_success")
        if ls:
            date_counts[ls[:10]] += 1  # YYYY-MM-DD

    if not date_counts:
        return

    most_common_date, count = date_counts.most_common(1)[0]
    if count >= 8:
        # Calculate how long ago this cliff was
        try:
            cliff_dt = datetime.strptime(most_common_date, "%Y-%m-%d")
            days_since = (datetime.now() - cliff_dt).days
            findings.append({
                "category": "SYSTEM",
                "message": (
                    f"SYSTEMIC REGRESSION DETECTED: {count} tasks all last succeeded {most_common_date} "
                    f"({days_since}d ago) and have been failing since. "
                    f"This is a systemic event — QRF investigation required, not individual restarts."
                ),
                "priority": "HIGH",
            })
        except ValueError:
            findings.append({
                "category": "SYSTEM",
                "message": f"SYSTEMIC REGRESSION: {count} RED tasks all share last_success {most_common_date} — QRF required.",
                "priority": "HIGH",
            })


def _check_infrastructure_service_down(state, findings):
    """Detect persistent infrastructure service failures indicating a stopped service.

    mastery_decay consistently failing with 'Connection refused' on port 8083
    indicates the Development Portal service is stopped — not a transient network
    issue. Connection refused is immediate (no TCP handshake) and 100% consistent
    when the service is down. This requires manual intervention to restart.

    Unlike transient failures, a service that has been down for days will not
    self-heal. After 2+ consecutive Connection Refused failures, flag as HIGH
    with an explicit restart instruction.

    Added 2026-04-21 (Cycle 6): Development Portal offline 26+ days.
    mastery_decay logged 3 consecutive Connection Refused failures with
    last_success 2026-03-26. No self-healing path — requires Commander action.
    """
    tasks = state.get("task_health", {}).get("tasks", {})
    mastery = tasks.get("mastery_decay", {})
    cf = mastery.get("consecutive_failures", 0)
    last_error = mastery.get("last_error", "") or ""

    # Skip if task has been archived (removed from orchestrator)
    if mastery.get("archived"):
        return

    if cf >= 2 and "Connection refused" in last_error:
        last_success = mastery.get("last_success") or "never"
        days_down = ""
        if last_success != "never":
            try:
                ls_dt = datetime.fromisoformat(last_success)
                days = (datetime.now() - ls_dt).days
                days_down = f" ({days}d down)"
            except ValueError:
                pass
        findings.append({
            "category": "SYSTEM",
            "message": (
                f"Development Portal (port 8083) OFFLINE{days_down} — "
                f"mastery_decay {cf}x Connection Refused. Last success: {last_success[:10]}. "
                f"Manual action required: restart dev portal service or disable mastery_decay task."
            ),
            "priority": "HIGH",
        })


def _check_api_infrastructure_errors(state, findings):
    """Detect tasks failing with API infrastructure errors distinct from timeout or auth failures.

    Two error signatures warrant specific detection:
    1. Rate limit (HTTP 429) — input tokens/minute exceeded. Requires prompt reduction
       or rescheduling to off-peak hours. Cannot be fixed by increasing runner TIMEOUT.
    2. Stream idle timeout — "partial response received" / connection dropped mid-stream.
       Indicates API instability or extremely long generation. Retry logic or prompt
       chunking is the correct fix.

    These are DIFFERENT from:
    - exit code 1 at 5s (auth window failure) → reschedule or retry
    - TIMEOUT at runner limit → increase timeout budget
    - Connection refused → service down (see _check_infrastructure_service_down)

    Added 2026-04-22 (Cycle 7): patrol_prophet failed twice in one day with:
    - 2026-04-21 19:26: 429 rate limit (30,000 input tokens/min exceeded)
    - 2026-04-22 20:05: Stream idle timeout (partial response)
    Neither of these is a timeout calibration issue — different diagnosis, different fix.
    """
    tasks = state.get("task_health", {}).get("tasks", {})
    rate_limited = []
    stream_timeout = []

    for task_name, task in tasks.items():
        err = (task.get("last_error") or "").lower()
        cf = task.get("consecutive_failures", 0)
        if cf < 1:
            continue
        if "rate limit" in err or "429" in err or "input tokens per minute" in err:
            rate_limited.append(task_name)
        if "stream idle timeout" in err or "partial response" in err:
            stream_timeout.append(task_name)

    if rate_limited:
        findings.append({
            "category": "SYSTEM",
            "message": (
                f"API rate limit (429) on: {', '.join(rate_limited)} — "
                f"input token budget exceeded. Fix: reduce prompt size or reschedule to off-peak hours. "
                f"NOT a timeout calibration issue."
            ),
            "priority": "HIGH",
        })
    if stream_timeout:
        findings.append({
            "category": "SYSTEM",
            "message": (
                f"Stream idle timeout on: {', '.join(stream_timeout)} — "
                f"API connection dropped mid-generation. Fix: add retry logic or reduce generation scope. "
                f"Transient but recurring if prompt is too large."
            ),
            "priority": "MEDIUM",
        })


def _check_overwatch_coverage_gap(state, findings):
    """Detect when Overwatch evening brief was missed today.

    Overwatch is the highest-leverage intelligence synthesis in the system.
    Missing an evening run means the Commander ends the day without a synthesized
    situation report and without tomorrow's preparation intel.

    overwatch_morning and overwatch_midday are somewhat redundant — if one misses,
    the other partially compensates. But overwatch_evening is unique: it reads the
    accountability tracker (1900 run) and pattern_prophet (1930 run) to synthesize
    the day's outcomes. No other agent reads that data.

    This rule fires MEDIUM when overwatch_evening hasn't run today. Escalates to HIGH
    if it also missed yesterday (two consecutive missed evenings).

    Added 2026-04-22 (Cycle 7): overwatch_evening MISSED today (4/22) per pulse_status.
    No existing rule flagged this — the _check_battle_rhythm and _check_task_failures
    rules use rolling consecutive_failures, which resets to 0 on any success. A task
    can have consecutive_failures=0 while still missing today's scheduled window.
    """
    from datetime import date
    tasks = state.get("task_health", {}).get("tasks", {})
    overwatch_evening = tasks.get("overwatch_evening", {})
    last_success = overwatch_evening.get("last_success")

    if not last_success:
        return  # Never ran — covered by _check_task_never_succeeds

    try:
        last_dt = datetime.fromisoformat(last_success)
        today = datetime.now().date()
        days_since = (today - last_dt.date()).days

        if days_since >= 2:
            findings.append({
                "category": "SYSTEM",
                "message": (
                    f"HIGH: overwatch_evening missed {days_since} consecutive days "
                    f"(last success: {last_success[:10]}). Commander missing evening synthesis + "
                    f"accountability/prophet integration. Investigate scheduling or runner issue."
                ),
                "priority": "HIGH",
            })
        elif days_since == 1:
            # Only flag if it's past 21:00 (the window should have fired by now)
            if datetime.now().hour >= 21:
                findings.append({
                    "category": "SYSTEM",
                    "message": (
                        f"overwatch_evening NOT YET RUN today (last success: {last_success[:10]}). "
                        f"Expected ~20:00. May still fire — monitor. Commander missing EOD synthesis."
                    ),
                    "priority": "MEDIUM",
                })
    except ValueError:
        pass


def _check_mask_indicators(state, findings):
    """1SG mask detection — high performance + declining health."""
    health = state.get("latest_health", {})
    br = state.get("br_ages", {})

    # If battle rhythm is highly active but health is declining
    active_br = sum(1 for age in br.values() if age is not None and age < 48)
    health_declining = False

    calories = health.get("calories", 2000)
    if calories and calories < 1500:
        health_declining = True

    if active_br >= 3 and health_declining:
        findings.append({
            "category": "PATTERN",
            "message": "Guardian Protocol: system running hard but body not fueled — the mask may be up",
            "priority": "HIGH",
        })


def _check_auth_cascade_signature(state, findings):
    """Detect auth cascade: multiple claude-agent tasks failing fast (<15s) simultaneously.

    When 3+ agent tasks fail in 3–15 seconds with RED status, this is NOT independent
    task failures — it is an auth cascade. The signature is the claude CLI auth handshake
    failing before any real work begins (3–5s overhead) or the runner's preflight check
    catching an auth misconfiguration (5–10s).

    Distinguishes from legitimate fast failures:
    - mastery_decay 0.1s: Connection Refused (service down, not auth)
    - formation_ingest 0.1s: Quick Python script, not a claude agent
    - stock_analyst 171s: Real execution failure, not auth

    Root causes this rule catches:
    - --bare flag without ANTHROPIC_API_KEY (qrf_005, 2026-04-24 config_drift)
    - OAuth token expired or revoked
    - ANTHROPIC_API_KEY unset by another process (cost_sentinel behavior)

    Added 2026-04-24 (Cycle 8): Auth cascade on 4/23 took 11+ hours to diagnose
    because the existing _check_task_failures rule counted failures but didn't
    distinguish fast-fail auth cascade from individual task failures. This rule
    fires within 15 minutes of the cascade starting.
    """
    # Tasks known to invoke claude -p (have outer timeout > 60s)
    CLAUDE_AGENT_TASKS = {
        'battle_morning', 'battle_cop_sync', 'overwatch_morning', 'overwatch_midday',
        'overwatch_evening', 'evolve_daily', 'evolve_weekly', 'patrol_pulse_0600',
        'patrol_pulse_1400', 'patrol_pulse_2200', 'patrol_pulse_0200', 'patrol_pulse_1000',
        'patrol_pulse_1800', 'patrol_accountability', 'patrol_opportunity',
        'patrol_relationship', 'patrol_prophet', 'patrol_network', 'patrol_shield',
        'patrol_legacy', 'patrol_ecosystem', 'battle_eod',
    }
    tasks = state.get("task_health", {}).get("tasks", {})
    fast_fail_tasks = []
    for name, info in tasks.items():
        if name not in CLAUDE_AGENT_TASKS:
            continue
        if info.get("status") != "RED":
            continue
        if info.get("archived"):
            continue
        duration = info.get("last_duration")
        if duration is not None and 2.5 <= duration <= 15.0:
            fast_fail_tasks.append((name, duration))

    if len(fast_fail_tasks) >= 3:
        task_list = ", ".join(f"{n}({d:.0f}s)" for n, d in sorted(fast_fail_tasks))
        findings.append({
            "category": "SYSTEM",
            "message": (
                f"AUTH CASCADE SIGNATURE: {len(fast_fail_tasks)} agent tasks failing fast (2.5–15s): "
                f"{task_list} — likely auth failure (--bare+no-API-key, expired OAuth, or ANTHROPIC_API_KEY "
                f"unset). Check battle_rhythm_runner.sh CMD_ARGS and ANTHROPIC_API_KEY env var. "
                f"See qrf_005 (2026-04-24) for precedent."
            ),
            "priority": "HIGH",
            "suggested_action": (
                "grep 'CMD_ARGS\\|ANTHROPIC_API_KEY' ~/Documents/S6_COMMS_TECH/scripts/battle_rhythm_runner.sh "
                "then: python3 ~/Documents/S6_COMMS_TECH/scripts/battle_rhythm_runner.sh pulse"
            ),
        })


def _check_phantom_task_entries(state, findings):
    """Detect tasks accumulating RED failures in task_health.json that are no longer running.

    When a task is removed from the orchestrator's TASKS dict (retired, replaced, or
    disabled), its entry remains in task_health.json with increasing consecutive_failures.
    These 'phantom tasks' pollute system health metrics and generate false alarms in
    other rules (_check_task_failures, _check_high_failure_rate, _check_systemic_task_cliff).

    Signature: 5+ consecutive failures AND last_run > 7 days ago AND status != ARCHIVED.

    The fix is to archive these entries in task_health.json (status = ARCHIVED,
    archived = True). This preserves audit history while clearing them from health metrics.

    Added 2026-04-24 (Cycle 8): evolution_sweep, mastery_decay, patrol_horizon were
    removed from the orchestrator TASKS dict but remained as RED entries in task_health.json.
    They were generating false alarms in _check_task_failures (inflating RED count by 3)
    and in _check_infrastructure_service_down (mastery_decay).
    """
    tasks = state.get("task_health", {}).get("tasks", {})
    phantom_tasks = []
    now = datetime.now()

    for name, info in tasks.items():
        if info.get("archived"):
            continue
        if info.get("status") not in ("RED", "UNKNOWN"):
            continue
        cf = info.get("consecutive_failures", 0)
        if cf < 5:
            continue
        last_run_str = info.get("last_run") or ""
        if not last_run_str:
            continue
        try:
            last_run = datetime.fromisoformat(last_run_str)
            days_since = (now - last_run).days
            if days_since >= 7:
                phantom_tasks.append((name, cf, days_since))
        except ValueError:
            pass

    if phantom_tasks:
        task_list = ", ".join(f"{n}(fail={c}, {d}d ago)" for n, c, d in phantom_tasks)
        findings.append({
            "category": "SYSTEM",
            "message": (
                f"PHANTOM TASKS in task_health.json: {len(phantom_tasks)} task(s) with 5+ consecutive "
                f"failures not run in 7+ days — likely removed from orchestrator: {task_list}. "
                f"Archive in task_health.json (status=ARCHIVED) to clear false alarms."
            ),
            "priority": "MEDIUM",
            "suggested_action": "Evolution Engine: set status=ARCHIVED + archived=True in task_health.json for these tasks.",
        })


def _check_subscription_cap_exhaustion(state, findings):
    """Detect recurring nightly Max subscription cap exhaustion.

    The Max subscription plan has a rolling daily usage cap. When exhausted,
    Claude CLI returns "You've hit your limit · resets HH:MMpm". This is
    structurally different from API 429 (input token rate limit) — it's a
    total-volume cap, not a per-minute rate limit.

    Signature in battle_rhythm.log (two formats):
      - New (post QRF_012a 2026-04-29): "RATE_LIMIT <mode>: Max subscription cap exhausted"
      - Legacy (pre-fix): "FAIL <mode> (exit 1): You've hit your limit"

    Pattern to detect: 2+ of the last 3 calendar nights had rate-limit failures
    on evening tasks. This means structural scheduling is wrong, not transient noise.

    Fix: shift affected tasks past the empirical reset window (23:10-23:50 ET).
    The evolve_daily schedule was shifted to 00:00 on 2026-04-29 — this rule
    monitors whether the fix holds (should go silent after the schedule change).

    Added 2026-04-29 (Cycle 9): 2 consecutive nights confirmed (4/27, 4/28).
    """
    log_file = SCRIPTS_DIR / "cleanup_logs" / "battle_rhythm.log"
    if not log_file.exists():
        return

    try:
        lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return

    # Scan last 500 lines — covers ~3 days of battle rhythm activity
    recent = lines[-500:]
    now = datetime.now()

    nights_with_cap_hit = set()
    for line in recent:
        if "rate_limit" in line.lower() or "you've hit your limit" in line.lower():
            # Extract date from log timestamp [YYYY-MM-DD HH:MM:SS]
            try:
                date_str = line.split("]")[0].strip("[").split(" ")[0]
                hit_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                # Only count nights within the last 7 days
                days_ago = (now.date() - hit_date).days
                if 0 <= days_ago <= 6:
                    nights_with_cap_hit.add(hit_date)
            except (ValueError, IndexError):
                continue

    if len(nights_with_cap_hit) >= 2:
        sorted_nights = sorted(nights_with_cap_hit)
        nights_str = ", ".join(d.strftime("%m/%d") for d in sorted_nights)
        findings.append({
            "category": "SYSTEM",
            "message": (
                f"Max subscription cap hit on {len(nights_with_cap_hit)} of last 7 nights ({nights_str}). "
                f"Evening tasks (battle_eod, patrol_pulse_2200, evolve_daily) exhausted quota before 23:00 reset. "
                f"evolve_daily rescheduled to 00:00 (post-reset) on 2026-04-29. "
                f"Monitor: rule should go silent after schedule fix takes effect."
            ),
            "priority": "HIGH" if len(nights_with_cap_hit) >= 3 else "MEDIUM",
        })


# ── Phase 3: Brief Generation ────────────────────────────────────────

def generate_brief(findings: list, state: dict) -> str:
    """Generate brief output. Silent when all clear."""
    if not findings:
        return ""

    lines = ["=== ANTICIPATION ENGINE ==="]

    # NEXT 48H
    next48 = [f for f in findings if f["category"] == "NEXT_48H"]
    if next48:
        lines.append("NEXT 48H:")
        for f in next48:
            lines.append(f"  {'!!' if f['priority']=='HIGH' else '-'} {f['message']}")

    # PATTERNS
    patterns = [f for f in findings if f["category"] == "PATTERN"]
    if patterns:
        lines.append("PATTERNS:")
        for f in patterns:
            lines.append(f"  {'!!' if f['priority']=='HIGH' else '-'} {f['message']}")

    # SYSTEM
    system = [f for f in findings if f["category"] == "SYSTEM"]
    if system:
        system_msgs = [f["message"] for f in system]
        lines.append("SYSTEM: " + " | ".join(system_msgs))

    lines.append("===")
    return "\n".join(lines)


def write_pending_actions(findings: list):
    """Write pending_actions.json for Claude to auto-execute."""
    actions = []
    for f in findings:
        if f["priority"] in ("HIGH", "MEDIUM"):
            actions.append({
                "category": f["category"],
                "message": f["message"],
                "priority": f["priority"],
                "suggested_action": _suggest_action(f),
                "timestamp": NOW.isoformat(timespec="seconds"),
            })

    data = {
        "generated": NOW.isoformat(timespec="seconds"),
        "count": len(actions),
        "actions": actions,
    }

    tmp = PENDING_ACTIONS.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.rename(PENDING_ACTIONS)


def _suggest_action(finding: dict) -> str:
    """Suggest an auto-executable action."""
    msg = finding["message"].lower()
    if "cop.md" in msg and "stale" in msg:
        return "Run cop-sync to refresh COP"
    if "battle rhythm" in msg:
        return "Check orchestrator health and skill output persistence"
    if "health data" in msg and "stale" in msg:
        return "Check Health Auto Export app on iPhone"
    if "protein" in msg:
        return "Log meals — prioritize high-protein options"
    if "calorie" in msg:
        return "Increase meal volume — add protein shake or snack"
    if "overdue" in msg:
        return "Review and close or reschedule overdue items"
    if "orchestrator" in msg and "failing" in msg:
        return "Run: python3 lifeos_orchestrator.py --status"
    return "Review and take action"


# ── Remediation Tracking ─────────────────────────────────────────────

def _make_finding_id(finding: dict) -> str:
    """Derive a stable ID from category + message prefix."""
    cat = finding.get("category", "UNKNOWN").lower()
    msg = finding.get("message", "")
    # Take first 60 chars, lowercase, replace non-alphanum with underscores
    slug = re.sub(r"[^a-z0-9]+", "_", msg[:60].lower()).strip("_")
    return f"{cat}_{slug}"


def _convert_for_tracker(findings: list) -> list:
    """Convert anticipation engine findings to remediation_tracker format."""
    result = []
    for f in findings:
        result.append({
            "id": _make_finding_id(f),
            "severity": f.get("priority", "MEDIUM"),
            "subject": f"{f['category']}: {f['message'][:80]}",
            "detail": f["message"],
        })
    return result


# ── Main ──────────────────────────────────────────────────────────────

def main():
    # Phase 1: State Snapshot
    state = load_state()

    if VERBOSE:
        print("=== ANTICIPATION ENGINE (TEST MODE) ===")
        print(f"Time: {NOW.strftime('%Y-%m-%d %H:%M')} ({state['weekday']})")
        print(f"Health data: {'available' if state['latest_health'].get('available') else 'MISSING'}")
        print(f"COP age: {state.get('cop_age_h', '?')}h")
        print(f"BR ages: {state['br_ages']}")
        print()

    # Phase 2: Pattern Detection
    findings = detect_patterns(state)

    if VERBOSE:
        print(f"Findings: {len(findings)}")
        for f in findings:
            print(f"  [{f['priority']}] {f['category']}: {f['message']}")
        print()

    # Phase 3: Brief Generation
    brief = generate_brief(findings, state)
    if brief:
        print(brief)

    # Write pending actions
    if "--json" in sys.argv or findings:
        write_pending_actions(findings)

    # Remediation tracking — convert findings to tracker format and record
    tracker_findings = _convert_for_tracker(findings)
    track_findings("anticipation_engine", tracker_findings)

    if VERBOSE and not brief:
        print("ALL CLEAR — no findings to report.")


if __name__ == "__main__":
    main()
