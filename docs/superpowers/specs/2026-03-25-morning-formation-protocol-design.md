# Morning Formation Protocol — Design Spec

**Date:** 2026-03-25
**Author:** OverwatchTDO + Commander
**Status:** Approved — ready for implementation planning

---

## Problem

The Life OS generates intelligence nobody reads. 16+ JSON files, 6 iCloud briefs, 3x/day Overwatch runs, 21 standing patrol agents — but the accountability tracker shows 18% follow-through on recommendations. Overwatch has flagged Dragonslayer for 8 consecutive runs with no resolution signal. The system observes Tory from the outside (health data, calendar, git commits) but has no structured channel for human input. Silence is ambiguous — the system can't distinguish "didn't see it" from "chose not to act."

## Solution

A daily interactive session on iPhone (claude.ai) that replaces passive consumption with active two-way engagement. The Commander confirms, defers, or dismisses every priority, provides subjective inputs the system can't observe, and closes the feedback loop so the system can continuously learn.

## Architecture

### Two-Phase System

**Phase 1 — Formation Packet Assembly (headless, Mac, 0545)**

A dedicated lightweight task (`formation_packet_generator.py`) runs at 0545 via the orchestrator — after Overwatch morning (0530) completes and writes its state, but before the Commander's expected Formation window (0630-0730). The generator reads already-produced JSONs (superagent_state, health_data, accountability_report, calendar_mirror, task_health) and assembles `formation_packet.json`. This is a read-only assembly — no AI inference needed, pure JSON-to-JSON, completes in <5 seconds. Synced to iCloud automatically.

**Expected Formation Window:** 0630-0730 (after packet is ready and synced). The packet includes a `generated` timestamp. If the Commander opens Formation >20 hours after generation, the claude.ai prompt warns that priorities may be stale.

**Phase 2 — Interactive Formation (iPhone, claude.ai)**

Tory opens claude.ai and says "/formation" or "morning." The Project system prompt recognizes this and walks through a 5-step structured flow using the formation packet. At completion, Claude generates a response artifact saved to iCloud for system ingestion.

### Formation Packet Schema

Written by `formation_packet_generator.py` at 0545 to:
`~/Library/Mobile Documents/com~apple~CloudDocs/FORMATION_PACKET.json`

```json
{
  "schema_version": 1,
  "date": "YYYY-MM-DD",
  "generated": "ISO8601 timestamp",
  "priority_cap": 7,
  "overflow_count": 0,
  "sitrep": {
    "health": {
      "recovery_score": 62,
      "recovery_zone": "YELLOW",
      "deep_sleep_hours": 0.4,
      "hrv": 65,
      "flag": "REST DAY prescribed"
    },
    "calendar": [
      { "time": "09:00", "event": "Team standup" },
      { "time": "14:00", "event": "Director roundtable" }
    ],
    "system": {
      "green": 38,
      "total": 43,
      "red": 5,
      "alerts": ["horizon timeout x2", "ecosystem scanner deployed"]
    },
    "overnight": "Free text summary of overnight system activity"
  },
  "priorities": [
    {
      "id": "pri_001",
      "source": "overwatch_concern_002",
      "text": "Dragonslayer — switch Rylan to Standard User",
      "category": "family_safety",
      "age_days": 25,
      "times_flagged": 8,
      "deadline": null,
      "alert_level": "RED",
      "required_response": "confirm | defer(date) | dismiss(reason) | done"
    }
  ],
  "coaching_homework": [
    {
      "id": "hw_001",
      "text": "Ask Lindsey: 'What do you need from me?'",
      "assigned": "2026-03-19",
      "days_pending": 6,
      "required_response": "confirm | defer(date) | done(note)"
    }
  ],
  "substance_prompt": true,
  "input_schema": {
    "energy": "1-5 (1=drained, 5=peak)",
    "mood": "1-5 (1=low, 5=great)",
    "sleep_feel": "1-5 (1=terrible, 5=refreshed)",
    "substances_last_night": ["nicotine", "thc", "alcohol", "caffeine_late", "cold_plunge", "sauna", "sex", "none"],
    "family_pulse": "free text — anything about Lindsey, kids, household",
    "anything_on_mind": "free text — things the system can't see"
  }
}
```

### Interactive Flow (5 steps, 5-7 minutes)

**Step 1 — SITREP (read only, ~60 sec)**
Claude presents overnight summary: recovery score, calendar, system health, Overwatch alerts. Commander reads, no input needed.

**Step 2 — Commander's Input (~90 sec)**
Claude asks for subjective data:
- Energy (1-5)
- Mood (1-5)
- Sleep feel (1-5)
- Substances last night
- Family pulse / anything on your mind

Commander responds naturally in one message. Claude parses into structured fields.

**Step 3 — Priority Board (~2-3 min)**
Every active priority and coaching homework item presented one at a time. Each requires explicit response:
- **Confirm** — will work on it today/this week
- **Defer(date)** — not now, revisit on specific date
- **Done(note)** — completed, with optional context
- **Dismiss(reason)** — removing from active tracking, with reason

Nothing falls through. No item can be skipped without a response.

**Step 4 — Day's Intent (~60 sec)**
Commander states top 3 priorities for the day and any meetings needing prep.

**Step 5 — Formation Complete**
Claude summarizes all inputs, confirms what was logged, and closes with any coaching note (rest day holds, meeting prep reminder, etc.).

### Write-Back Mechanism

**Phase 1 (now) — iCloud File Drop:**
Claude on iPhone generates the formation response as a structured JSON artifact. Commander saves to iCloud via an iOS Shortcut (see Implementation Components). The Shortcut receives the share from Claude and writes directly to the target iCloud path — one tap on the share sheet, no folder navigation.

**Fallback (no Shortcut):** Commander copies the JSON from the artifact, opens a new note or message to self, and the system scrapes it from the briefing packet on next sync. This is worse but functional.

A new orchestrator task (`formation_ingest`) runs every 15 minutes. When it finds a new response file:
1. Parses the formation response JSON
2. Updates `superagent_state.json` — marks concerns as confirmed/deferred/done/dismissed
3. Updates `accountability_report.json` — logs explicit responses with timestamps
4. Updates `substance_tracker.json` — logs substance data from Commander's input
5. Updates `formation_log.json` — append-only daily log for learning
6. Updates COP action items if any priority marked done
7. Moves processed file to `FORMATION_RESPONSES/processed/`

**Phase 2 (future) — Remote MCP:**
When stable, expose MCP server over authenticated HTTP. claude.ai on iPhone writes directly — eliminates file drop latency. No architectural changes needed, just a transport upgrade.

### Formation Response Schema

Written by Claude on iPhone, saved to:
`~/Library/Mobile Documents/com~apple~CloudDocs/FORMATION_RESPONSES/formation_YYYY-MM-DD.json`

```json
{
  "schema_version": 1,
  "date": "YYYY-MM-DD",
  "completed": "ISO8601 timestamp",
  "commander_input": {
    "energy": 3,
    "mood": 4,
    "sleep_feel": 2,
    "substances": ["gummy", "nicotine"],
    "family_pulse": "Talked about summer plans with Lindsey",
    "free_text": null
  },
  "priority_responses": [
    {
      "id": "pri_001",
      "response": "confirm",
      "note": "doing tonight",
      "defer_date": null
    },
    {
      "id": "hw_001",
      "response": "done",
      "note": "she said she wants more date nights"
    }
  ],
  "day_intent": [
    "Director roundtable prep",
    "Estate packet assembly",
    "Zone 2 if recovery allows"
  ]
}
```

### Priority Triage Algorithm

The formation packet caps at 7 priority items + coaching homework (uncapped). `formation_packet_generator.py` applies this triage:

1. All items with `alert_level: RED` — included first, sorted by `age_days` DESC
2. All items with a `deadline` within 7 days — included next, sorted by deadline ASC
3. Remaining `YELLOW` items — sorted by `times_flagged` DESC, then `age_days` DESC
4. **Excluded:** items with `defer_date` >= today (deferred items resurface on their defer date)
5. **Excluded:** items with status `dismissed` or `resolved`
6. If total > 7 after filtering, truncate and set `overflow_count` in the packet so the Commander knows items were omitted

Coaching homework is presented separately (not counted against the 7-item cap) because it requires a different response model (done with context vs confirm/defer).

### Formation Ingest Error Handling

`formation_ingest.py` behavior on edge cases:
- **Invalid JSON** (syntax error, truncated file): log warning to `alert_history.json`, do not process, do not move to `processed/`. Retry on next 15-min cycle (iCloud sync may have been mid-write).
- **Missing fields**: process what's present, skip what's missing. A formation with `commander_input` but no `priority_responses` still logs the subjective data.
- **Unknown priority ID** (stale packet): skip that item with a warning log. Process all other items normally.
- **Duplicate date** (Commander re-did Formation): overwrite the day's entry in `formation_log.json` with the newer response.
- **Partial success**: always write a `formation_log` entry for whatever was successfully processed. Compliance rate metrics should count the day as "completed" even if some items were skipped.

### Formation Log (Learning Data)

`~/Documents/S6_COMMS_TECH/dashboard/formation_log.json` — append-only, one entry per day. Ingested from formation responses by the orchestrator task.

### Learning Loop — Who Reads What

| Consumer | What It Learns | Cadence |
|----------|---------------|---------|
| **Overwatch** | Reads `priority_responses` + `commander_input.free_text`. Ground truth on every priority — no more guessing if silence = not seen. Coaching homework closure with human context. | Every run (3x/day) |
| **Accountability Tracker** | Reads `priority_responses` (response, note, defer_date). Time-to-action from Formation confirm, not recommendation date. Defer reasons tracked — "busy" vs "avoiding." | Daily 1900 |
| **Pattern Prophet** | Reads `commander_input` (energy, mood, sleep_feel, substances). Correlate subjective state with training, day-of-week, substances. Predict bad days. | Daily 1930 |
| **Evolution Engine** | Reads full `formation_log.json` history. What gets chronically deferred? What coaching homework sticks? Gap between morning intent and EOD reality. | Weekly Sunday |
| **Sleep Optimizer** | Reads `commander_input.sleep_feel`. Subjective feel vs objective deep sleep hours — additive to existing metrics, not a replacement. Calibrate when numbers diverge from felt experience. Null on missed Formation days = no data, existing inference continues. | Daily 0730 |
| **Relationship Intel** | Reads `commander_input.family_pulse`. First direct Commander signal about bond health — additive to calendar inference, not a replacement. Calendar gaps still flagged independently. Null family_pulse = no data (not "all clear"). | Daily 0515 |

### Dashboard Integration

Formation data feeds existing dashboard tabs:
- **COP tab** — priority status badges update from confirm/defer/done/dismiss
- **Health tab** — subjective energy/mood/sleep overlaid on objective metrics
- **Evolution tab** — formation compliance rate, chronic deferrals, intent vs outcome

No new dashboard needed. JSON files update, dashboard reads them.

## Implementation Components

### New Files
1. `formation_packet_generator.py` — standalone script, reads existing JSONs (superagent_state, health_data, accountability_report, calendar_mirror, task_health), assembles formation_packet.json. Pure JSON-to-JSON, no AI inference. <5 sec runtime.
2. `formation_ingest.py` — orchestrator task, watches iCloud folder for new response files. Validates JSON structure (schema_version check), skips unknown priority IDs with warning log (does not hard-fail), writes formation_log entry even on partial success. Updates downstream JSONs. Moves processed files to `processed/`.
3. `formation_log.json` — new dashboard data file, append-only daily log
4. claude.ai Project system prompt update — Formation protocol instructions including staleness check (warn if packet >20h old)
5. iOS Shortcut: "Save Formation Response" — receives share from Claude artifact, writes to `iCloud Drive/FORMATION_RESPONSES/formation_YYYY-MM-DD.json`. Must be built and installed on Commander's iPhone.

### Modified Files
1. `lifeos_orchestrator.py` — add `formation_packet` task (daily 0545) and `formation_ingest` task (every 15 min)
2. `overwatch-tdo.md` (agent) — add instruction to read formation_log.json in every run for ground truth on priorities
3. `lifeos_mcp_server.py` — add `get_formation_packet` tool for Desktop access
4. `briefing_packet_generator.py` — include Formation status in cross-platform packet
5. Existing agents — update to read `formation_log.json`:
   - `accountability-tracker.md` — read `priority_responses` for time-to-action and defer reasons
   - `pattern-prophet.md` — read `commander_input` for subjective state correlations
   - `sleep-optimization-engine.py` — read `commander_input.sleep_feel` as additive input
   - `relationship-intel.md` — read `commander_input.family_pulse` as additive signal
   - `evolution-engine.md` — read full formation_log history for behavioral patterns

### iCloud Folders
- `~/Library/Mobile Documents/com~apple~CloudDocs/FORMATION_PACKET.json` (written daily)
- `~/Library/Mobile Documents/com~apple~CloudDocs/FORMATION_RESPONSES/` (Commander saves here)
- `~/Library/Mobile Documents/com~apple~CloudDocs/FORMATION_RESPONSES/processed/` (after ingestion)

## Success Criteria

1. **Compliance:** Priority follow-through rate moves from 18% to >80% within 2 weeks
2. **Data richness:** System has daily subjective inputs (energy, mood, sleep feel, family pulse) for correlation
3. **Accountability clarity:** Zero ambiguous priorities — every item has an explicit Commander response
4. **Learning velocity:** Evolution Engine detects at least 2 new behavioral patterns within 30 days of formation data
5. **Adoption:** Commander completes Formation 5+ days per week for 3 consecutive weeks

## Future Extensions

- **Evening Debrief (Approach C):** Add EOD touchpoint comparing morning intent to actual outcomes. Unlocks intent-vs-reality learning loop.
- **Dispatch push notifications:** When Dispatch exits research preview, push Formation reminder to iPhone. No more "forgot to check."
- **Remote MCP write-back:** Eliminate file drop, enable real-time Formation response ingestion.
- **Voice Formation:** If claude.ai adds voice input on iOS, the entire flow becomes a 3-minute spoken conversation from the couch.

## Risks

| Risk | Mitigation |
|------|-----------|
| Commander skips Formation | Overwatch detects absence by midday run (no formation_log entry for today), iMessage nudge. Missed day = no subjective data, existing inference continues for all agents. |
| iCloud sync delay | 15-min ingest cycle absorbs typical iCloud lag. If >1hr stale, pulse-monitor flags it |
| Formation fatigue | Keep strict 5-7 min. If it grows, cut scope. Simpler beats thorough. |
| Priority list too long | Cap at 7 items via triage algorithm (see Priority Triage Algorithm section). Overflow count surfaced to Commander. |
| Artifact save friction | iOS Shortcut pre-built to target exact iCloud folder — one tap on share sheet. If Shortcut breaks, fallback to manual save (4-6 taps) or copy-paste into follow-up message. |
| Stale packet | claude.ai prompt checks `generated` timestamp. If >20 hours old, warns Commander before proceeding. |
| Corrupted/partial response | formation_ingest.py handles gracefully — processes what it can, logs warnings, never hard-fails (see Formation Ingest Error Handling section). |
