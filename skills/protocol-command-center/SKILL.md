---
name: protocol-command-center
description: >
  Health protocol execution dashboard ("PCC") for Operation Iron Discipline Phase 3. Mobile-first passive
  interface that pulls from Apple Health for ambient status, requires active engagement only on Wednesdays
  (Hume scan import + photos + week-over-week analysis) or when triggers fire. Toward end state 10-12% BF
  with lean mass held or increased. V1 was daily-input artifact (killed — anti-pattern). V2 is passive
  Code-hosted dashboard wired to health_data.json.
---

# Protocol Command Center (PCC) — V2

**Status:** V1 KILLED · V2 IN BUILD — 2026-04-24
**Owner:** Commander Owens

## V1 POST-MORTEM

V1 daily morning check-in killed same day. Root cause: daily-input compliance tracker conflicts with ISTJ-A model. All four data points already in Apple Health. Manual entry was ceremony, not signal.

**Principle codified:**
> Ambient by Default, Active by Exception. If the data exists, read it. Don't collect it daily.

## V2 DATA FLOW

```
Apple Watch → Apple Health → Health Auto Export → ~/lifeos/data/health_data.json
                                                          ↓
                                              Local HTTP endpoint (:8077 or :8079)
                                                          ↓
                                       PCC HTML fetches JSON (Tailscale for mobile)
```

### Auto-Pulled (health_data.json)
Weight (latest + rolling) · Sleep (total/deep/REM) · HRV (+ 30d baseline) · RHR · Steps · Active energy · Workouts (type/duration)

### Manual — Wednesday only (~5 min)
Hume scan (8 fields + optional Hct) · Progress photos (front/side/back)

### Manual — Ad-hoc
Phase advance · Diet break · Deload declaration · Notes/overrides

## NEW IA (4 TABS)

### OVERVIEW (ambient landing — no inputs)
- Status dot (composite)
- Today's fuel card (phase + DOW → macros)
- Today's training card (DOW → session)
- Last night recovery snapshot (Apple Health, display-only)
- Active trigger banners
- Top-line scan delta (weight/BF/LM)

### WEDNESDAY (active work)
- Scan import form (8 fields + Hct opt)
- Photo uploads × 3
- Week-over-week delta table
- AI weekly insight (OverwatchTDO voice)
- Trigger check summary
- Phase gate progress + advance button

### TRENDS
- Weight: daily (Apple Health) + Wed scans + 7d rolling
- BF%: scan-only, phase markers, gate lines
- Lean mass: scan-only, floor line
- Sleep: 14d stacked (total+deep)
- HRV: 14d vs 30d baseline
- Workout heatmap (28d, Apple Health)
- Trigger status panel

### PROTOCOL (reference)
Phase A/B/C macros · Gates · Trigger defs · Advance action

## PROTOCOL (unchanged from V1)

**Phase A** 19.5→16% · 2,470kcal avg · 0.5-0.7lb/wk
High(M/Th) 2600·220·280·70 | Mod(T/F) 2450·220·230·70 | ActRec(Sat) 2400·220·200·75 | Rest(W/Sun) 2200·220·130·80

**Phase B** 16→13% · 2,290kcal avg · 0.4-0.5lb/wk
Refeed 2600·230·320·60 | Mod 2300·230·200·65 | ActRec 2200·230·170·65 | Rest 2000·230·100·75

**Phase C** 13→10-12% · 2,200kcal avg · 0.25-0.4lb/wk
Refeed 2500·240·320·55 | Mod 2200·240·180·60 | ActRec 2100·240·140·65 | Rest 1900·240·80·70

**Training:** Mon UPush · Tue LStr · Wed Z2/Mob · Thu UPull · Fri LPow · Sat Z2 · Sun Rest

**Triggers:** LM drop Δ≤-2lb/3scans(RED) · Weight stall 3wk flat(AMB) · Sleep <6h 3+nights(RED) · HRV -15%(AMB) · Hct ≥54%(RED) · Deep sleep 14d<0.5h(AMB)

**Gates:** A→B: BF≤16.5% × 2wk + LM≥161 | B→C: BF≤13.2% × 2wk + LM≥161 | C→M: BF≤12% × 4wk + LM stable

## V2 BUILD REQUIREMENTS FOR CODE

### Infrastructure
1. **Local HTTP endpoint for health_data.json** — prefer reusing :8077 dashboard server, CORS-enabled for localhost + Tailscale
2. **File locations:**
   - HTML: `~/owens-lifeos/dashboards/protocol_command_center.html`
   - Manifest: `~/owens-lifeos/dashboards/pcc-manifest.json`
   - SW: `~/owens-lifeos/dashboards/pcc-sw.js`
   - Icons: `~/owens-lifeos/dashboards/pcc-icon-{192,512}.png`
3. **Photo storage:** `~/owens-lifeos/data/progress_photos/YYYY-MM-DD/{front,side,back}.jpg`
4. **New MCP tools:**
   - `lifeos:save_scan` → writes `~/owens-lifeos/data/scans.json`
   - `lifeos:save_photo` → base64 → jpg write
   - `lifeos:log_protocol_day` → compliance signals to COP
5. **Anticipation engine:**
   - Task `protocol_trigger_scan` every 6h
   - Push via Pushover (verify user has account) when RED fires
   - Wed 0700 reminder: "Hume scan + photos today"
6. **Model upgrade:** Replace `claude-sonnet-4-20250514` throughout (June 15 deprecation)

### Data Contracts

`health_data.json` expected shape:
```
{ "updated_at": "ISO", "metrics": {
  "weight": { "latest": 216.7, "history": [{"date","value"}] },
  "sleep": { "total": 6.7, "deep": 0.54, "rem": 1.8, "history": [...] },
  "hrv": { "latest": 39, "avg_30d": 39, "history": [...] },
  "rhr": { "latest": 71, "history": [...] },
  "steps": { "today": 8500, "history": [...] },
  "workouts": [{"date","type","duration_min"}]
}}
```
If actual format differs, adapter layer in PCC fetch.

`scans.json` (new, PCC writes):
```
[{ "date": "YYYY-MM-DD", "weight": float, "bf_pct": float, "fat_mass": float,
   "lean_mass": float, "skeletal_muscle": float, "body_water_pct": float,
   "visceral_fat": int, "hct": float|null, "photos": [paths], "ai_analysis": string }]
```

### Build Checklist
- [ ] Expose health_data.json via local endpoint
- [ ] Port V2 prototype artifact → production HTML
- [ ] Swap mock data fetcher → real fetch
- [ ] Implement photo uploads + MCP save
- [ ] Implement scan save via MCP
- [ ] PWA manifest + SW + icons
- [ ] anticipation_engine task + Wed reminder
- [ ] Push notifications (verify Pushover)
- [ ] Test Tailscale access from iPhone
- [ ] Back-link to COP via log_protocol_day
- [ ] Upgrade AI model throughout

## ITERATION LOG

| Date | Version | Change |
|---|---|---|
| 2026-04-24 | 1.0 | V1 artifact deployed |
| 2026-04-24 | 1.0 KILLED | Daily check-in anti-pattern. Commander rejection same day. |
| 2026-04-24 | 2.0 | V2: passive dashboard + Wednesday active + trigger-driven. Prototype delivered. |

## PRINCIPLE (propagate to health-performance + COS)

> **Ambient by Default, Active by Exception.**
> Read data that already exists. Active engagement permitted on cadence (weekly scan) or exception (trigger). Daily manual input must justify against this principle or be killed.

---
*Ambient by default. Active by exception.*
