---
name: military
description: >
  Guard check, RPED, Military retirement, Tricare, SBP, VA check, VA benefits,
  Chapter 35, CHAMPVA, Property tax exemption.
  Unified military intelligence covering Guard retirement tracking, benefits
  verification, VA entitlements, and military-specific financial operations.
---

# Military — Gray Area Retiree Operations

Consolidates: guard-admin, va-intel

**CRITICAL CONTEXT:** Tory is RETIRED from the Indiana Army National Guard (April 2024, 23 years, 1SG/E-8). He is NOT active duty. NOT drilling. NO Guard income. He is a GRAY AREA RETIREE — meaning he has earned retirement but pay does not start until RPED (Retired Pay Eligibility Date): **2040/09/07**.

**Sub-mode detection:** Match user intent:
- "Guard check", "RPED", "Military retirement", "Tricare", "SBP" → **guard**
- "VA check", "VA benefits", "Chapter 35", "CHAMPVA", "Property tax exemption" → **va**

## Standing Orders
1. **Gray area retiree status** — never confuse "retired" with "receiving retirement pay." Pay starts at RPED 2040. Until then, no military income.
2. **No Guard income currently** — do not include Guard pay in any financial projection for the current period.
3. **Track retirement pay verification** — ensure points, service years, and pay grade are correctly recorded for when RPED arrives.

## Sub-Mode: guard
### Procedure
1. Pull COP military section.
2. Verify retirement record status:
   - Total service: 23 years
   - Rank at retirement: 1SG (E-8)
   - Retirement date: April 2024
   - RPED: September 7, 2040
3. Check Tricare eligibility timeline — Tricare Reserve Retired available at age 60 (or earlier with qualifying active duty time under NDAA provisions).
4. Verify SBP (Survivor Benefit Plan) election status and cost projections.
5. Check retirement points statement — any corrections needed?
6. Calculate projected retirement pay at RPED:
   - Pension projections: $7,348/mo single / $6,123/mo joint (per Fidelity 3/19)
7. Surface any administrative actions needed (ID card renewal, DEERS update, etc.).
### Output Format
- Retirement record verification
- RPED countdown
- Tricare timeline
- SBP status
- Projected pay
- Admin action items

## Sub-Mode: va
### Procedure
1. Audit current VA benefits status:
   - Disability rating and compensation
   - Healthcare enrollment and eligibility
   - Education benefits (Chapter 35 for dependents if applicable)
2. Check for unclaimed benefits:
   - Property tax exemption (state-specific, verify applied)
   - CHAMPVA eligibility for dependents
   - VA home loan entitlement remaining
   - Veteran-specific state benefits
3. Verify all benefits are correctly applied and payments current.
4. Flag upcoming recertification or renewal deadlines.
5. Surface any new VA programs or policy changes that may apply.
### Output Format
- Benefits inventory table
- Unclaimed benefits check
- Payment verification
- Deadline calendar
- New program alerts

## Shared Data Sources
- `~/Library/Mobile Documents/com~apple~CloudDocs/COP.md` (military section)
- Military service records (when accessible)
- VA.gov benefit letters
