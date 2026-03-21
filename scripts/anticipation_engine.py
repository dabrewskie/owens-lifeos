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
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────
DASHBOARD_DIR = Path.home() / "Documents" / "S6_COMMS_TECH" / "dashboard"
SCRIPTS_DIR = Path.home() / "Documents" / "S6_COMMS_TECH" / "scripts"
ICLOUD = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
HEALTH_DIR = Path.home() / "Library" / "Mobile Documents" / "iCloud~com~ifunography~HealthExport" / "Documents" / "Health Metrics"
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

    files = sorted(HEALTH_DIR.glob("HealthAutoExport-*.json"), reverse=True)
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
            latest_val = vals[-1].get("qty", vals[-1].get("value", None))
            if name == "weight_body_mass":
                result["weight"] = latest_val
            elif name == "body_fat_percentage":
                result["body_fat"] = latest_val
            elif name == "dietary_protein":
                result["protein"] = latest_val
            elif name == "dietary_energy":
                result["calories"] = latest_val
            elif name == "sleep_analysis":
                # Sum sleep stages
                total_sleep = sum(
                    v.get("qty", v.get("value", 0))
                    for v in vals
                    if v.get("source", "") != ""
                )
                result["sleep_hours"] = round(total_sleep, 1) if total_sleep else None
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

    # ── System Rules ──────────────────────────────────────────────────
    _check_battle_rhythm(state, findings)
    _check_task_failures(state, findings)
    _check_cop_staleness(state, findings)

    # ── Cross-Domain Rules ────────────────────────────────────────────
    _check_stress_cascade(state, findings)
    _check_mask_indicators(state, findings)

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
    ]
    if failed:
        findings.append({
            "category": "SYSTEM",
            "message": f"Orchestrator: {len(failed)} tasks failing — {', '.join(failed)}",
            "priority": "HIGH",
        })

    total = len(tasks)
    green = sum(1 for t in tasks.values() if t.get("status") == "GREEN")
    if total > 0:
        findings.append({
            "category": "SYSTEM",
            "message": f"Orchestrator: {green}/{total} tasks GREEN",
            "priority": "LOW" if green == total else "MEDIUM",
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

    if VERBOSE and not brief:
        print("ALL CLEAR — no findings to report.")


if __name__ == "__main__":
    main()
