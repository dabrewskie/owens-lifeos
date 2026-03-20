---
name: body-recomp
description: >
  Body recomposition tracking for Tory's TRT journey. Reads recomp_data.json
  and delivers week-over-week SITREP with metrics, phase analysis, trends,
  and flags. Triggers on: "Recomp check", "Body comp", "TRT progress",
  "How's the recomp", "Body recomp", "TRT update", "Body composition",
  "Recomp status", "How's my body comp". Standing Order #1 applies.
---

# Body Recomp Intelligence — TRT Journey Tracker

**Mission:** Report body recomposition progress against protocol phases. No softening. If the numbers are stalling, say so. If a phase isn't producing results, flag it.

---

## Data Source

**Primary:** `~/Documents/S6_COMMS_TECH/dashboard/recomp_data.json`
- Written by `recomp_ingestion.py` during daily data-ingest (0632)
- Contains: weekly body comp, photos, labs, phase deltas, KPIs

**If JSON is missing or stale (>48h):** Run the ingestion script first:
```bash
python3 ~/Documents/S6_COMMS_TECH/scripts/recomp_ingestion.py
```

---

## Protocol Timeline

| Phase | Start | Intervention | Color |
|-------|-------|-------------|-------|
| Pre-TRT | Before 9/11/2025 | Baseline | — |
| TRT Only | 9/11/2025 | Testosterone | Blue |
| TRT + AI | 12/2025 | + Aromatase Inhibitor | Green |
| TRT + AI + Peptides | 3/13/2026 | + CJC-1295/Ipamorelin | Gold |

---

## SITREP Format

Read `recomp_data.json` and deliver:

### 1. Header
```
BODY RECOMP SITREP — Week {current_week} of {total_weeks_target}
Phase: {current_phase} (Day {days_in_phase})
Last Updated: {last_updated}
```

### 2. KPI Snapshot
| Metric | Current | Start | Delta | Trend |
|--------|---------|-------|-------|-------|
| Weight | {lbs} | {lbs} | {delta} | {direction over last 4 weeks} |
| Body Fat | {%} | {%} | {delta} | {direction over last 4 weeks} |
| Lean Mass | {lbs} | {lbs} | {delta} | {direction over last 4 weeks} |
| BMI | {val} | {val} | {delta} | — |
| Testosterone | {ng/dL} | {ng/dL} | {delta} | — |

### 3. Phase Performance
For each phase, report:
- Duration in weeks
- Weight delta, BF% delta, lean mass delta
- Rate of change per week
- Assessment: EFFECTIVE / MARGINAL / STALLED

### 4. Current Week vs Last Week
- Weight change
- BF% change
- Lean mass change
- Photo status (days since last photo)

### 5. Flags
- RED: Adverse trend 3+ weeks (weight up or BF% up consistently)
- AMBER: No photo in 10+ days, stale data (>48h), lab draw overdue
- GREEN: On track, photos current, data fresh

### 6. Lab Status
- Days until next expected draw
- Any markers trending out of range
- Hematocrit watch (phlebotomy threshold: 54%)

---

## Output Persistence

Write SITREP to: `~/Library/Mobile Documents/com~apple~CloudDocs/recomp-latest.md`

---

## Dashboard Link

View full dashboard: http://localhost:8082/recomp.html
