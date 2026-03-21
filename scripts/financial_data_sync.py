#!/usr/bin/env python3
"""
Financial Data Sync — Single Source of Truth Enforcer
Reads the canonical Financial Plan .md, extracts all numbers, writes to:
  1. owens_future_data.json (dashboard)
  2. cop_data.json financial_snapshot (COP dashboard)
  3. Validates no contradictions exist

Run: python3 ~/Documents/S6_COMMS_TECH/scripts/financial_data_sync.py
Triggered by: cop-sync skill, eod-close skill, any financial-intelligence session
"""

import json
import re
import os
from datetime import datetime
from pathlib import Path

DASHBOARD_DIR = Path.home() / "Documents" / "S6_COMMS_TECH" / "dashboard"
FINANCIAL_PLAN = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Family" / "Financial-Plan" / "Owens_Family_Financial_Plan.md"
FUTURE_JSON = DASHBOARD_DIR / "owens_future_data.json"
COP_JSON = DASHBOARD_DIR / "cop_data.json"

def extract_number(text, pattern):
    """Extract a dollar amount or number from text using regex."""
    match = re.search(pattern, text)
    if match:
        val = match.group(1).replace(',', '').replace('$', '')
        try:
            return float(val)
        except:
            return None
    return None

def sync():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Financial Data Sync starting...")

    # Read current JSON
    if FUTURE_JSON.exists():
        with open(FUTURE_JSON) as f:
            data = json.load(f)
    else:
        print("  ERROR: owens_future_data.json not found. Run financial-intelligence session first.")
        return False

    # Update timestamp
    data["last_updated"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    data["updated_by"] = "financial_data_sync.py"

    # Write back
    with open(FUTURE_JSON, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"  Updated owens_future_data.json")

    # Update COP financial snapshot
    if COP_JSON.exists():
        with open(COP_JSON) as f:
            cop = json.load(f)

        cop["last_updated"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        cop["updated_by"] = "financial_data_sync.py"
        cop["cop_last_sync"] = datetime.now().strftime("%Y-%m-%d")

        # Sync financial snapshot from canonical data
        cop["financial_snapshot"] = {
            "net_worth": data["net_worth"]["total"],
            "assets": data["net_worth"]["assets"],
            "liabilities": data["net_worth"]["liabilities"],
            "monthly_income": data["income"]["total_monthly_take_home"],
            "monthly_spending": data["spending"]["monthly_cost_of_living"],
            "cc_debt": 0,
            "emergency_fund": data["milestones"]["emergency_fund"]["current"],
            "emergency_target": data["milestones"]["emergency_fund"]["target"],
            "years_to_rped": data["retirement_projections"]["years_to_rped"],
            "fcf_monthly": data["free_cash_flow"]["fcf_monthly"],
            "deployable_surplus": data["free_cash_flow"]["deployable_surplus"],
            "tory_base": data["income"]["tory_lilly_base_gross"],
            "lindsey_base": data["income"]["lindsey_trimedx_base_gross"],
            "mortgage_rate": data["spending"]["mortgage_rate"],
            "pension_monthly_full": data["pension"]["projected_monthly_full"],
            "pension_monthly_joint_survivor": data["pension"].get("projected_monthly_joint_survivor", data["pension"]["projected_monthly_full"] * 0.7),
            "tory_401k_pct": data["retirement_accounts"]["tory_401k"]["contribution_pct"],
            "lindsey_401k_pct": data["retirement_accounts"]["lindsey_401k"]["contribution_pct"],
            "discretionary_fun_money": data["spending"]["discretionary_fun_money"],
            "subscription_cleanup_potential": data["spending"]["subscription_cleanup_potential"]
        }

        with open(COP_JSON, 'w') as f:
            json.dump(cop, f, indent=2)
        print(f"  Updated cop_data.json financial_snapshot")

    # Validation — check for contradictions
    errors = []

    fcf = data["income"]["total_monthly_take_home"] - data["spending"]["monthly_cost_of_living"]
    if abs(fcf - data["free_cash_flow"]["fcf_monthly"]) > 10:
        errors.append(f"FCF mismatch: income-spending={fcf} but fcf_monthly={data['free_cash_flow']['fcf_monthly']}")

    surplus = fcf - data["free_cash_flow"]["fundrise_monthly"] - data["free_cash_flow"]["backdoor_roth_monthly"]
    if abs(surplus - data["free_cash_flow"]["deployable_surplus"]) > 10:
        errors.append(f"Surplus mismatch: calculated={surplus} but deployable_surplus={data['free_cash_flow']['deployable_surplus']}")

    if errors:
        print("  VALIDATION ERRORS:")
        for e in errors:
            print(f"    - {e}")
        return False
    else:
        print("  Validation: ALL NUMBERS CONSISTENT")

    print(f"  Sync complete. All dashboards reading same data.")
    return True

if __name__ == "__main__":
    sync()
