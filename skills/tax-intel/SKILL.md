---
name: tax-intel
description: >
  Tax Intelligence & Optimization for the Owens household. Manages the complex
  intersection of VA disability (tax-free), Guard retirement (partially taxable),
  Lilly W2 + RSUs (capital gains), rental income, and investment accounts.
  Triggers on: "Tax check", "Tax optimization", "What's my tax situation",
  "Capital gains", "RSU tax", "Tax loss harvest", "Roth conversion",
  "Tax planning", "Withholding check", "Tax estimate", "Filing status",
  "Tax bracket", "Deductions". Standing Order #1 applies — report the real
  number, not the comfortable one.
---

# Tax Intelligence — S4 Financial (Tax Division)

**Mission:** Minimize lifetime tax burden across a uniquely complex income stack. Every dollar saved in taxes is a dollar deployed toward RPED 2040. This isn't about compliance — it's about optimization.

---

## Why This Exists

Tory's tax situation is unusually complex and unusually advantageous — but only if managed actively:

- **VA Disability ($4,354/mo):** 100% tax-free, forever. This is the foundation.
- **Lilly W2 (~$174K):** Fully taxable. Standard withholding likely over/under-shooting.
- **Lilly RSUs:** Taxed as ordinary income at vest, capital gains on appreciation after vest.
- **Guard Drill Pay:** Taxable income, but may enable additional retirement contributions.
- **Rental Income ($1,000/mo):** Taxable but offset by depreciation, mortgage interest, expenses.
- **Investment Accounts:** Capital gains, dividends, interest across E*Trade, Transamerica 401k, TSP.
- **Lindsey's Income (TriMedX):** Combined filing impacts bracket, deductions, phase-outs.

Most people have 1-2 income types. Tory has 6+. Without active management, money leaks.

---

## Procedure

### When Invoked — Tax Check

1. **Read current financial data:**
   - Financial Plan: `~/Library/Mobile Documents/com~apple~CloudDocs/Family/Financial-Plan/Owens_Family_Financial_Plan.md`
   - Tax returns: `~/Library/Mobile Documents/com~apple~CloudDocs/Taxes/` (latest available)
   - COP S4 running estimate

2. **Assess current tax posture:**
   - Estimate current year AGI from all income sources
   - Identify current marginal tax bracket (federal + Indiana state)
   - Check withholding adequacy — are estimated payments needed?
   - Flag any upcoming taxable events (RSU vests, property sale, etc.)

3. **Deliver Tax Intelligence Brief:**

```
━━ TAX INTELLIGENCE — [DATE] ━━

INCOME STACK (Current Year Estimate):
  Lilly W2:           $XXX,XXX (taxable)
  Lilly RSUs:         $XX,XXX (ordinary income at vest)
  Guard Drill:        $X,XXX (taxable)
  VA Disability:      $52,248 (TAX-FREE)
  Rental Income:      $12,000 (net after expenses: $X,XXX)
  Lindsey TriMedX:    $XX,XXX (taxable)
  Investment Income:  $X,XXX (dividends, cap gains)
  ─────────────────
  Estimated AGI:      $XXX,XXX
  Tax-Free Income:    $52,248 (VA — NOT included in AGI)

BRACKET ANALYSIS:
  Federal: XX% marginal (MFJ)
  Indiana: 3.05% flat
  Effective rate: XX%

OPTIMIZATION OPPORTUNITIES:
  1. [Most impactful opportunity]
  2. [Second]
  3. [Third]

ACTION ITEMS:
  - [Specific actions with deadlines]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Tax Optimization Strategies (Standing Playbook)

### 1. Roth Conversion Ladder Analysis
- TSP and Transamerica 401k are traditional (pre-tax)
- After military retirement (2040), income drops — lower bracket years are conversion windows
- Model: What's the optimal annual Roth conversion amount between ages 58-72?
- Factor: VA disability is NOT included in AGI, creating a uniquely low taxable income floor

### 2. RSU Tax Management
- Lilly RSUs are taxed as ordinary income at vest date
- Track: vest dates, FMV at vest, subsequent sale prices
- Strategy: Hold for 1+ year post-vest for LTCG treatment on appreciation
- Risk: Concentration — don't hold too much Lilly for tax reasons alone

### 3. Rental Property Optimization
- Depreciation schedule (27.5 year straight-line for residential)
- Deductible expenses: mortgage interest, insurance, repairs, property management
- Track: Is the rental generating a paper loss that offsets other income?
- Passive activity loss rules: Can losses offset W2 income? (AGI < $150K for full deduction — likely phased out)

### 4. Retirement Account Optimization
- **401k (Transamerica):** Traditional vs Roth contributions — which is better at current bracket?
- **TSP:** Roth TSP available? Traditional TSP contributions reduce taxable Guard income
- **Backdoor Roth IRA:** If AGI exceeds Roth IRA limits, use backdoor conversion
- **HSA:** Triple tax advantage — contribute max ($8,300 family 2026), invest, don't spend until retirement

### 5. Capital Gains Harvesting
- In years with lower income (or large deductions), harvest gains at 0% rate
- Tax-loss harvesting: Sell losing positions to offset gains, repurchase after 30 days
- Track wash sale rules carefully

### 6. Indiana-Specific
- Indiana flat income tax: 3.05%
- Military retirement income: Indiana exempts up to $6,250 of military retirement pay
- Property tax deductions/credits for primary residence
- 529 contributions: Indiana offers 20% state tax credit (up to $1,500 credit per year for MFJ)

### 7. VA Tax Benefits (Often Overlooked)
- VA disability is excluded from AGI — this lowers bracket for ALL other income
- Some states exempt VA disability from state taxes (Indiana does)
- Property tax exemptions for disabled veterans (check county-specific rules)
- Vehicle registration exemptions in some states

---

## Seasonal Calendar

| When | Action |
|------|--------|
| January | Gather W-2s, 1099s, K-1s. Review prior year strategy. |
| February | Complete draft return. Identify optimization opportunities before filing. |
| March | Lilly bonus — confirm withholding is adequate |
| April 15 | Filing deadline. Confirm estimated payments if needed. |
| June 15 | Q2 estimated payment (if applicable) |
| September | Q3 estimated payment. Begin year-end tax planning. |
| October | RSU vest calendar review. Tax-loss harvesting window opens. |
| November | Final year-end moves: Roth conversion, charitable giving, 529 contributions |
| December | Maximize retirement contributions. Final tax-loss harvesting. |

---

## Data Sources

- Tax returns: `~/Library/Mobile Documents/com~apple~CloudDocs/Taxes/`
- Financial Plan: `~/Library/Mobile Documents/com~apple~CloudDocs/Family/Financial-Plan/Owens_Family_Financial_Plan.md`
- Lilly pay stubs: [ask Commander for access method]
- Rocket Money exports: `~/Downloads/*transactions*.csv`
- Investment statements: [via WealthBuilder app when Plaid goes live]

---

## The Standard

Tax optimization isn't about being clever — it's about not leaving money on the table. With VA disability creating a tax-free income floor and multiple taxable streams above it, the Owens household has more optimization levers than 95% of families. Every dollar saved in taxes accelerates RPED.

"The question isn't whether you're paying taxes. The question is whether you're paying the RIGHT amount of taxes."
