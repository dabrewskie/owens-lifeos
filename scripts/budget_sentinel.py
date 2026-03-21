#!/usr/bin/env python3
"""
Budget Sentinel — Weekly Financial Watchdog
S4 Logistics/Financial | com.s4.budget-sentinel

Detects budget drift, subscription creep, and category overspend.
Reads owens_future_data.json, outputs budget_alerts.json.

Schedule: Monday 0700 via LaunchAgent
Author: Claude Code (Life OS automation)
Created: 2026-03-19
"""

import json
import os
import sys
from datetime import datetime, date
from pathlib import Path

# Paths
DASHBOARD_DIR = Path.home() / "Documents" / "S6_COMMS_TECH" / "dashboard"
INPUT_FILE = DASHBOARD_DIR / "owens_future_data.json"
OUTPUT_FILE = DASHBOARD_DIR / "budget_alerts.json"

# Thresholds
EARLY_BURN_PCT = 0.80       # Flag if >80% spent with >40% of month remaining
FUNMONEY_TIGHT = 500        # Flag if fun money < $500 with >7 days left
FUNMONEY_BLOWN = 0          # Flag if fun money negative
UNUSUAL_DEVIATION_PCT = 0.50  # Flag if a category deviates >50% from its typical pattern


def load_financial_data() -> dict:
    """Load the canonical financial data JSON."""
    if not INPUT_FILE.exists():
        print(f"ERROR: {INPUT_FILE} not found", file=sys.stderr)
        sys.exit(1)
    with open(INPUT_FILE, "r") as f:
        return json.load(f)


def get_month_progress() -> tuple:
    """Return (day_of_month, days_in_month, pct_elapsed, days_remaining)."""
    today = date.today()
    day = today.day
    # Get last day of month
    if today.month == 12:
        last_day = 31
    else:
        next_month = date(today.year, today.month + 1, 1)
        last_day = (next_month - __import__("datetime").timedelta(days=1)).day
    pct_elapsed = day / last_day
    days_remaining = last_day - day
    return day, last_day, pct_elapsed, days_remaining


def check_category_overspend(categories: list, pct_elapsed: float, days_remaining: int) -> list:
    """Check each spending category for budget issues."""
    alerts = []
    pct_remaining = 1.0 - pct_elapsed

    for cat in categories:
        name = cat.get("name", "Unknown")
        budget = cat.get("budget", 0)
        spent = cat.get("spent_mtd", 0)

        if budget <= 0:
            continue

        spend_pct = spent / budget

        # OVER: spent more than budget
        if spent > budget:
            alerts.append({
                "type": "OVER_BUDGET",
                "severity": "RED",
                "category": name,
                "budget": budget,
                "spent_mtd": spent,
                "overage": round(spent - budget, 2),
                "message": f"{name}: ${spent:,.0f} spent vs ${budget:,.0f} budget — OVER by ${spent - budget:,.0f}"
            })
        # EARLY BURN: >80% spent with >40% of month remaining
        elif spend_pct > EARLY_BURN_PCT and pct_remaining > 0.40:
            alerts.append({
                "type": "EARLY_BURN",
                "severity": "AMBER",
                "category": name,
                "budget": budget,
                "spent_mtd": spent,
                "spend_pct": round(spend_pct * 100, 1),
                "days_remaining": days_remaining,
                "message": f"{name}: {spend_pct:.0%} of budget burned with {days_remaining} days left"
            })

    return alerts


def check_fun_money(data: dict, days_remaining: int) -> list:
    """Check discretionary/fun money status."""
    alerts = []

    # Get fun money from monthly_budget.summary or spending.discretionary_fun_money
    fun_remaining = data.get("monthly_budget", {}).get("summary", {}).get("fun_money_remaining")
    if fun_remaining is None:
        fun_remaining = data.get("spending", {}).get("discretionary_fun_money", 0)

    # Calculate actual discretionary spent
    categories = data.get("spending", {}).get("categories", [])
    discretionary_spent = sum(
        c.get("spent_mtd", 0) for c in categories if c.get("bucket") == "wants"
    )
    wants_budget = data.get("spending", {}).get("wants_budget", 0)
    actual_remaining = wants_budget - discretionary_spent

    if actual_remaining < FUNMONEY_BLOWN:
        alerts.append({
            "type": "FUNMONEY_BLOWN",
            "severity": "RED",
            "wants_budget": wants_budget,
            "spent": discretionary_spent,
            "remaining": round(actual_remaining, 2),
            "message": f"Fun money BLOWN: ${discretionary_spent:,.0f} spent of ${wants_budget:,.0f} budget — ${abs(actual_remaining):,.0f} over"
        })
    elif actual_remaining < FUNMONEY_TIGHT and days_remaining > 7:
        alerts.append({
            "type": "FUNMONEY_TIGHT",
            "severity": "AMBER",
            "wants_budget": wants_budget,
            "spent": discretionary_spent,
            "remaining": round(actual_remaining, 2),
            "days_remaining": days_remaining,
            "message": f"Fun money TIGHT: ${actual_remaining:,.0f} left with {days_remaining} days remaining"
        })

    return alerts


def check_unusual_amounts(data: dict) -> list:
    """Look for unusual recurring charges or category anomalies using frequent_spend data."""
    alerts = []
    frequent = data.get("spending", {}).get("fifty_thirty_twenty", {}).get("frequent_spend", {})

    for merchant, spend_data in frequent.items():
        # Get historical months
        months = {k: v for k, v in spend_data.items()
                  if k.startswith(("jan", "feb")) and isinstance(v, (int, float))}
        if not months:
            continue

        avg_historical = sum(months.values()) / len(months) if months else 0
        mtd_key = [k for k in spend_data.keys() if "mtd" in k.lower()]
        if not mtd_key:
            continue
        current_mtd = spend_data.get(mtd_key[0], 0)

        if avg_historical > 0 and current_mtd > 0:
            deviation = (current_mtd - avg_historical) / avg_historical
            if deviation > UNUSUAL_DEVIATION_PCT:
                alerts.append({
                    "type": "UNUSUAL_SPEND",
                    "severity": "AMBER",
                    "merchant": merchant,
                    "current_mtd": current_mtd,
                    "historical_avg": round(avg_historical, 0),
                    "deviation_pct": round(deviation * 100, 1),
                    "message": f"{merchant}: ${current_mtd:,.0f} MTD vs ${avg_historical:,.0f} avg — {deviation:+.0%} deviation"
                })

    # Check largest purchases for anything unusual
    largest = data.get("spending", {}).get("fifty_thirty_twenty", {}).get("largest_purchases_mar", [])
    for purchase in largest:
        amount = purchase.get("amount", 0)
        if amount > 400:
            alerts.append({
                "type": "LARGE_PURCHASE",
                "severity": "INFO",
                "name": purchase.get("name", "Unknown"),
                "amount": amount,
                "date": purchase.get("date", ""),
                "category": purchase.get("category", ""),
                "message": f"Large purchase: {purchase.get('name', 'Unknown')} — ${amount:,.0f} on {purchase.get('date', '?')}"
            })

    return alerts


def build_summary(alerts: list, data: dict, day: int, days_in_month: int, days_remaining: int) -> dict:
    """Build the summary section."""
    red_count = sum(1 for a in alerts if a.get("severity") == "RED")
    amber_count = sum(1 for a in alerts if a.get("severity") == "AMBER")
    info_count = sum(1 for a in alerts if a.get("severity") == "INFO")

    # Overall status
    if red_count > 0:
        status = "RED"
        status_msg = f"{red_count} critical budget issue(s) detected"
    elif amber_count > 0:
        status = "AMBER"
        status_msg = f"{amber_count} warning(s) — monitor closely"
    else:
        status = "GREEN"
        status_msg = "All categories within budget"

    # Actuals summary
    actuals = data.get("monthly_budget", {}).get("actuals", {})
    total_spent = actuals.get("total_spent", 0)
    total_budget = data.get("spending", {}).get("monthly_cost_of_living", 0)

    return {
        "status": status,
        "status_message": status_msg,
        "red_alerts": red_count,
        "amber_alerts": amber_count,
        "info_alerts": info_count,
        "month_day": day,
        "month_days_total": days_in_month,
        "month_pct_elapsed": round(day / days_in_month * 100, 1),
        "days_remaining": days_remaining,
        "total_spent_mtd": total_spent,
        "total_budget": total_budget,
        "budget_remaining": total_budget - total_spent,
        "burn_rate_daily": round(total_spent / max(day, 1), 2),
        "projected_month_end": round((total_spent / max(day, 1)) * days_in_month, 0)
    }


def main():
    print(f"[{datetime.now().isoformat()}] Budget Sentinel starting...")

    data = load_financial_data()
    day, days_in_month, pct_elapsed, days_remaining = get_month_progress()

    print(f"  Month progress: Day {day}/{days_in_month} ({pct_elapsed:.0%} elapsed, {days_remaining} remaining)")

    # Run all checks
    all_alerts = []

    categories = data.get("spending", {}).get("categories", [])
    all_alerts.extend(check_category_overspend(categories, pct_elapsed, days_remaining))
    all_alerts.extend(check_fun_money(data, days_remaining))
    all_alerts.extend(check_unusual_amounts(data))

    # Sort: RED first, then AMBER, then INFO
    severity_order = {"RED": 0, "AMBER": 1, "INFO": 2}
    all_alerts.sort(key=lambda a: severity_order.get(a.get("severity", "INFO"), 3))

    # Build output
    summary = build_summary(all_alerts, data, day, days_in_month, days_remaining)

    output = {
        "generated_at": datetime.now().isoformat(),
        "generated_by": "budget_sentinel.py",
        "data_source": str(INPUT_FILE),
        "summary": summary,
        "alerts": all_alerts
    }

    # Write output
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"  Status: {summary['status']} — {summary['status_message']}")
    print(f"  Alerts: {len(all_alerts)} total ({summary['red_alerts']} RED, {summary['amber_alerts']} AMBER, {summary['info_alerts']} INFO)")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"[{datetime.now().isoformat()}] Budget Sentinel complete.")


if __name__ == "__main__":
    main()
