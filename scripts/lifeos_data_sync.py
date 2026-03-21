#!/usr/bin/env python3
"""
Life OS Data Sync — Single writer for lifeos_data.json.
Replaces financial_data_sync.py + dashboard_updater.py dual-writer pattern.

Reads from:
  - owens_future_data.json (canonical financial data)
  - cop_data.json (COP operational data: LOE, CCIR, action items, battle rhythm)
  - budget_alerts.json (budget sentinel output)
  - morning_intel.json (calendar intel)
  - task_health.json (orchestrator health)

Writes to:
  - lifeos_data.json (single consolidated file for dashboard + skills)

Also handles renames:
  - invest_intel_data.json → market_data.json (symlink)
  - recomp_data.json → health_history.json (symlink)
  - evolution_intel_data.json → evolution_data.json (symlink)

Usage:
  python3 lifeos_data_sync.py           # Full sync
  python3 lifeos_data_sync.py --check   # Validate only, don't write
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

DASHBOARD_DIR = Path.home() / "Documents" / "S6_COMMS_TECH" / "dashboard"
SCRIPTS_DIR = Path.home() / "Documents" / "S6_COMMS_TECH" / "scripts"

# Input files
FUTURE_JSON = DASHBOARD_DIR / "owens_future_data.json"
COP_JSON = DASHBOARD_DIR / "cop_data.json"
BUDGET_JSON = DASHBOARD_DIR / "budget_alerts.json"
MORNING_JSON = DASHBOARD_DIR / "morning_intel.json"
TASK_HEALTH = DASHBOARD_DIR / "task_health.json"

# Output
LIFEOS_JSON = DASHBOARD_DIR / "lifeos_data.json"

# Rename mappings (old → new, create symlinks for backward compat)
RENAMES = {
    "invest_intel_data.json": "market_data.json",
    "recomp_data.json": "health_history.json",
    "evolution_intel_data.json": "evolution_data.json",
}


def load_json(path: Path) -> dict:
    """Load JSON file, return empty dict if missing or invalid."""
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            print(f"  WARN: Could not read {path.name}: {e}")
    return {}


def build_lifeos_data() -> dict:
    """Merge source files into consolidated lifeos_data.json structure."""
    future = load_json(FUTURE_JSON)
    cop = load_json(COP_JSON)
    budget = load_json(BUDGET_JSON)
    morning = load_json(MORNING_JSON)
    health = load_json(TASK_HEALTH)

    now = datetime.now()

    # Build consolidated structure
    data = {
        "meta": {
            "version": "2.0",
            "updated": now.isoformat(timespec="seconds"),
            "updated_by": "lifeos_data_sync.py",
            "sources": {
                "financial": FUTURE_JSON.name,
                "cop": COP_JSON.name,
                "budget": BUDGET_JSON.name,
                "calendar": MORNING_JSON.name,
                "orchestrator": TASK_HEALTH.name,
            },
        },
        "commander": cop.get("commander", {
            "name": "Tory Owens",
            "role": "Associate Director, Eli Lilly",
            "rped_date": "2040-09-07",
            "age": 43,
        }),
        "domains": {
            "financial": _build_financial(future, cop, budget),
            "health": _build_health(cop),
            "family": _build_family(cop, morning),
            "career": _build_career(cop),
            "security": _build_security(cop),
        },
        "loe_scorecards": cop.get("loe_scorecards", {}),
        "ccir": cop.get("ccir", []),
        "action_items": cop.get("action_items", []),
        "action_summary": cop.get("action_summary", {}),
        "cross_domain_signals": cop.get("cross_domain_signals", []),
        "battle_rhythm": cop.get("battle_rhythm", {}),
        "orchestrator_health": _build_orchestrator_health(health),
        "staff_sections": cop.get("staff_sections", {}),
        "staff_summary": cop.get("staff_summary", {}),
        "data_freshness": cop.get("data_freshness", {}),
        "market_intelligence": cop.get("market_intelligence", {}),
    }

    return data


def _build_financial(future: dict, cop: dict, budget: dict) -> dict:
    """Build financial domain from owens_future_data + cop + budget."""
    snap = cop.get("financial_snapshot", {})

    return {
        "status": _get_loe_status(cop, "financial_independence"),
        "last_updated": future.get("last_updated", "unknown"),
        # Core snapshot
        "net_worth": future.get("net_worth", {}),
        "income": future.get("income", {}),
        "spending": future.get("spending", {}),
        "free_cash_flow": future.get("free_cash_flow", {}),
        # Retirement
        "retirement_accounts": future.get("retirement_accounts", {}),
        "pension": future.get("pension", {}),
        "retirement_projections": future.get("retirement_projections", {}),
        # Budget
        "monthly_budget": future.get("monthly_budget", {}),
        "budget_alerts": budget.get("alerts", []),
        "budget_summary": budget.get("summary", {}),
        # Milestones
        "milestones": future.get("milestones", {}),
        "blind_spots": future.get("blind_spots", []),
    }


def _build_health(cop: dict) -> dict:
    """Build health domain stub (detailed data in health_history.json)."""
    return {
        "status": _get_loe_status(cop, "health_longevity"),
        "last_updated": cop.get("data_freshness", {}).get(
            "medical_health_pull_health_recommendations", {}
        ).get("last_data", "unknown"),
        "note": "Detailed health data in health_history.json",
    }


def _build_family(cop: dict, morning: dict) -> dict:
    """Build family domain from COP + morning intel."""
    return {
        "status": _get_loe_status(cop, "family_legacy"),
        "last_updated": cop.get("data_freshness", {}).get(
            "s1_personnel_family_ops", {}
        ).get("last_data", "unknown"),
        "calendar": {
            "today": morning.get("today", []),
            "tomorrow": morning.get("tomorrow", []),
            "family_next_3_days": morning.get("family_next_3_days", []),
            "reminders": morning.get("reminders", []),
        },
    }


def _build_career(cop: dict) -> dict:
    """Build career domain from COP."""
    return {
        "status": _get_loe_status(cop, "career_advancement"),
        "last_updated": cop.get("data_freshness", {}).get(
            "s2_intelligence_personal_development", {}
        ).get("last_data", "unknown"),
    }


def _build_security(cop: dict) -> dict:
    """Build security domain from COP."""
    return {
        "status": cop.get("data_freshness", {}).get(
            "s6_communications_technology_s6_it_ops", {}
        ).get("status", "UNKNOWN"),
        "last_updated": cop.get("data_freshness", {}).get(
            "s6_communications_technology_s6_it_ops", {}
        ).get("last_data", "unknown"),
        "mcp_servers": cop.get("mcp_servers", {}),
    }


def _build_orchestrator_health(health: dict) -> dict:
    """Summarize orchestrator task health."""
    tasks = health.get("tasks", {})
    total = len(tasks)
    green = sum(1 for t in tasks.values() if t.get("status") == "GREEN")
    red = sum(1 for t in tasks.values() if t.get("status") == "RED")

    return {
        "total_tasks": total,
        "green": green,
        "red": red,
        "last_cycle": health.get("meta", {}).get("updated", "never"),
        "tasks": {
            name: {
                "status": t.get("status", "UNKNOWN"),
                "last_run": t.get("last_run"),
                "consecutive_failures": t.get("consecutive_failures", 0),
            }
            for name, t in tasks.items()
        },
    }


def _get_loe_status(cop: dict, loe_key: str) -> str:
    """Extract LOE status from cop_data."""
    return cop.get("loe_scorecards", {}).get(loe_key, {}).get("status", "UNKNOWN")


def validate(data: dict) -> list:
    """Run validation checks on consolidated data."""
    errors = []

    fin = data.get("domains", {}).get("financial", {})
    income = fin.get("income", {})
    spending = fin.get("spending", {})
    fcf = fin.get("free_cash_flow", {})

    if income and spending and fcf:
        calc_fcf = income.get("total_monthly_take_home", 0) - spending.get("monthly_cost_of_living", 0)
        actual_fcf = fcf.get("fcf_monthly", 0)
        if abs(calc_fcf - actual_fcf) > 500:
            errors.append(
                f"FCF mismatch: income-spending={calc_fcf} vs fcf_monthly={actual_fcf}"
            )

    if not data.get("ccir"):
        errors.append("No CCIR data found")

    if not data.get("action_items"):
        errors.append("No action items found")

    return errors


def setup_renames():
    """Create symlinks for renamed files (backward compatibility)."""
    for old_name, new_name in RENAMES.items():
        old_path = DASHBOARD_DIR / old_name
        new_path = DASHBOARD_DIR / new_name

        if old_path.exists() and not old_path.is_symlink():
            if new_path.exists() and not new_path.is_symlink():
                # Both exist as real files — new wins, old becomes symlink
                old_path.unlink()
                old_path.symlink_to(new_name)
                print(f"  Linked {old_name} → {new_name}")
            elif not new_path.exists():
                # Only old exists — rename it, create symlink back
                old_path.rename(new_path)
                old_path.symlink_to(new_name)
                print(f"  Renamed {old_name} → {new_name} (symlinked back)")
        elif not new_path.exists() and old_path.is_symlink():
            # Symlink exists but target missing — nothing to do
            pass


def sync(check_only=False):
    """Main sync operation."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Life OS Data Sync starting...")

    # Build consolidated data
    data = build_lifeos_data()

    # Validate
    errors = validate(data)
    if errors:
        print("  VALIDATION WARNINGS:")
        for e in errors:
            print(f"    - {e}")

    if check_only:
        print(f"  CHECK ONLY — would write {len(json.dumps(data))} bytes to lifeos_data.json")
        return True

    # Write atomically
    tmp = LIFEOS_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.rename(LIFEOS_JSON)
    size_kb = LIFEOS_JSON.stat().st_size / 1024
    print(f"  Wrote lifeos_data.json ({size_kb:.1f} KB)")

    # Handle renames
    setup_renames()

    # Also keep cop_data.json and owens_future_data.json updated for
    # backward compatibility during transition (Phase 3 dashboard will
    # read from lifeos_data.json exclusively)
    # The old financial_data_sync.py logic is preserved here:
    if FUTURE_JSON.exists() and COP_JSON.exists():
        try:
            future = json.loads(FUTURE_JSON.read_text())
            cop = json.loads(COP_JSON.read_text())

            cop["last_updated"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            cop["updated_by"] = "lifeos_data_sync.py"
            cop["cop_last_sync"] = datetime.now().strftime("%Y-%m-%d")

            cop["financial_snapshot"] = {
                "net_worth": future.get("net_worth", {}).get("total", 0),
                "assets": future.get("net_worth", {}).get("assets", 0),
                "liabilities": future.get("net_worth", {}).get("liabilities", 0),
                "monthly_income": future.get("income", {}).get("total_monthly_take_home", 0),
                "monthly_spending": future.get("spending", {}).get("monthly_cost_of_living", 0),
                "cc_debt": 0,
                "emergency_fund": future.get("milestones", {}).get("emergency_fund", {}).get("current", 0),
                "emergency_target": future.get("milestones", {}).get("emergency_fund", {}).get("target", 0),
                "years_to_rped": future.get("retirement_projections", {}).get("years_to_rped", 0),
                "fcf_monthly": future.get("free_cash_flow", {}).get("fcf_monthly", 0),
                "deployable_surplus": future.get("free_cash_flow", {}).get("deployable_surplus", 0),
                "tory_base": future.get("income", {}).get("tory_lilly_base_gross", 0),
                "lindsey_base": future.get("income", {}).get("lindsey_trimedx_base_gross", 0),
                "mortgage_rate": future.get("spending", {}).get("mortgage_rate", 0),
                "pension_monthly_full": future.get("pension", {}).get("projected_monthly_full", 0),
                "pension_monthly_joint_survivor": future.get("pension", {}).get("projected_monthly_joint_survivor", 0),
                "tory_401k_pct": future.get("retirement_accounts", {}).get("tory_401k", {}).get("contribution_pct", 0),
                "lindsey_401k_pct": future.get("retirement_accounts", {}).get("lindsey_401k", {}).get("contribution_pct", 0),
                "discretionary_fun_money": future.get("spending", {}).get("discretionary_fun_money", 0),
                "subscription_cleanup_potential": future.get("spending", {}).get("subscription_cleanup_potential", 0),
            }

            tmp_cop = COP_JSON.with_suffix(".tmp")
            tmp_cop.write_text(json.dumps(cop, indent=2))
            tmp_cop.rename(COP_JSON)
            print(f"  Updated cop_data.json (backward compat)")
        except Exception as e:
            print(f"  WARN: cop_data.json backward compat update failed: {e}")

    print(f"  Sync complete.")
    return True


if __name__ == "__main__":
    check_only = "--check" in sys.argv
    sync(check_only=check_only)
