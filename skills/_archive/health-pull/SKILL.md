---
name: health-pull
description: >
  Pull and analyze Tory's latest health data from Health Auto Export CSVs. Executes
  the reader script and delivers a no-softening SITREP against targets. Triggers on:
  "Health check", "Health pull", "How are my macros", "Nutrition status", "Body comp",
  "Training status", "Health data", "How am I doing on health", "Morning health brief".
  Standing Order #1 applies: report truth even when the numbers are ugly.
---

# Health Intelligence — Tory Owens

**Mission:** Pull real data. Report against real targets. No rounding up. No "pretty close" when it's not.

---

## Data Sources (Priority Order)

1. **Primary — Health Auto Export JSON** (CORRECT PATH — fixed 2026-03-09)
   `~/Library/Mobile Documents/iCloud~com~ifunography~HealthExport/Documents/Health Metrics/`
   - Format: Daily JSON files (`HealthAutoExport-YYYY-MM-DD.json`)
   - Run: `python3 ~/Documents/S6_COMMS_TECH/scripts/health_auto_export_reader.py`
   - Contains macros (from Cronometer), vitals (Apple Watch), sleep, activity, body comp

2. **AutoSync (same app, more granular)**
   `~/Library/Mobile Documents/iCloud~com~ifunography~HealthExport/Documents/AutoSync/`
   - Sub-folders: HealthMetrics/, Routes/, Workouts/

3. **Tertiary — Apple Health XML**
   `~/Library/Mobile Documents/com~apple~CloudDocs/apple_health_export/export.xml`
   - Hume body composition (weight, body fat %, BMI)
   - Fallback when JSON not available

---

## Target Standards

| Metric | Target | Status Logic |
|--------|--------|-------------|
| Protein | 210g | Green ≥200g / Amber 170-199g / Red <170g |
| Carbs | 130g | Green ≤145g / Amber 146-165g / Red >165g |
| Fat | 71g | Green ≤80g / Amber 81-95g / Red >95g |
| Calories | 2,000 kcal | Green 1,850-2,100 / Amber ±200 / Red outside |
| Training | 4x/week | Green 4+ / Amber 2-3 / Red 0-1 |
| Body Fat % | Trending down | Green decline / Amber flat / Red increase |
| Weight | Trending toward target | Per goal set |

---

## Output Format

```
HEALTH SITREP — [Date]
━━━━━━━━━━━━━━━━━━━━━━

NUTRITION (Last 7 days avg)
Protein:  [X]g / 210g target  [🟢/🟡/🔴]
Carbs:    [X]g / 130g target  [🟢/🟡/🔴]
Fat:      [X]g / 71g target   [🟢/🟡/🔴]
Calories: [X] / 2,000 target  [🟢/🟡/🔴]

BODY COMPOSITION (Latest reading)
Weight:   [X] lbs
Body Fat: [X]%
BMI:      [X]
Trend:    [up/down/flat] ([X] lbs vs. 30 days ago)

TRAINING
Sessions this week: [X]/4 target
Last workout: [date or unknown]

ASSESSMENT
[One paragraph. Honest. What is the number-one thing to fix?]

NEXT ACTION
[One specific, executable action]
```

---

## COP Synchronization Protocol (Medical — health-pull)

**COP Location:** `~/Library/Mobile Documents/com~apple~CloudDocs/COP.md`

**At Invocation Start:**
1. Read COP.md — check Medical running estimate for staleness
2. Check CROSS-DOMAIN FLAGS targeting Medical (e.g., from S1 re: Rylan's ADHD meds, from S2 re: health→performance cascade)
3. Incorporate any relevant cross-domain context into analysis

**At Invocation End:**
1. Update the `### Medical (health-pull)` running estimate in COP.md with latest data
2. Set CROSS-DOMAIN FLAGS if health findings affect other domains:
   - Poor macros/training → FLAG S2 (cognitive performance risk)
   - Weight trend concern → FLAG S1 (may affect presence/energy for family)
   - Data staleness → FLAG CoS (system blind spot)
3. Update `Last Updated` timestamp on Medical section
4. If any CCIR triggered (health gap >14 days), flag for CoS

---

## Analysis Protocol

When data is pulled:

1. Calculate 7-day averages for macros
2. Compare against targets — no rounding in Tory's favor
3. Flag trends: is compliance improving or degrading?
4. If body fat % data available, note 30-day trend
5. Cross-reference training frequency if available in data
6. Deliver SITREP without softening

If data isn't current (>7 days since last export):
- Flag the data gap explicitly
- Report last available data with staleness warning
- Remind Tory to export from Health Auto Export iPhone app

---

## The Standard

Tory's macro targets aren't aspirational — they're based on body composition goals and health performance objectives. If he's hitting 160g protein and calling it "pretty close" to 210g, that's not close. That's 24% below target. Say it.

The health system exists because the body is the platform everything else runs on. PTSD recovery, work performance, family presence, longevity — all downstream of physical discipline. This is not optional optimization. This is the base layer.
