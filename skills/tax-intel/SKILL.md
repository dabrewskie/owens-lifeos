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

### 1. Roth Conversion + VA Tax Arbitrage (Evolution Engine — Score 100)

**Full Strategy Document:** `~/Library/Mobile Documents/com~apple~CloudDocs/roth-conversion-strategy.md`

**Core Insight:** VA disability ($52,248/yr) excluded from AGI creates artificially low taxable income. Real household income is ~$312K but AGI is ~$260K. This means every Roth conversion dollar is taxed at 24% instead of the 32%+ it would face in retirement when Guard pension + Lilly pension + SS stack.

**Pre-Tax Balances for Conversion:**
- Tory Lilly 401k (Traditional portion): ~$143K and growing at $23.5K/yr (switched to Pre-Tax 3/16/26)
- TSP (Guard): **UNKNOWN — Commander must check TSP.gov**
- Combined Traditional balance at RPED: ~$1.5M+ if unconverted

**Active Strategy (3 Phases):**

1. **TSP Roth In-Plan Conversion (Immediate):** Convert Traditional TSP to Roth TSP via TSP.gov. No separation required. Low fees (0.043%). Tax hit at 24% now avoids 32%+ later. Target: 100% Roth TSP by end of 2027.

2. **Annual Bracket-Fill Conversions (2026-2040):** Each November, calculate remaining 24% bracket headroom (~$124K+ above current taxable income). Convert $15K-$25K/yr of Lilly 401k Traditional balance to Roth. Scale UP in income-dip years (maternity leave, job change, market crash). Pay conversion tax from cash flow, never from converted funds.

3. **Post-RPED Roth Withdrawals (2040+):** Guard retirement ($63.8K) + Lilly pension ($73.5K) + VA ($69.6K tax-free) = $207K floor. Pull supplemental income from Roth = $0 additional tax. Avoids RMD exposure at age 73+. SS benefits stay minimally taxed because Roth withdrawals don't count toward provisional income.

**Projected Lifetime Benefit:** $100K-$200K+ in tax savings vs. leaving balances in Traditional accounts.

**Annual Battle Rhythm Addition — November Roth Conversion Window:**
1. Calculate YTD AGI from all sources
2. Determine remaining 24% bracket headroom
3. Execute optimal conversion amount before Dec 31
4. Set aside 28.4% (federal + Indiana) tax reserve for April filing
5. Update strategy document with actual conversion

**TCJA Sunset Risk:** If TCJA expires (2026+), 24% bracket becomes 28%. Conversions still profitable vs. 33% in retirement but less so. Accelerate conversions if sunset appears imminent.

**Action Items:**
- [ ] Commander: Check TSP.gov Traditional vs. Roth balances
- [ ] Commander: Check if Fidelity/Lilly 401k allows in-plan Roth conversions
- [ ] tax-intel: Run first bracket-fill calculation November 2026
- [ ] CoS: Add "November Roth Window" to annual battle rhythm

### 2. RSU Tax Management
- Lilly RSUs are taxed as ordinary income at vest date
- Track: vest dates, FMV at vest, subsequent sale prices
- Strategy: Hold for 1+ year post-vest for LTCG treatment on appreciation
- Risk: Concentration — don't hold too much Lilly for tax reasons alone

#### RSU Withholding Gap Warning (Evolution Engine — Score 100)

**The Problem:** RSU supplemental income is withheld at the IRS flat rate of 22% federal. However, the Owens household actual marginal rate is likely 24-32% based on combined AGI.

**Household AGI Build (before RSUs):**
- Tory base salary: $137,787
- Lindsey base salary: $111,167
- Rental income: $12,000/yr ($1,000/mo)
- Guard drill pay: ~$5,000+
- Investment income: variable
- VA Disability: $52,248/yr — TAX-FREE, excluded from AGI but still real income
- **Estimated AGI before RSUs: ~$266K+**

At $266K+ AGI (MFJ), the household is solidly in the **24% bracket** (2026 MFJ: $201,051-$383,900) and approaching 32% depending on RSU vest size and bonus timing. Every RSU dollar withheld at 22% creates a 2-10% gap per dollar vested.

**Risk:** $1,500-$2,500 underpayment at tax filing, potentially triggering IRS underpayment penalties if total withholding falls short by more than $1,000 or 90% of tax owed.

**Action Required:**
1. **Review W-4 Line 4(c) — Additional Withholding:** Add extra per-paycheck withholding to cover the RSU gap. Estimate: $60-$100/paycheck additional withholding across 24 pay periods = $1,440-$2,400 coverage.
2. **Track each RSU vest:** Calculate the gap between 22% withheld and actual marginal rate at vest. Log in COP.
3. **Q3 withholding check:** By September, run a year-to-date projection to confirm withholding is on track. Adjust W-4 if needed.
4. **Consider selling RSU shares at vest** to cover the tax gap immediately rather than holding and facing a lump-sum bill at filing.

**Standing Order:** Flag this during every October RSU vest calendar review and every March bonus withholding check.

### SALT Cap Analysis (Evolution Engine — Score 75, Analyzed 2026-03-19)

**Context:** The 2025 tax law quadrupled the SALT deduction cap to $40,400 for MFJ filers. Question: does this change the Owens household from standard deduction to itemizing?

**Answer: No. Standard deduction wins by $10,000-$15,000. The SALT cap is not the binding constraint.**

**Itemized Deduction Build (2025 Tax Year):**

| Component | Amount | Notes |
|-----------|--------|-------|
| Indiana state income tax (2.95%) | ~$6,372 | On ~$216K taxable income (AGI after 401k/HSA) |
| Hamilton County income tax (1.44%) | ~$3,110 | Local income tax, counts as SALT |
| **SALT subtotal** | **~$9,482** | Well under $40,400 cap |
| Property taxes | $0–$4,508 | $0 if VA P&T exemption filed; $4,508 if not yet |
| **Total SALT** | **$9,482–$13,990** | Cap is irrelevant at this level |
| Mortgage interest (2.25% on $246K) | ~$5,535 | Low rate = low deduction |
| Charitable giving | **UNKNOWN** | **FLAG: Commander needs to provide 2025 giving total** |
| **Total Itemized** | **~$15,017–$19,525** | Before charitable |
| **Standard Deduction (MFJ 2025)** | **$30,000** | |
| **Gap (standard wins)** | **$10,475–$14,983** | |

**Why the SALT Cap Increase Does Not Help:**
1. Indiana is a low-tax state (2.95% flat + ~1.44% county). Total state/local income tax is only ~$9,500.
2. VA P&T property tax exemption eliminates or will eliminate property taxes entirely.
3. The 2.25% mortgage rate — an incredible asset for wealth building — is a terrible asset for itemizing.
4. The problem is not that SALT is being capped. The problem is total itemized deductions are too low to beat $30,000.

**Break-Even Analysis:**
- To itemize, charitable giving would need to exceed **$10,475** (if property tax exempt) or **$5,967** (if not yet exempt).
- If Commander is giving $10K+/yr to charity, itemizing may be worth revisiting.
- Consider: donor-advised fund (DAF) "bunching" strategy — contribute 2-3 years of charitable giving in one year to exceed the standard deduction threshold, then take standard deduction in off years.

**Action Items:**
1. **Commander: Report 2025 charitable giving total.** This is the only variable that could flip the analysis.
2. **Confirm VA P&T property tax exemption status** for Hamilton County 2025 assessment. If not yet filed, file immediately — saves $4,508/yr regardless of itemizing.
3. **If charitable giving is significant:** Model a DAF bunching strategy (e.g., $30K in one year, $0 the next two) to alternate between itemizing and standard deduction.
4. **No action needed on SALT cap itself** — household is $26,000+ below the $40,400 cap. This is a non-issue.

**Standing Note:** Revisit if (a) Indiana raises state income tax, (b) property tax exemption is lost, (c) mortgage is refinanced at higher rate, or (d) household moves to a high-tax state. None of these are expected.

---

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
| January | Gather W-2s, 1099s, K-1s. Review prior year strategy. **Request CHAMPVA 1095-B from VA** (no longer auto-mailed as of 2026 — must be manually requested for tax filing). |
| February | Complete draft return. Identify optimization opportunities before filing. |
| March | Lilly bonus — confirm withholding is adequate |
| April 15 | Filing deadline. Confirm estimated payments if needed. |
| June 15 | Q2 estimated payment (if applicable) |
| September | Q3 estimated payment. Begin year-end tax planning. |
| October | RSU vest calendar review. Tax-loss harvesting window opens. |
| November | **ROTH CONVERSION WINDOW:** Run bracket-fill calculation, execute optimal conversion amount. Also: charitable giving, 529 contributions. See `roth-conversion-strategy.md`. |
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
