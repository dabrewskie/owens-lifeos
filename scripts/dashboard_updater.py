#!/usr/bin/env python3
"""
Dashboard Updater — Parses COP.md and writes cop_data.json for the Life OS dashboard.
Triggered by PostToolUse hook when COP.md is edited/written.

Robust: if parsing fails at any stage, logs the error and exits cleanly.
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

COP_PATH = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/COP.md"
)
DASHBOARD_JSON = os.path.expanduser(
    "~/Documents/S6_COMMS_TECH/dashboard/cop_data.json"
)
LOG_FILE = os.path.expanduser(
    "~/Documents/S6_COMMS_TECH/scripts/cleanup_logs/dashboard_updater.log"
)


def log(msg: str):
    """Append a timestamped message to the log file."""
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass  # logging failure should never crash the updater


def parse_staff_statuses(text: str) -> dict:
    """Extract staff section statuses from COP.md."""
    statuses = {}
    # Pattern: ### SectionName\n**Last Updated:** ...\n**Status:** COLOR
    pattern = re.compile(
        r"###\s+(.+?)\n"
        r"\*\*Last Updated:\*\*\s*(.+?)\n"
        r"\*\*Status:\*\*\s*(GREEN|AMBER|RED)",
        re.MULTILINE,
    )
    for match in pattern.finditer(text):
        section_name = match.group(1).strip()
        last_updated = match.group(2).strip()
        status = match.group(3).strip()
        # Create a clean key from section name
        key = re.sub(r"[^a-z0-9]+", "_", section_name.lower()).strip("_")
        statuses[key] = {
            "label": section_name,
            "status": status,
            "last_updated": last_updated,
        }
    return statuses


def parse_ccir(text: str) -> list:
    """Extract CCIR items from the CCIR table."""
    items = []
    # Find the CCIR section
    ccir_match = re.search(
        r"## COMMANDER'S CRITICAL INFORMATION REQUIREMENTS.*?\n\|.*?\n\|[-\s|]+\n(.*?)(?=\n---|\n##)",
        text,
        re.DOTALL,
    )
    if not ccir_match:
        return items
    table_body = ccir_match.group(1)
    for row in table_body.strip().split("\n"):
        cols = [c.strip() for c in row.split("|") if c.strip()]
        if len(cols) >= 5:
            items.append({
                "number": cols[0],
                "description": cols[1],
                "trigger": cols[2],
                "owner": cols[3],
                "status": cols[4],
            })
    return items


def parse_action_items(text: str) -> list:
    """Extract action items from the Action Items table."""
    items = []
    action_match = re.search(
        r"## ACTION ITEMS.*?\n\|.*?\n\|[-\s|]+\n(.*?)(?=\n---|\n##)",
        text,
        re.DOTALL,
    )
    if not action_match:
        return items
    table_body = action_match.group(1)
    for row in table_body.strip().split("\n"):
        cols = [c.strip() for c in row.split("|") if c.strip()]
        if len(cols) >= 6:
            items.append({
                "number": cols[0],
                "action": cols[1],
                "owner": cols[2],
                "due": cols[3],
                "status": cols[4],
                "depends_on": cols[5] if len(cols) > 5 else "",
            })
    return items


def parse_last_sync(text: str) -> str:
    """Extract the Last Full Sync date."""
    match = re.search(r"\*\*Last Full Sync:\*\*\s*(.+)", text)
    return match.group(1).strip() if match else "Unknown"


def parse_cross_domain_signals(text: str) -> list:
    """Extract cross-domain signal matrix entries."""
    signals = []
    sig_match = re.search(
        r"## CROSS-DOMAIN SIGNAL MATRIX.*?\n\|.*?\n\|[-\s|]+\n(.*?)(?=\n---|\n##)",
        text,
        re.DOTALL,
    )
    if not sig_match:
        return signals
    table_body = sig_match.group(1)
    for row in table_body.strip().split("\n"):
        cols = [c.strip() for c in row.split("|") if c.strip()]
        if len(cols) >= 5:
            signals.append({
                "signal": cols[0],
                "from": cols[1],
                "to": cols[2],
                "status": cols[3],
                "action": cols[4],
            })
    return signals


def compute_data_freshness(staff: dict) -> dict:
    """Derive data freshness indicators from staff section update dates."""
    freshness = {}
    today = datetime.now().date()
    for key, info in staff.items():
        last = info.get("last_updated", "")
        try:
            dt = datetime.strptime(last, "%Y-%m-%d").date()
            days_old = (today - dt).days
            if days_old <= 7:
                fstatus = "GREEN"
            elif days_old <= 14:
                fstatus = "AMBER"
            else:
                fstatus = "RED"
            freshness[key] = {
                "last_data": last,
                "days_old": days_old,
                "status": fstatus,
            }
        except (ValueError, TypeError):
            freshness[key] = {
                "last_data": last,
                "days_old": None,
                "status": "UNKNOWN",
            }
    return freshness


def build_dashboard_data(text: str) -> dict:
    """Build the full dashboard JSON from COP.md content."""
    staff = parse_staff_statuses(text)
    ccir = parse_ccir(text)
    actions = parse_action_items(text)
    last_sync = parse_last_sync(text)
    signals = parse_cross_domain_signals(text)
    freshness = compute_data_freshness(staff)

    # Compute summary counts
    status_counts = {"GREEN": 0, "AMBER": 0, "RED": 0}
    for info in staff.values():
        s = info.get("status", "")
        if s in status_counts:
            status_counts[s] += 1

    action_summary = {
        "total": len(actions),
        "complete": sum(1 for a in actions if "COMPLETE" in a.get("status", "").upper()),
        "overdue": sum(1 for a in actions if "OVERDUE" in a.get("status", "").upper()),
        "pending": sum(
            1 for a in actions
            if "OVERDUE" not in a.get("status", "").upper()
            and "COMPLETE" not in a.get("status", "").upper()
        ),
    }

    # Try to preserve existing dashboard fields that COP.md doesn't contain
    existing = {}
    try:
        with open(DASHBOARD_JSON, "r") as f:
            existing = json.load(f)
    except Exception:
        pass

    # Build output, preserving fields COP doesn't own
    data = {
        "last_updated": datetime.now().isoformat(timespec="seconds"),
        "updated_by": "PostToolUse Hook — dashboard_updater.py",
        "cop_last_sync": last_sync,
    }

    # Preserve commander, loe_scorecards, financial_snapshot, battle_rhythm,
    # skills/agents/hooks/scheduled_tasks inventories, mcp_servers from existing
    for preserve_key in [
        "commander", "loe_scorecards", "financial_snapshot", "battle_rhythm",
        "skills_inventory", "agents_inventory", "hooks_inventory",
        "scheduled_tasks_inventory", "mcp_servers",
    ]:
        if preserve_key in existing:
            data[preserve_key] = existing[preserve_key]

    # Update fields derived from COP.md
    data["staff_sections"] = staff
    data["staff_summary"] = status_counts
    data["ccir"] = ccir
    data["action_items"] = actions
    data["action_summary"] = action_summary
    data["cross_domain_signals"] = signals
    data["data_freshness"] = freshness

    # Update the last_updated timestamp at top level
    data["last_updated"] = datetime.now().isoformat(timespec="seconds")

    return data


def main():
    try:
        if not os.path.exists(COP_PATH):
            log(f"COP.md not found at {COP_PATH}")
            return

        with open(COP_PATH, "r") as f:
            text = f.read()

        if not text.strip():
            log("COP.md is empty — skipping update")
            return

        data = build_dashboard_data(text)

        os.makedirs(os.path.dirname(DASHBOARD_JSON), exist_ok=True)
        with open(DASHBOARD_JSON, "w") as f:
            json.dump(data, f, indent=2)

        log(f"Dashboard updated: {len(data.get('staff_sections', {}))} sections, "
            f"{len(data.get('action_items', []))} actions, "
            f"{len(data.get('ccir', []))} CCIRs")

    except Exception as e:
        log(f"ERROR: {type(e).__name__}: {e}")
        # Exit cleanly — never crash the hook
        return


def inject_market_intelligence():
    """Read invest_intel_data.json and inject market intelligence into cop_data.json."""
    invest_intel_path = os.path.expanduser(
        "~/Documents/S6_COMMS_TECH/dashboard/invest_intel_data.json"
    )
    try:
        if not os.path.exists(invest_intel_path):
            log("invest_intel_data.json not found — skipping market intelligence injection")
            return

        if not os.path.exists(DASHBOARD_JSON):
            log("cop_data.json not found — skipping market intelligence injection")
            return

        with open(invest_intel_path, "r") as f:
            invest_data = json.load(f)

        with open(DASHBOARD_JSON, "r") as f:
            cop_data = json.load(f)

        # Extract market intelligence fields
        market_intel = {
            "market_status": invest_data.get("market_status", "UNKNOWN"),
            "macro_regime": invest_data.get("macro_regime", {}).get("regime", "UNKNOWN"),
            "macro_regime_confidence_pct": invest_data.get("macro_regime", {}).get("confidence_pct", 0),
            "invest_intel_last_updated": invest_data.get("last_updated", "UNKNOWN"),
        }

        cop_data["market_intelligence"] = market_intel
        cop_data["last_updated"] = datetime.now().isoformat(timespec="seconds")

        with open(DASHBOARD_JSON, "w") as f:
            json.dump(cop_data, f, indent=2)

        log(f"Market intelligence injected: {market_intel['market_status']} / "
            f"{market_intel['macro_regime']} ({market_intel['macro_regime_confidence_pct']}%)")

    except Exception as e:
        log(f"ERROR injecting market intelligence: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
    inject_market_intelligence()
