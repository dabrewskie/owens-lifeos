# CODE SESSION: Fix "Building Our Future" Dashboard Page
**Date:** 2026-03-27
**Priority:** HIGH — financial data is 9 days stale and showing incorrect values
**Requested by:** Commander via COS Chat session

---

## PROBLEM STATEMENT

The "Building Our Future" page displays hardcoded/static financial data that has not been updated since ~March 18. It is NOT wired to `owens_future_data.json` or `lifeos_data.json` — the two JSON files that the main Life OS dashboard (`lifeos-dashboard.html`) reads from. This means every data update requires manual editing of the page HTML.

**Impact:** The page shows the family's financial picture as "EXCELLENT" when reality is $896 OVER budget. Net worth, spending, and all tracker values are stale.

---

## WHAT NEEDS TO HAPPEN

### Phase 1: Locate the source file
The "Building Our Future" page content has this structure:
- Title: "Owens Life OS — Building Our Future"
- Updated date shown: "March 16, 2026"
- Sections: Action Required checklist, What We Changed, Impact Tracker, Live Spend Tracker

Search for it:
```bash
grep -rl "Building Our Future" ~/Documents/ ~/owens-lifeos/ 2>/dev/null
grep -rl "What we changed today" ~/Documents/ ~/owens-lifeos/ 2>/dev/null
# Also check Notion — may be a Notion page
```

### Phase 2: Update ALL stale values (immediate fix)

Corrected values from 3/27 Rocket Money pull + COP:

#### Live Spend Tracker (CRITICAL — 9 days stale)
| Field | OLD (wrong) | NEW (correct) |
|-------|-------------|---------------|
| Days Elapsed | 18 / 31 | **27 / 31** |
| Last Rocket $ Export | Mar 18 | **Mar 27** |
| Verdict | EXCELLENT | **OVER BUDGET** |
| Spent So Far | $10,495 | **$13,929** |
| Budget Left | $2,538 left | **-$896 (over)** |
| Wants / Fun $$ | $3,269 (81%) | **$3,654 (91% of $4,019)** |
| Fun $$ left | $750 | **$365** |

#### Financial Values
| Field | OLD (wrong) | NEW (correct) |
|-------|-------------|---------------|
| Net Worth | ~$615,294 | **$716,807** |
| Assets | $935,537 | **$1,037,050** |
| VCX/Fundrise | $60,561 | **$162,074** |
| VCX NAV/share | $117.70 | **$314.99** |
| Portfolio | $497,837 | **$599,350** |
| Monthly FCF | $1,245 | **$3,756** |

#### Top Recurring (March MTD)
| Merchant | OLD | NEW |
|----------|-----|-----|
| Meijer | $584 (12x) | **~$1,050+ (20+x)** |
| Amazon | $624 (7x) | **$659 (8x)** |
| Lilly Cafe | $81 (7x) | **$95+ (8x)** |

### Phase 3: Refactor to read from JSON (permanent fix)

Wire the page to dynamically read from `~/Documents/S6_COMMS_TECH/dashboard/owens_future_data.json`

Key JSON paths:
```
net_worth.total → Net Worth
net_worth.assets → Assets  
income.total_monthly_take_home → Take-Home ($16,789)
spending.monthly_cost_of_living → Cost of Living ($13,033)
free_cash_flow.fcf_monthly → FCF ($3,756)
spending.categories[] → budget bars (name, budget, spent_mtd, remaining)
spending.weekly_note_3_27.march_mtd_total_rm_dashboard → Spent So Far
retirement_accounts.fundrise.current_balance → VCX value
retirement_projections.portfolio_current → Portfolio total
```

### Phase 4: Consolidate data sources

Current broken state: 3 separate data stores with no sync.
1. `owens_future_data.json` — financial plan
2. `lifeos_data.json` → `domains.financial` — dashboard source  
3. "Building Our Future" page — hardcoded

Fix: Single source (`owens_future_data.json`), others read from it.
Add sync function to `financial_data_sync.py` or `lifeos_orchestrator.py`.

---

## DATA FILES (updated 3/27 by COS)

Both JSON files corrected with VCX, net worth, spending.
Full Rocket Money CSV: `~/Documents/S4_LOGISTICS_FINANCIAL/transactions/rocket_money_full_export_2026-03-20_to_2026-03-27.csv`

## VALIDATION
- [ ] Net Worth $716,807 | VCX $162,074 | Spent $13,929
- [ ] Verdict OVER BUDGET | FCF $3,756 | Days 27/31
- [ ] Page auto-updates from JSON (no manual edits needed)
