---
name: cop-sync
description: >
  COP freshness maintenance agent for Tory Owens' Life OS. Reads all data sources,
  updates stale running estimates, routes cross-domain flags, and keeps the Common
  Operating Picture current. Triggers on: "COP sync", "Update the COP", "Refresh COP",
  "How fresh is the COP", "COP status", "Sync the system", "Update running estimates".
  The COP is the shared state for the entire Life OS — when it's stale, every skill
  starts with bad intelligence.
---

# COP Synchronization Agent

**Mission:** Keep the Common Operating Picture fresh. Every skill in the Life OS reads the COP for context. Stale COP = bad decisions everywhere.

---

## Why This Exists

The COP is a shared state file. Every skill reads it. But skills only update their own section when they're invoked. If nobody invokes S4 for two weeks, the financial running estimate goes stale — and the morning sweep reports old data as current. The COP sync agent is the custodian that prevents this decay.

---

## Staleness Policy

| Age | Status | Action |
|-----|--------|--------|
| 0-7 days | GREEN | No action needed |
| 8-14 days | AMBER | Queue for refresh, note in output |
| 15+ days | RED | Escalate to Commander — "Operating on assumptions" |

---

## Procedure

### Step 1: Read the Full COP
`~/Library/Mobile Documents/com~apple~CloudDocs/COP.md`

Check every section's `Last Updated` timestamp. Calculate staleness.

### Step 2: Dispatch Domain Agents in Parallel

**Dispatch ALL 5 domain agents in a SINGLE message to refresh stale sections simultaneously:**

```
Agent(subagent_type="domain-medical",    prompt="Run Medical SITREP for COP sync. Include 7-day trends.", run_in_background=true)
Agent(subagent_type="domain-finance",    prompt="Run Finance SITREP for COP sync. Check dashboard JSON freshness.", run_in_background=true)
Agent(subagent_type="domain-family",     prompt="Run Family SITREP for COP sync. Pull 14-day calendar horizon.", run_in_background=true)
Agent(subagent_type="domain-security",   prompt="Run Security SITREP for COP sync. Full LaunchAgent health + posture.", run_in_background=true)
Agent(subagent_type="domain-operations", prompt="Run Operations SITREP for COP sync. Full action item + CCIR status.", run_in_background=true)
```

**CRITICAL:** All 5 calls MUST be in a single message for parallel execution.

### Step 2.5: Gather and Refresh COP Sections

Wait for all agents (60-second timeout). Map each SITREP to the COP:

- **S1 (Family)** ← domain-family output (calendar, kids, presence, milestones)
- **S2 (Intel/Career)** ← note staleness only (low-frequency, don't fabricate)
  - Check if Lilly milestones approaching (8-year anniversary 7/10)
- **S3 (Operations)** ← domain-operations output (action items, deadlines, battle rhythm)
- **S4 (Finance)** ← domain-finance output (snapshot, dashboard health, milestones)
- **Medical** ← domain-medical output (metrics, compliance, trends, alerts)
- **S6 (IT/Comms)** ← domain-security output (posture, LaunchAgents, dashboards)

Update each stale section in COP.md with fresh data from the domain agents.

### Step 3: Route Cross-Domain Flags
- Read all pending flags
- Note which have been addressed and which are still pending
- Set new flags if data refresh reveals cross-domain impacts

### Step 4: CCIR Check
- Evaluate each CCIR against current data
- If any condition is triggered, flag prominently

### Step 5: Update and Log
- Update `Last Full Sync` timestamp
- Append to HISTORY: `[Date] — COP sync. [Sections updated]. [Outstanding flags]`

### Step 5.5: Financial Data Sync
After updating the COP, sync all dashboard JSON data to prevent drift:
1. Run: `python3 ~/Documents/S6_COMMS_TECH/scripts/financial_data_sync.py`
2. This reads `owens_future_data.json` (canonical) and writes to `cop_data.json` financial_snapshot
3. Validates all numbers are consistent — flags contradictions
4. If validation fails, STOP and reconcile before proceeding

### Step 6: Cross-Platform Sync
After updating the COP, trigger platform-sync to push changes to all Claude instances:
1. Run: `python3 ~/Documents/S6_COMMS_TECH/scripts/briefing_packet_generator.py`
2. Update the Notion COP Mirror page (ID: `323d8b84-a3b6-8101-8cad-f166d58b46a3`, under LifeOS)
3. Log this sync to the Notion Session Log database (data source: `collection://85358b0a-c917-4aff-a3ae-46a7df01df33`)
This ensures Desktop, Web, and iOS instances get updated context automatically.

---

## Output Format

```
━━ COP SYNC REPORT — [DATE] ━━

FRESHNESS STATUS:
| Section | Last Updated | Age | Status |
| S1 Family | [date] | [X days] | [G/A/R] |
| S2 Intel | [date] | [X days] | [G/A/R] |
| S3 Ops | [date] | [X days] | [G/A/R] |
| S4 Finance | [date] | [X days] | [G/A/R] |
| Medical | [date] | [X days] | [G/A/R] |
| S6 IT | [date] | [X days] | [G/A/R] |

SECTIONS REFRESHED: [list]
STILL STALE: [list + reason]

CROSS-DOMAIN FLAGS:
- [Pending flags and routing status]

CCIR STATUS:
- [Any triggered conditions]

NEXT SYNC: [date based on schedule]
```

---

## Output Persistence (MANDATORY)

**After completing the COP sync, you MUST save a summary to a file using the Write tool:**

```
File: ~/Library/Mobile Documents/com~apple~CloudDocs/cop-sync-latest.md
```

Write the sync summary (what was updated, what flags were set, staleness status) to this file. This ensures sync results persist and sync to all devices via iCloud. This is non-negotiable — scheduled tasks that don't persist output are invisible to the system.

---

## The Standard

The COP sync is infrastructure maintenance. It's not glamorous. But a military staff that doesn't update the COP is flying blind. This agent ensures no domain goes dark for more than a few days.
