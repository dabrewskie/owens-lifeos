---
name: money
description: >
  Financial check, Money update, Net worth, Investment check, Budget review,
  Retirement update, Market brief, Portfolio review, Spending review,
  Transaction analysis, Tax check, Tax optimization, Estate plan, Will,
  Beneficiaries, Property update, Rental check, Mortgage check.
  Unified financial intelligence across all money domains — investments,
  spending, taxes, estate, and property operations.
---

# Money — Total Financial Dominance

Consolidates: financial-intelligence, invest-intel, spend-intel, tax-intel, estate-guard, property-ops

**Sub-mode detection:** Match user intent:
- "Financial check", "Money update", "Net worth", "Retirement update" → **brief**
- "Investment check", "Market brief", "Portfolio review" → **invest**
- "Budget review", "Spending review", "Transaction analysis" → **spend**
- "Tax check", "Tax optimization" → **tax**
- "Estate plan", "Will", "Beneficiaries" → **estate**
- "Property update", "Rental check", "Mortgage check" → **property**

## Standing Orders
1. **One source of truth** — all numbers backed by JSON data files, never manual estimates.
2. **SWOT every plan** — stress-test assumptions, challenge projections, call out blind spots before Commander asks.
3. **Never soften numbers** — ugly numbers stay ugly. Truth-first, always.

## Sub-Mode: brief
### Procedure
1. Pull latest from owens_future_data.json and lifeos_data.json.
2. Compute net worth, FCF, debt status, e-fund progress.
3. Compare to last period — surface delta and trend.
4. Flag any metric outside tolerance (e-fund pace, spending spike, income change).
5. One-paragraph BLUF, then table.
### Output Format
- BLUF paragraph
- Net Worth / FCF / Debt / E-Fund table
- Trend arrows and flags

## Sub-Mode: invest
### Procedure
1. Pull market_data.json and portfolio holdings.
2. Assess RSU position (LLY shares, catalysts, thesis intact?).
3. Check retirement projections — pension, 401k, Roth IRA.
4. Surface any rebalancing triggers or market events.
5. SWOT the current investment posture.
### Output Format
- Portfolio summary table
- RSU thesis check
- Retirement projection snapshot
- SWOT matrix

## Sub-Mode: spend
### Procedure
1. Pull transaction data and budget categories.
2. Compare actual vs. planned by category.
3. Flag overages > 10% in any category.
4. Calculate fun money remaining.
5. Surface subscription creep or recurring charge changes.
### Output Format
- Budget vs. actual table
- Overage flags
- Fun money remaining
- Subscription audit (if changes detected)

## Sub-Mode: tax
### Procedure
1. Review current tax position — withholding, estimated payments, deductions.
2. Identify optimization opportunities (HSA, 401k max, Roth conversion, charitable).
3. Check military-specific tax benefits (state exemptions, combat zone carryover).
4. Model impact of any proposed changes.
### Output Format
- Current tax posture summary
- Optimization opportunities ranked by impact
- Action items with deadlines

## Sub-Mode: estate
### Procedure
1. Audit beneficiary designations across all accounts (401k, IRA, insurance, TSP).
2. Check will/trust currency — any life changes since last update?
3. Verify SBP election alignment with family plan.
4. Flag gaps in coverage or outdated designations.
### Output Format
- Beneficiary audit table (account → designated → correct?)
- Gap analysis
- Action items

## Sub-Mode: property
### Procedure
1. Pull property data — mortgage balances, rental income, expenses.
2. Calculate cash flow per property.
3. Check maintenance schedule and upcoming costs.
4. Review property tax status (military exemption applied?).
5. Assess equity position and market comps if available.
### Output Format
- Property cash flow table
- Maintenance calendar
- Equity snapshot

## Shared Data Sources
- `~/Documents/S6_COMMS_TECH/data/owens_future_data.json`
- `~/Documents/S6_COMMS_TECH/data/lifeos_data.json`
- `~/Documents/S6_COMMS_TECH/data/market_data.json`
- `~/Library/Mobile Documents/com~apple~CloudDocs/COP.md` (financial section)
- Financial Plan markdown files
