---
name: health
description: >
  Health check, Health pull, How are my macros, Nutrition status, Body comp,
  Health recommendations, Supplement check, Recomp check, TRT progress,
  Meal plan, What should I eat, Mental health check, PTSD, Stress check.
  Unified health intelligence covering daily metrics, body recomposition,
  nutrition planning, supplement protocols, and mental health operations.
---

# Health — Warfighter Readiness

Consolidates: health-pull, health-recommendations, body-recomp, meal-planner, ptsd-ops

**Sub-mode detection:** Match user intent:
- "Health check", "Health pull", "How are my macros", "Nutrition status" → **check**
- "Health recommendations", "Supplement check" → **optimize**
- "Body comp", "Recomp check", "TRT progress" → **recomp**
- "Meal plan", "What should I eat" → **meals**
- "Mental health check", "PTSD", "Stress check" → **mental**

## Standing Orders
1. **Truth-first** — ugly numbers stay ugly. Never round favorably or soften trends.
2. **Evidence-based only** — no bro-science. Cite mechanisms or studies when recommending changes.
3. **Track to protocol** — every recommendation ties back to established targets and physician guidance.

## Targets
| Metric | Target |
|--------|--------|
| Protein | 210g/day |
| Calories | 2,000 kcal/day |
| Carbs | 130g/day |
| Fat | 71g/day |
| Training | 4x/week |
| Sleep | 7.5h total |
| Deep Sleep | 1.5h minimum |

## Sub-Mode: check
### Procedure
1. Pull latest Health Auto Export JSON (daily metrics).
2. Extract: calories, macros, sleep duration, deep sleep, steps, weight.
3. Compare each metric to targets — flag misses.
4. Calculate rolling 7-day averages for trend detection.
5. Surface any concerning patterns (protein deficit streak, sleep degradation).
### Output Format
- Today's metrics vs. targets table
- 7-day trend summary
- Flags and alerts

## Sub-Mode: optimize
### Procedure
1. Review current supplement stack and medications.
2. Cross-reference with health data trends — are protocols working?
3. Check for interactions or timing conflicts.
4. Identify gaps based on bloodwork or symptom patterns.
5. Rank recommendations by evidence quality and expected impact.
### Output Format
- Current stack review
- Effectiveness assessment
- Recommendations (ranked)
- Interaction check

## Sub-Mode: recomp
### Procedure
1. Pull body composition data — weight, body fat %, lean mass (if available).
2. Chart trajectory against recomp goals.
3. Assess TRT protocol effectiveness — energy, recovery, strength markers.
4. Check training volume and progressive overload adherence.
5. SWOT current recomp approach.
### Output Format
- Body comp trend table
- TRT effectiveness assessment
- Training compliance check
- SWOT matrix

## Sub-Mode: meals
### Procedure
1. Check current macro position for the day (what's been consumed).
2. Calculate remaining macro budget.
3. Generate meal options that hit remaining targets.
4. Prioritize protein-first options.
5. Account for preferences, restrictions, and what's likely available.
### Output Format
- Remaining macro budget
- 2-3 meal options with macro breakdowns
- Protein-first recommendation

## Sub-Mode: mental
### Procedure
1. Check recent sleep quality, stress indicators, and mood patterns.
2. Review therapy cadence — last session, next scheduled.
3. Assess PTSD management — triggers, coping protocol adherence.
4. Check medication compliance (if tracked).
5. Surface environmental stressors (work load, family demands, calendar density).
6. Recommend specific actions — not platitudes.
### Output Format
- Mental health status assessment
- Stressor inventory
- Protocol compliance check
- Actionable recommendations

## Shared Data Sources
- `~/Library/Mobile Documents/iCloud~com~ifunography~HealthExport/Documents/Health Metrics/` (daily JSON)
- `~/Documents/S6_COMMS_TECH/data/health_history.json`
- `~/Library/Mobile Documents/com~apple~CloudDocs/COP.md` (medical section)
