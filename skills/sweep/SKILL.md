---
name: sweep
description: >
  Battle rhythm engine for Tory Owens' Life OS. Sub-modes: morning (daily brief),
  eod (day close + COP write), sync (COP refresh), data (pipeline ingest),
  status (system health). Triggers on: "Morning sweep", "Start my day", "Good morning",
  "Daily brief", "Day start", "0600 brief", "Close my day", "EOD", "Day close",
  "End of day", "Wrap up", "Night close", "Log the day", "COP sync", "Update the COP",
  "Refresh COP", "Sync the system", "Data check", "Data pipeline", "Data freshness",
  "Ingest data", "Pull latest data", "System status", "Platform sync", "Update all Claudes",
  "Briefing packet refresh", "How fresh is the COP".
---

# Sweep — Battle Rhythm Engine

Consolidates: morning-sweep, eod-close, cop-sync, data-pipeline, platform-sync.

**Sub-mode detection:** Match user intent to sub-mode, then execute that procedure.
- "morning", "start my day", "daily brief", "good morning" → **morning**
- "eod", "close my day", "end of day", "wrap up" → **eod**
- "cop sync", "refresh cop", "update cop", "sync the system" → **sync**
- "data check", "data pipeline", "ingest", "pull data" → **data**
- "status", "system health", "platform sync", "briefing packet" → **status**

---

## Standing Orders (All Sub-Modes)

1. **Seek and deliver truth.** Never soften numbers. Never perform wellness.
2. **Read the COP first.** `~/Library/Mobile Documents/com~apple~CloudDocs/COP.md`
3. **Write output to file.** Every sub-mode MUST write its output:
   - morning → `~/Library/Mobile Documents/com~apple~CloudDocs/morning-sweep-latest.md`
   - eod → `~/Library/Mobile Documents/com~apple~CloudDocs/eod-close-latest.md`
   - sync → `~/Library/Mobile Documents/com~apple~CloudDocs/cop-sync-latest.md`
   - data → `~/Library/Mobile Documents/com~apple~CloudDocs/data-ingest-latest.md`
   - status → no file (console only)
4. **Run lifeos_data_sync.py after any data update:** `python3 ~/Documents/S6_COMMS_TECH/scripts/lifeos_data_sync.py`
5. **Domain agents for parallel data gathering.** Dispatch ALL needed domain agents in ONE message:
   ```
   Agent(subagent_type="domain-medical", ...)
   Agent(subagent_type="domain-finance", ...)
   Agent(subagent_type="domain-family", ...)
   Agent(subagent_type="domain-security", ...)
   Agent(subagent_type="domain-operations", ...)
   ```
6. **DESIGN SYSTEM COMPLIANCE (v1.0 — 2026-03-25):**
   - HTML outputs: MUST embed canonical tokens from `~/Library/Mobile Documents/com~apple~CloudDocs/LIFE_OS_DESIGN_TOKENS.css`. No hardcoded hex. Use `var(--token-name)` references.
   - Markdown outputs: MUST follow canonical templates below. Consistent domain naming, heading structure, section order.
   - Reference: `~/Library/Mobile Documents/com~apple~CloudDocs/LIFE_OS_DESIGN_SYSTEM.html`

---

## Sub-Mode: morning

**Mission:** 90-second command brief. What happened overnight, what's today, what needs attention.

### Procedure
1. Dispatch 5 domain agents in parallel (ONE message)
2. Pull calendar: today + tomorrow (gcal_list_events)
3. Read anticipation engine output: `~/Documents/S6_COMMS_TECH/dashboard/pending_actions.json`
4. Read orchestrator health: `~/Documents/S6_COMMS_TECH/dashboard/task_health.json`

### Canonical Output Template
```
# MORNING SWEEP — [Day], [Month] [Date], [Year]
> **Status:** Health [GREEN/AMBER/RED] | Finance [GREEN/AMBER/RED] | Family [GREEN/AMBER/RED] | Admin [GREEN/AMBER/RED]

---

## BLUF
[One paragraph. What matters today. What's at risk. What to execute.]

---

## HEALTH OPS — [GREEN/AMBER/RED]
**Yesterday:** P [X]g/210g [HIT/MISS] | C [X]g/130g | F [X]g/71g | [X] kcal
**Training:** [Type] [Duration] | [X]/14 streak
**Sleep:** Total [X]h | Deep [X]h ([X]% of 1.5h target) | REM [X]h
**Vitals:** RHR [X] | HRV [X]ms | SpO2 [X]%
**Recovery Score:** [X]/100 — [GREEN/AMBER/RED]
**Flags:** [Bulleted items if any]

---

## FINANCIAL INTEL — [GREEN/AMBER/RED]
**Budget:** $[X] spent MTD / $[X] target ([X]% of month elapsed)
**50/30/20:** [X]% needs / [X]% wants / [X]% savings
**LLY:** $[X] ([trend])
**Flags:** [If any]

---

## FAMILY OPS — [GREEN/AMBER/RED]
**Today:** [Events or "Open evening"]
**This week:** [Key events]
**Overdue:** [Action items past due]

---

## LIFE ADMIN — [GREEN/AMBER/RED]
**Critical path:** [Top 1-2 admin items]
**Overdue items:** [Count and list]

---

## DAILY DEVOTION
[One verse. One sentence. Rotate 6 values. Connect to today's challenge.]

---

## COACHING CHALLENGE
[One growth edge for today — not homework, a micro-practice]

---

## TODAY'S BATTLE PLAN
1. [Most important]
2. [Second]
3. [Third]

---

## UNCOMFORTABLE TRUTH
[One thing Tory doesn't want to hear but needs to. Data-backed.]

---
*Generated [timestamp] | Owens Life OS v2.0*
```

### Domain Naming Rules (MANDATORY)
- Health section: ALWAYS "HEALTH OPS" (never "HEALTH SNAPSHOT", "HEALTH PULSE", etc.)
- Finance section: ALWAYS "FINANCIAL INTEL" (never "FINANCIAL PULSE", "FINANCE CHECK", etc.)
- Family section: ALWAYS "FAMILY OPS" (never "FAMILY CHECK", "FAMILY PULSE", etc.)
- Admin section: ALWAYS "LIFE ADMIN" (never "ADMIN CHECK", "ADMIN OPS", etc.)

5. Write output file
6. Run lifeos_data_sync.py

---

## Sub-Mode: eod

**Mission:** Capture the day before it fades. Update COP so tomorrow's sweep starts fresh.

### Procedure
1. Read today's calendar (what was scheduled)
2. Pull health data: `python3 ~/Documents/S6_COMMS_TECH/scripts/health_auto_export_reader.py`
3. Check Gmail for significant items
4. Read COP for current state

### Canonical Output Template
```
# EOD CLOSE — [Day], [Month] [Date], [Year]
> **Status:** Health [GREEN/AMBER/RED] | Finance [GREEN/AMBER/RED] | Family [GREEN/AMBER/RED] | Admin [GREEN/AMBER/RED]

---

## EXECUTED TODAY
- [Completed items with status: ✅ done / ⬜ incomplete / 🔴 blocked]

---

## HEALTH OPS
**Macros:** P [X]g/210g | C [X]g/130g | F [X]g/71g = [X] kcal
**Training:** [Type] [Duration] | [X]/14 streak
**Sleep (last night):** [X]h total | [X]h deep | [X]h REM
**Vitals:** RHR [X] | HRV [X]ms | SpO2 [X]%
**Status:** [GREEN/AMBER/RED] — [one-line summary]

---

## FAMILY PRESENCE
- Dinner present: [Y/N]
- Phone down after dinner: [Y/N]
- 1-on-1 time: [With whom, or none]

---

## FINANCIAL INTEL
[Notable spending, budget status, or "No significant events"]

---

## CARRY FORWARD
1. [Highest priority for tomorrow]
2. [Second]
3. [Third]

---

## FLAGS
[Items requiring commander attention, or "None"]

---
*Generated [timestamp] | Owens Life OS v2.0*
```

5. Update COP.md — medical running estimate, family presence, action item status
6. Log family presence data to `~/Documents/S6_COMMS_TECH/dashboard/presence_log.json`:
   ```json
   {"date": "YYYY-MM-DD", "dinner_present": true/false, "phone_down": true/false, "one_on_one_child": "Rylan"/"Emory"/"Harlan"/null, "notes": "optional"}
   ```
   Append to the `entries` array. The accountability-tracker reads this to track CCIR #5 (family presence <3 dinners/week).
   If the Commander doesn't provide answers, ask directly: "Were you present for dinner? Phone down? Any 1-on-1 time with the kids?"
7. Write output file
8. Run lifeos_data_sync.py
9. Check active watchlist items (Plaid approval, pending items from COP)

---

## Sub-Mode: sync

**Mission:** Refresh every stale COP section. The COP is shared state — stale COP = bad decisions.

### Staleness Policy
| Age | Status | Action |
|-----|--------|--------|
| 0-7 days | GREEN | No action |
| 8-14 days | AMBER | Queue refresh |
| 15+ days | RED | Escalate |

### Procedure
1. Read full COP.md, check every section's timestamp
2. Dispatch 5 domain agents in parallel for stale sections
3. Update stale sections with fresh data
4. Route cross-domain flags
5. CCIR check — evaluate each against current data
6. Run lifeos_data_sync.py
7. Write output file

---

## Sub-Mode: data

**Mission:** Ingest all available data sources. Fill gaps.

### Data Sources
| Source | Script/Tool | Auto? |
|--------|------------|-------|
| Health Export JSON | health_auto_export_reader.py | Yes |
| Body Recomp | recomp_ingestion.py | Yes |
| Rocket Money CSV | rocket_money_ingest.py | Yes |
| Google Calendar | MCP gcal_list_events | Yes |
| Gmail | MCP gmail_search_messages | Yes |
| Financial accounts | Manual | No |

### Procedure (Interactive — when invoked via conversation)
1. Optionally dispatch domain agents for richer analysis context
2. Run health reader: `python3 ~/Documents/S6_COMMS_TECH/scripts/health_auto_export_reader.py`
3. Run recomp ingestion: `python3 ~/Documents/S6_COMMS_TECH/scripts/recomp_ingestion.py`
4. Check for Rocket Money CSV in Downloads
5. Report data freshness for all sources
6. Run lifeos_data_sync.py
7. Write output file

### Scheduled Execution (Automated — via orchestrator at 07:30)
The orchestrator runs `data_pipeline.py` directly (not headless Claude).
This script runs health_reader, recomp_ingest, and rocket_money in parallel,
then consolidates via lifeos_data_sync.py and writes data-ingest-latest.md.
Completes in ~15s vs 7+ min via headless Claude.

---

## Sub-Mode: status

**Mission:** Full system health report. Console only.

### Procedure
1. Run orchestrator status: `python3 ~/Documents/S6_COMMS_TECH/scripts/lifeos_orchestrator.py --status`
2. Run anticipation engine: `python3 ~/Documents/S6_COMMS_TECH/scripts/anticipation_engine.py --test`
3. Check battle rhythm file ages
4. Read lifeos_data.json for dashboard/data freshness
5. Report: orchestrator health, data freshness, battle rhythm %, pending actions
6. Optionally: generate + push briefing packet (`python3 ~/Documents/S6_COMMS_TECH/scripts/briefing_packet_generator.py`)
7. Optionally: push to Notion (COP Mirror, Action Items, Session Log)
8. Optionally: sync skills repo (`bash ~/owens-lifeos/sync.sh push`)

---

## COP Update Protocol (Used by eod and sync)

When updating COP.md:
1. Read current COP
2. Update ONLY sections with fresh data (don't overwrite good data with nothing)
3. Update "Last Updated" timestamp on each section touched
4. Run `python3 ~/Documents/S6_COMMS_TECH/scripts/dashboard_updater.py` after COP write
5. Run `python3 ~/Documents/S6_COMMS_TECH/scripts/lifeos_data_sync.py` to propagate to JSON

---

## Shared Data Sources

- **COP:** `~/Library/Mobile Documents/com~apple~CloudDocs/COP.md`
- **Health Export:** `~/Library/Mobile Documents/iCloud~com~ifunography~HealthExport/Documents/Health Metrics/`
- **Financial Plan:** `~/Library/Mobile Documents/com~apple~CloudDocs/Family/Financial-Plan/Owens_Family_Financial_Plan.md`
- **Orchestrator Health:** `~/Documents/S6_COMMS_TECH/dashboard/task_health.json`
- **Pending Actions:** `~/Documents/S6_COMMS_TECH/dashboard/pending_actions.json`
- **Life OS Data:** `~/Documents/S6_COMMS_TECH/dashboard/lifeos_data.json`
- **Design System:** `~/Library/Mobile Documents/com~apple~CloudDocs/LIFE_OS_DESIGN_TOKENS.css`
- **Design System Reference:** `~/Library/Mobile Documents/com~apple~CloudDocs/LIFE_OS_DESIGN_SYSTEM.html`
