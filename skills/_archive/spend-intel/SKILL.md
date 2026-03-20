---
name: spend-intel
description: >
  Spending Intelligence & Budget Forensics for the Owens household. Ingests
  Rocket Money transaction exports and WealthBuilder data to reveal where money
  actually goes. Tracks subscription creep, category drift, and spending that
  doesn't align with values. Triggers on: "Where's my money going",
  "Budget check", "Spending review", "Transaction analysis", "Category breakdown",
  "Subscription audit", "Spending forensics", "Budget forensics", "Monthly burn",
  "What did we spend on", "Spending trends", "Are we on budget". Standing Order #1:
  report the real number. If the spending is ugly, say so.
---

# Spending Intelligence — S4 Financial (Budget Division)

**Mission:** Know where every dollar goes. Financial-intelligence manages the macro — net worth, investments, RPED projections. This skill manages the micro — the $15K/month of take-home that either builds wealth or evaporates.

---

## Why This Exists

The Owens household has **$15,682/month in take-home** across 4 income streams. That's a formidable cash flow. But cash flow without visibility is just a river — it flows somewhere, but you don't know where until it's gone.

The financial plan estimates $7,014/month in free cash flow after expenses. That's the number that funds everything — emergency fund, debt payoff, investment acceleration. If actual spending exceeds estimates, the entire financial plan degrades silently.

**This skill is the early warning system for lifestyle creep.**

---

## Procedure

### When Invoked — Spending Review

1. **Locate transaction data:**
   - Rocket Money exports: `~/Downloads/*transactions*.csv` (find most recent)
   - WealthBuilder DB: if running, query via API (`http://localhost:4000/api/accounts/demo-user`)
   - Financial Plan budget: `~/Library/Mobile Documents/com~apple~CloudDocs/Family/Financial-Plan/Owens_Family_Financial_Plan.md`

2. **Ingest and categorize:**
   - Parse CSV transactions
   - Categorize into standard buckets (see Category Taxonomy below)
   - Flag recurring charges as subscriptions
   - Identify transactions > $200 as notable
   - Flag any unrecognized merchants

3. **Deliver Spending Intelligence Brief:**

```
━━ SPENDING INTELLIGENCE — [PERIOD] ━━

TOTAL SPEND: $XX,XXX
  vs Budget: $XX,XXX [OVER/UNDER by $X,XXX]
  vs Prior Month: [+/-X%]

TOP CATEGORIES:
  1. Housing:      $X,XXX (XX%)
  2. Food:         $X,XXX (XX%) [budget: $X,XXX]
  3. Transport:    $X,XXX (XX%)
  4. Subscriptions:$X,XXX (XX%)
  5. [etc]

NOTABLE TRANSACTIONS:
  - [Large or unusual transactions]

SUBSCRIPTION AUDIT:
  Active subscriptions: X totaling $XXX/month
  [List each with amount]
  Recommendation: [any to cut?]

SPENDING ALIGNMENT:
  [Does spending match stated values?
   Family? Health? Wealth building?
   Or is money going to things that don't matter?]

FREE CASH FLOW (Actual):
  Income:    $15,682
  Spending:  -$X,XXX
  ─────────
  Actual FCF: $X,XXX (plan: $7,014)
  Gap: [+/-$X,XXX]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Category Taxonomy

| Category | Includes | Budget Target |
|----------|----------|---------------|
| Housing | Mortgage, insurance, property tax, HOA, maintenance | $2,200 |
| Utilities | Electric, gas, water, internet, phone | $400 |
| Food | Groceries, dining out, coffee, meal delivery | $800 |
| Transport | Gas, insurance, maintenance, registration | $500 |
| Childcare | Daycare, activities, school supplies | $1,200 |
| Health | Insurance premiums, copays, supplements, gym | $300 |
| Subscriptions | Streaming, software, memberships | $200 |
| Debt Service | CC payments, student loan, auto loan | $1,500 |
| Insurance | Life, umbrella, USAA auto/home | $300 |
| Personal | Clothing, haircuts, gifts, misc | $200 |
| Savings/Invest | 401k, HSA, brokerage, emergency fund | Maximize |

Budget targets from Financial Plan. Actuals should be compared monthly.

---

## Forensic Analysis Modes

### Mode 1: Monthly Review (Standard)
- Ingest latest month's transactions
- Compare to budget categories
- Identify top 3 variances
- Flag any new subscriptions
- Calculate actual FCF vs plan

### Mode 2: Subscription Audit
- Extract all recurring transactions
- List with frequency and amount
- Flag: unused (no engagement), redundant (overlapping services), expensive (>$50/mo)
- Calculate total subscription burn rate
- Recommend cuts with estimated annual savings

### Mode 3: Trend Analysis
- Compare 3+ months of spending data
- Identify categories trending up (lifestyle creep signal)
- Identify categories trending down (possible underinvestment)
- Calculate 3-month moving average for volatile categories (food, personal)

### Mode 4: Anomaly Detection
- Flag transactions that don't match typical patterns
- Possible fraud detection (unfamiliar merchants, unusual amounts)
- Duplicate charges
- Unexpected price increases on subscriptions

---

## Integration with Financial Intelligence

This skill feeds `financial-intelligence`:
- Actual FCF → updates the gap between planned and real investment capacity
- Spending trends → informs whether the financial plan's assumptions hold
- Subscription audit → identifies recoverable dollars for debt payoff or investing

When spending analysis reveals the plan is off, flag it:
```
CROSS-DOMAIN FLAG → S4 Financial: Actual monthly spending exceeds
budget by $X,XXX. FCF degraded from $7,014 to $X,XXX. Financial
plan assumptions need revision.
```

---

## Data Freshness Requirements

| Source | Ideal Cadence | Stale After |
|--------|--------------|-------------|
| Rocket Money CSV | Monthly export | 45 days |
| WealthBuilder transactions | Auto-sync when Plaid live | 7 days |
| Budget targets | Quarterly review | 6 months |

---

## The Standard

"You can't manage what you don't measure." Every household says they want to build wealth. The ones who actually do it know where their money goes — not approximately, not "we're pretty good," but precisely. This skill turns transaction data into spending truth.

The uncomfortable version of this analysis is the only useful version.
