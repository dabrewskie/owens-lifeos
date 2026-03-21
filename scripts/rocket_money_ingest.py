#!/usr/bin/env python3
"""
rocket_money_ingest.py — Rocket Money Transaction Ingest Pipeline
Watches for new CSV exports in ~/Downloads, parses transactions,
categorizes into 50/30/20 framework, updates owens_future_data.json,
and generates transaction detail for dashboard drill-down.

Usage:
  python3 rocket_money_ingest.py                    # Process latest CSV
  python3 rocket_money_ingest.py --file path.csv    # Process specific file
  python3 rocket_money_ingest.py --watch             # Watch mode (for LaunchAgent)

Safety: Reads CSV, writes JSON. No destructive operations.
"""

import csv
import json
import os
import sys
import glob
from datetime import datetime, date
from pathlib import Path
from collections import defaultdict

DOWNLOADS = Path.home() / "Downloads"
DASHBOARD_DIR = Path.home() / "Documents" / "S6_COMMS_TECH" / "dashboard"
OUTPUT_FILE = DASHBOARD_DIR / "owens_future_data.json"
TRANSACTION_FILE = DASHBOARD_DIR / "transaction_detail.json"


def find_latest_csv():
    """Find the most recent Rocket Money CSV in Downloads."""
    patterns = [
        str(DOWNLOADS / "*transactions*.csv"),
        str(DOWNLOADS / "*rocket*.csv"),
        str(DOWNLOADS / "*Rocket*.csv"),
        str(DOWNLOADS / "export*.csv"),
    ]
    files = []
    for p in patterns:
        files.extend(glob.glob(p))

    if not files:
        return None

    # Return most recently modified
    return max(files, key=os.path.getmtime)


def parse_csv(filepath):
    """Parse Rocket Money CSV into structured transactions."""
    transactions = []
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Rocket Money CSV columns: Date, Original Date, Account, Name,
            # Custom Name, Category, Tags, Amount, Note, Recurring, Account #
            amount_str = row.get('Amount', '0').replace('$', '').replace(',', '').strip()
            try:
                amount = float(amount_str)
            except ValueError:
                continue

            date_str = row.get('Date', '') or row.get('Original Date', '')
            try:
                txn_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                try:
                    txn_date = datetime.strptime(date_str, '%m/%d/%Y').date()
                except (ValueError, TypeError):
                    continue

            transactions.append({
                'date': txn_date.isoformat(),
                'name': row.get('Custom Name') or row.get('Name', 'Unknown'),
                'original_name': row.get('Name', ''),
                'category': row.get('Category', 'Uncategorized'),
                'amount': abs(amount),
                'is_credit': amount > 0,
                'account': row.get('Account', ''),
                'recurring': row.get('Recurring', '').lower() in ('true', 'yes', '1'),
                'note': row.get('Note', ''),
                'tags': row.get('Tags', ''),
            })

    return sorted(transactions, key=lambda x: x['date'], reverse=True)


# 50/30/20 category mapping
NEEDS_CATEGORIES = {
    'needs', 'mortgage', 'rent', 'groceries', 'gas', 'insurance',
    'utilities', 'bills & utilities', 'childcare', 'medical',
    'auto & transport', 'health', 'education',
}
WANTS_CATEGORIES = {
    'wants', 'shopping', 'dining & drinks', 'entertainment & rec.',
    'personal care', 'subscriptions', 'clothing', 'hobbies',
    'entertainment', 'travel',
}
SAVINGS_CATEGORIES = {
    'savings', 'investments', 'charitable donations', 'transfer',
    'cash & checks',
}
IGNORE_CATEGORIES = {
    'income', 'internal transfer', 'reimbursement', 'ignored',
    'tax deductible',
}


def classify_5030(category):
    """Classify a Rocket Money category into 50/30/20."""
    cat_lower = category.lower().strip()
    if cat_lower in IGNORE_CATEGORIES:
        return 'ignore'
    for n in NEEDS_CATEGORIES:
        if n in cat_lower:
            return 'needs'
    for w in WANTS_CATEGORIES:
        if w in cat_lower:
            return 'wants'
    for s in SAVINGS_CATEGORIES:
        if s in cat_lower:
            return 'savings'
    # Default: if it's spending, it's a want
    return 'wants'


def analyze_month(transactions, year_month):
    """Analyze a single month's transactions."""
    month_txns = [t for t in transactions if t['date'].startswith(year_month)]

    categories = defaultdict(lambda: {'total': 0, 'count': 0, 'transactions': []})
    needs_total = 0
    wants_total = 0
    savings_total = 0
    income_total = 0

    for t in month_txns:
        if t['is_credit']:
            income_total += t['amount']
            continue

        classification = classify_5030(t['category'])
        if classification == 'ignore':
            continue

        cat = t['category']
        categories[cat]['total'] += t['amount']
        categories[cat]['count'] += 1
        categories[cat]['transactions'].append({
            'date': t['date'],
            'name': t['name'],
            'amount': t['amount'],
        })
        categories[cat]['classification'] = classification

        if classification == 'needs':
            needs_total += t['amount']
        elif classification == 'wants':
            wants_total += t['amount']
        elif classification == 'savings':
            savings_total += t['amount']

    total_spend = needs_total + wants_total + savings_total
    income = income_total if income_total > 0 else 1  # avoid div/0

    # Parse month for days calculation
    y, m = int(year_month.split('-')[0]), int(year_month.split('-')[1])
    today = date.today()
    if y == today.year and m == today.month:
        days_elapsed = today.day
        import calendar
        days_in_month = calendar.monthrange(y, m)[1]
        is_mtd = True
        projected = round(total_spend / (days_elapsed / days_in_month)) if days_elapsed > 0 else total_spend
    else:
        days_elapsed = None
        days_in_month = None
        is_mtd = False
        projected = total_spend

    # Status determination
    needs_pct = round(needs_total / income * 100) if income > 0 else 0
    wants_pct = round(wants_total / income * 100) if income > 0 else 0
    savings_pct = round((income - total_spend) / income * 100) if income > 0 else 0

    if savings_pct >= 20 and wants_pct <= 35:
        status = 'EXCELLENT' if savings_pct >= 40 else 'ON_TRACK'
    elif savings_pct >= 10:
        status = 'CAUTION'
    else:
        status = 'BLOWN'

    result = {
        'income': round(income_total),
        'needs': round(needs_total),
        'wants': round(wants_total),
        'savings_charity': round(income_total - total_spend),
        'needs_pct': needs_pct,
        'wants_pct': wants_pct,
        'savings_pct': savings_pct,
        'total_spend': round(total_spend),
        'status': status,
        'categories': {},
    }

    if is_mtd:
        result['mtd'] = True
        result['days_elapsed'] = days_elapsed
        result['days_in_month'] = days_in_month
        result['projected_full_month'] = projected

    # Category detail for drill-down
    for cat, data in sorted(categories.items(), key=lambda x: x[1]['total'], reverse=True):
        result['categories'][cat] = {
            'total': round(data['total']),
            'count': data['count'],
            'classification': data.get('classification', 'wants'),
            'transactions': sorted(data['transactions'], key=lambda x: x['amount'], reverse=True)[:20],
        }

    # Frequent spend analysis
    merchant_totals = defaultdict(lambda: {'total': 0, 'count': 0})
    for t in month_txns:
        if not t['is_credit'] and classify_5030(t['category']) != 'ignore':
            merchant_totals[t['name']]['total'] += t['amount']
            merchant_totals[t['name']]['count'] += 1

    result['frequent_spend'] = {
        name: {
            'total': round(data['total']),
            'visits': data['count'],
            'avg_per_visit': round(data['total'] / data['count']) if data['count'] > 0 else 0,
        }
        for name, data in sorted(merchant_totals.items(), key=lambda x: x[1]['total'], reverse=True)[:10]
    }

    return result


def update_dashboard_json(monthly_data, transactions):
    """Update owens_future_data.json with fresh spending data."""
    if not OUTPUT_FILE.exists():
        print(f"  WARN: {OUTPUT_FILE} not found — skipping dashboard update")
        return

    with open(OUTPUT_FILE, 'r') as f:
        data = json.load(f)

    spending = data.get('spending', {})
    ftt = spending.get('fifty_thirty_twenty', {})

    # Update months
    months = ftt.get('months', {})
    for month_key, month_data in monthly_data.items():
        # Keep existing notes if present
        existing = months.get(month_key, {})
        if 'note' in existing and 'note' not in month_data:
            month_data['note'] = existing['note']
        months[month_key] = month_data

    ftt['months'] = months
    ftt['last_pulled'] = datetime.now().isoformat()
    ftt['source'] = 'Rocket Money CSV auto-ingest'

    # Update categories array with fresh monthly data
    categories = spending.get('categories', [])
    for cat in categories:
        key = cat['key']
        new_monthly = {}
        for month_key, month_data in monthly_data.items():
            # Map category keys to Rocket Money categories
            for rm_cat, rm_data in month_data.get('categories', {}).items():
                if _category_matches(key, rm_cat):
                    new_monthly[month_key] = rm_data['total']
                    break
        if new_monthly:
            cat['monthly'].update(new_monthly)
            vals = list(cat['monthly'].values())
            cat['avg'] = round(sum(vals) / len(vals)) if vals else 0

    spending['fifty_thirty_twenty'] = ftt
    data['spending'] = spending
    data['last_updated'] = datetime.now().isoformat()

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"  Updated {OUTPUT_FILE}")


def _category_matches(our_key, rm_category):
    """Match our JSON category keys to Rocket Money category names."""
    rm_lower = rm_category.lower()
    mapping = {
        'needs': 'needs',
        'wants': 'wants',
        'charitable': 'charitable',
        'education': 'education',
        'shopping': 'shopping',
        'dining': 'dining',
        'auto_transport': 'auto',
        'bills_utilities': 'bills',
        'personal_care': 'personal care',
        'medical': 'medical',
    }
    match_term = mapping.get(our_key, our_key)
    return match_term in rm_lower


def save_transaction_detail(monthly_data):
    """Save detailed transaction data for dashboard drill-down."""
    detail = {
        'last_updated': datetime.now().isoformat(),
        'months': {}
    }

    for month_key, month_data in monthly_data.items():
        detail['months'][month_key] = {
            'categories': month_data.get('categories', {}),
            'frequent_spend': month_data.get('frequent_spend', {}),
            'summary': {
                'needs': month_data['needs'],
                'wants': month_data['wants'],
                'savings': month_data['savings_charity'],
                'total': month_data['total_spend'],
                'status': month_data['status'],
            }
        }

    with open(TRANSACTION_FILE, 'w') as f:
        json.dump(detail, f, indent=2)

    print(f"  Transaction detail saved to {TRANSACTION_FILE}")


def main():
    print("=" * 50)
    print(f"ROCKET MONEY INGEST — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    # Find CSV
    if '--file' in sys.argv:
        idx = sys.argv.index('--file')
        filepath = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
    else:
        filepath = find_latest_csv()

    if not filepath:
        print("  No Rocket Money CSV found in ~/Downloads/")
        print("  Export from: app.rocketmoney.com/transactions → Export")
        return

    print(f"  Processing: {filepath}")
    print(f"  Modified: {datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%Y-%m-%d %H:%M')}")

    # Parse
    transactions = parse_csv(filepath)
    print(f"  Parsed: {len(transactions)} transactions")

    if not transactions:
        print("  ERROR: No transactions parsed. Check CSV format.")
        return

    # Get unique months
    months = sorted(set(t['date'][:7] for t in transactions))
    print(f"  Months: {', '.join(months)}")

    # Analyze each month
    monthly_data = {}
    for month in months:
        data = analyze_month(transactions, month)
        monthly_data[month] = data
        mtd_flag = ' (MTD)' if data.get('mtd') else ''
        print(f"\n  {month}{mtd_flag}:")
        print(f"    Needs: ${data['needs']:,} ({data['needs_pct']}%)")
        print(f"    Wants: ${data['wants']:,} ({data['wants_pct']}%)")
        print(f"    Savings: ${data['savings_charity']:,} ({data['savings_pct']}%)")
        print(f"    Status: {data['status']}")
        if data.get('projected_full_month'):
            print(f"    Projected: ${data['projected_full_month']:,}")

    # Update dashboard
    update_dashboard_json(monthly_data, transactions)

    # Save transaction detail for drill-down
    save_transaction_detail(monthly_data)

    print(f"\n  Done. Dashboard updated.")


if __name__ == '__main__':
    main()
