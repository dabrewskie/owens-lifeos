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

### Step 2: Refresh Stale Sections

**S1 — Personnel (Family):**
- Check Google Calendar for family events in next 14 days
- Update 90-day horizon with upcoming birthdays, anniversaries, school events
- Note: Emory (7, bday 2/25), Harlan (3), Rylan (14, bday 9/24), Lindsey (bday 2/8), Anniversary 9/6

**S2 — Intelligence (Career/Development):**
- Generally low-frequency updates. Note staleness but don't fabricate data.
- Check if any Lilly milestones approaching (8-year anniversary 7/10)

**S3 — Operations (Life Admin):**
- Check for approaching deadlines in action items
- Verify estate planning status (CCIR #3: deadline 3/15)
- Check NGB 23A due date (April annually)

**S4 — Logistics/Finance:**
- Check current date vs. financial milestones (CC payoff 3/6/26, bonus timing)
- Note any changes to financial context from recent history entries
- Cannot auto-pull account balances — note if data needs manual refresh

**Medical:**
- Run: `python3 ~/Documents/S6_COMMS_TECH/scripts/health_auto_export_reader.py`
- Update with latest macro/body comp data if available
- Flag data gaps

**S6 — Communications/IT:**
- Run: `python3 ~/Documents/S6_COMMS_TECH/scripts/security_audit.py --quick`
- Update security posture
- Check LaunchAgent status

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

## The Standard

The COP sync is infrastructure maintenance. It's not glamorous. But a military staff that doesn't update the COP is flying blind. This agent ensures no domain goes dark for more than a few days.
