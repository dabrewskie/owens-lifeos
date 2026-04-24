---
name: protocol-command-center
description: >
  Health protocol execution dashboard ("PCC") for Operation Iron Discipline Phase 3. Mobile-first interactive
  interface for daily compliance tracking, weekly Hume scan import, decision trigger detection, and phase
  progression management toward 10-12% BF end state. Triggers on (1) "PCC", "Protocol Command Center",
  (2) "Daily check-in", "Morning protocol", (3) "Scan import", "Import Hume", (4) "Phase A/B/C", "Phase gate",
  (5) "Protocol trigger", "Trigger alert". V1 is a Claude artifact with window.storage persistence; V2 is a
  Code-hosted dashboard wired into Life OS health pipeline.
---

# Protocol Command Center (PCC)

**Project:** Protocol Command Center
**Status:** V1 DEPLOYED (Claude Artifact) — 2026-04-24
**Owner:** Commander Owens
**Parent Protocol:** Operation Iron Discipline Phase 3 Rebuild
**End State:** 10-12% BF with lean mass held or increased. No deadline.

---

## PROJECT PURPOSE

Reduce friction on daily protocol compliance. Surface decision triggers before they become problems. Replace fragmented tracking (Cronometer + Apple Watch + Hume app + Notes + memory) with one operator interface.

**Primary success metric:** 14-day use test yields ≥80% daily input compliance and ≥3 weekly scan imports. If yes → green-light V2 port to Life OS. If no → debrief what failed and rebuild or kill.

---

## VERSION STATUS

### V1 — Claude Artifact (ACTIVE)
- **Location:** Claude artifact in conversation thread dated 2026-04-24
- **Tech:** React + Tailwind + window.storage + Claude API (sonnet-4-20250514)
- **Persistence:** Browser-local via window.storage — NOT synced across devices
- **Data model:** See Section 5 of this doc
- **Home screen:** Installable via Safari "Add to Home Screen"
- **Limitations:** Manual input only; no HealthKit; no COP integration

### V2 — Code-Hosted (PLANNED, post-14-day bake)
- **Target location:** `~/owens-lifeos/dashboards/protocol_command_center.html`
- **Host:** New port on orchestrator (suggest 8079, verify free)
- **Data source:** `health_data.json` (Apple Watch → HAE pipeline, already flowing)
- **Cross-platform:** Tailscale accessible from iPhone
- **Integration points:**
  - Read from `health_data.json` (replaces manual daily input)
  - Write compliance signals to COP.md via `lifeos:log_completion`
  - Fire trigger alerts through `anticipation_engine.py`
  - New MCP tool required: `lifeos:log_protocol_day`
- **PWA:** Manifest + service worker for true installable app
- **Model:** MUST upgrade to current Sonnet (not claude-sonnet-4-20250514 — deprecated June 15)

---

## PROTOCOL REFERENCE (embedded in artifact + authoritative source)

### Phase A — Foundation Recomp (19.5% → ~16% BF)
**Calorie avg:** ~2,470/day | **Expected loss:** 0.5-0.7 lb/week

| Day Type | Days | Cal | P | C | F |
|---|---|---|---|---|---|
| High (heavy lift) | Mon, Thu | 2,600 | 220 | 280 | 70 |
| Moderate | Tue, Fri | 2,450 | 220 | 230 | 70 |
| Active recovery | Sat | 2,400 | 220 | 200 | 75 |
| Rest (low) | Wed, Sun | 2,200 | 220 | 130 | 80 |

**Diet break:** Every 6 weeks, 5-7 days at 2,800 kcal.

### Phase B — Precision Cut (~16% → ~13% BF)
**Calorie avg:** ~2,290/day | **Expected loss:** 0.4-0.5 lb/week

| Day Type | Days | Cal | P | C | F |
|---|---|---|---|---|---|
| Refeed (heavy lift) | Mon, Thu | 2,600 | 230 | 320 | 60 |
| Moderate | Tue, Fri | 2,300 | 230 | 200 | 65 |
| Active recovery | Sat | 2,200 | 230 | 170 | 65 |
| Rest (low) | Wed, Sun | 2,000 | 230 | 100 | 75 |

**Diet break:** Every 4-5 weeks, 5 days maintenance.

### Phase C — Single Digits (~13% → 10-12% BF)
**Calorie avg:** ~2,200/day | **Expected loss:** 0.25-0.4 lb/week

| Day Type | Days | Cal | P | C | F |
|---|---|---|---|---|---|
| Refeed (heavy lift) | Mon, Thu | 2,500 | 240 | 320 | 55 |
| Moderate | Tue, Fri | 2,200 | 240 | 180 | 60 |
| Active recovery | Sat | 2,100 | 240 | 140 | 65 |
| Rest (low) | Wed, Sun | 1,900 | 240 | 80 | 70 |

**Diet break:** Every 3-4 weeks, 5-7 days mandatory.

### Training Split (constant across phases, volume/intensity varies)
| Day | Focus |
|---|---|
| Mon | Upper Push (heavy) |
| Tue | Lower Strength |
| Wed | Active rest / mobility / Zone 2 (45 min) |
| Thu | Upper Pull (heavy) |
| Fri | Lower Power |
| Sat | Zone 2 cardio (45-60 min) |
| Sun | Full rest + meal prep |

---

## DECISION TRIGGERS (codified)

| Trigger | Detection Logic | Severity | Action |
|---|---|---|---|
| Lean mass drop | Δ LM ≤ -2.0 lb over trailing 3 scans | RED | +200 kcal/day, diet break next week |
| Strength drop | 2+ main lifts regress over 2 weeks | AMBER | Sleep audit + deload |
| Weight stall | 4-wk rolling avg flat ±0.5 lb × 3 weeks | AMBER | Diet break, then resume |
| Sleep crater | <6h on 3+ nights in rolling 7 | RED | Skip training, walk only |
| HRV drop | 15% below 30-day baseline | AMBER | Deload week |
| Hct threshold | Scan imports value ≥54% | RED | Donate blood, hydration audit |
| Deep sleep chronic | 14-day avg <0.5h | AMBER | Sleep intervention escalation |

## PHASE GATES

| Gate | Criteria | Effect |
|---|---|---|
| A → B | BF ≤ 16.5% × 2 weeks + LM ≥ 173 lb | Advance available |
| B → C | BF ≤ 13.2% × 2 weeks + LM ≥ 173 lb | Advance available |
| C → Maintenance | BF ≤ 12% × 4 weeks + LM stable | Transition to maintenance macros |

---

## DATA MODEL (for V2 port reference)

### DailyLog (keyed by date)
```
{
  date: "YYYY-MM-DD",
  weight: float,
  sleep_total: float,
  sleep_deep: float,
  hrv: int,
  rhr: int,
  training_done: bool,
  training_rpe: int,
  supplements: { trt, tadalafil, mag, creatine },
  macros_est: { kcal, protein, carbs, fat },
  mood: int,
  notes: string
}
```

### WeeklyScan (keyed by date)
```
{
  date: "YYYY-MM-DD",
  weight: float,
  bf_pct: float,
  fat_mass: float,
  lean_mass: float,
  skeletal_muscle: float,
  body_water_pct: float,
  visceral_fat: int,
  ai_analysis: string,
  delta_vs_prior: { weight, bf, lm }
}
```

### PhaseState (single object)
```
{
  current_phase: "A" | "B" | "C" | "M",
  week_in_phase: int,
  phase_start_date: "YYYY-MM-DD",
  last_diet_break: "YYYY-MM-DD" | null,
  triggers: { lean_mass_drop, strength_drop, weight_stall, sleep_crater,
              hrv_drop, hematocrit, deep_sleep_chronic }
}
```

---

## V1 STORAGE KEYS (window.storage — private scope)

| Key | Content |
|---|---|
| `pcc:daily:YYYY-MM-DD` | DailyLog |
| `pcc:scan:YYYY-MM-DD` | WeeklyScan |
| `pcc:phase_state` | PhaseState |
| `pcc:settings` | User prefs |

---

## ITERATION LOG

| Date | Version | Change | Notes |
|---|---|---|---|
| 2026-04-24 | 1.0 | Initial V1 artifact deployed | Spec approved as-is. 14-day bake period started. |

---

## COP INTEGRATION (CURRENT)

This skill exists so Claude Code can locate the project when referenced. V1 operates independently of COP. V2 will integrate via:
- `lifeos:log_completion` on daily input submission
- New MCP tool `lifeos:log_protocol_day` (to be built with V2)
- Anticipation engine task `protocol_trigger_scan` (to be built with V2)

---

## NOTES FOR CLAUDE CODE (V2 BUILD)

When building V2, reference:
- This skill file for full spec
- `health-performance` skill for protocol philosophy
- `personal-cos` skill for COP integration patterns
- The V1 artifact code (captured in Conversation 2026-04-24 — ask Commander for URL if needed)

Critical V2 requirements:
1. **Model upgrade:** Replace `claude-sonnet-4-20250514` with current Sonnet model (June 15 deprecation)
2. **Data source switch:** Read `health_data.json` instead of manual input — preserve manual override for fields not covered by Apple Watch (macros, supplement compliance)
3. **COP writeback:** Daily compliance → staff section running estimates
4. **PWA packaging:** Installable app via Tailscale URL
5. **Trigger integration:** Fire into `anticipation_engine.py` for morning sweep surfacing
6. **Weekly feedback loop:** Commander provides weekly notes; update this skill's ITERATION LOG

---

*"You don't need motivation. You need clarity and friction removal."*
