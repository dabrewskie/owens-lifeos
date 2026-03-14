---
name: platform-sync
description: "Cross-platform synchronization orchestrator. Generates briefing packet, pushes COP to Notion, and keeps all Claude instances current. Triggers on: 'Platform sync', 'Sync all instances', 'Update the briefing packet', 'Push to Notion', 'Cross-platform update', 'Sync the system', 'Update all Claudes', 'Briefing packet refresh'."
---

# Platform Sync — Cross-Instance Synchronization

You are the synchronization engine for Tory Owens' Life OS. Your job is to ensure every Claude instance (Code, Desktop, Web, iOS) has current operational context.

## Execution Steps

### Step 1: Generate Briefing Packet
Run the briefing packet generator:
```bash
python3 ~/Documents/S6_COMMS_TECH/scripts/briefing_packet_generator.py
```
This reads PROFILE.md + COP.md + CLAUDE.md and produces `~/Library/Mobile Documents/com~apple~CloudDocs/BRIEFING_PACKET.md`.

Report: character count, staleness warnings, any missing source files.

### Step 2: Push COP to Notion
Using the Notion MCP tools:
1. Search for the "COP Mirror" page in Notion (under "Life OS Hub")
2. If it exists, update it with the current COP content
3. If it doesn't exist, create it under the Life OS Hub page
4. Update the "Last Synced" timestamp at the top

### Step 3: Push Session Log Summary to Notion
1. Search for the "Session Log" database in Notion
2. If recent sessions from Claude Code had meaningful outcomes, create entries
3. Each entry: date, platform (Claude Code), summary, domains affected, action items generated

### Step 4: Push Action Items to Notion
1. Search for the "Action Items" database in Notion
2. Sync current COP action items to the database
3. Mark completed items, add new ones, update statuses

### Step 5: Verify and Report
- Confirm briefing packet generated (check file exists and timestamp)
- Confirm Notion pages updated
- Report any failures
- Calculate days since last sync

## Output
Write sync status to: `~/Library/Mobile Documents/com~apple~CloudDocs/platform-sync-latest.md`

Format:
```
# Platform Sync — [TIMESTAMP]
## Briefing Packet: [GENERATED/FAILED] ([char count] chars)
## Notion COP: [SYNCED/FAILED]
## Notion Session Log: [X entries pushed]
## Notion Action Items: [X synced, Y new, Z completed]
## Next Auto-Sync: [scheduled time]
## Staleness: [days since COP last updated]
```

## Integration Points
- **Runs after**: cop-sync, eod-close, weekly-assessment
- **Reads from**: COP.md, PROFILE.md, CLAUDE.md, HISTORY.md
- **Writes to**: BRIEFING_PACKET.md, Notion, platform-sync-latest.md
- **Feeds**: All non-Code Claude instances via Project instructions + Notion

## Standing Orders Apply
- SO #1: If sync reveals stale data, say so
- SO #3: Report the gap, not "sync looks good"
- Never silently skip a failed sync step

## Notion Reference (Actual IDs — do not search, use directly)
- **LifeOS Hub**: page `1e6d8b84a3b68065b3e7dd14ee0cb5b6`
- **COP Mirror**: page `323d8b84-a3b6-8101-8cad-f166d58b46a3` (under LifeOS)
- **COS Action Tracker**: database `1e6d8b84a3b6800c8689c7e96420bc9d`, data source `collection://1e6d8b84-a3b6-805b-b4c9-000b642d233d`
- **Session Log**: database `077d28dd92764622b9d4aac6c53c752e`, data source `collection://85358b0a-c917-4aff-a3ae-46a7df01df33`
- **Decision Log**: database `c2a4d472b6374b3aa507cf5c6d73dcc8`, data source `collection://c35f903c-315e-4098-a8a0-01a07212985e`

### Action Tracker Schema (existing — do not recreate)
Properties: Name (title), Status (Inbox/Today/In Progress/Waiting/Done/Archived), Priority (P1-P4), Domain (S1-S6/Medical/Career/Recreation), Due Date, Source (Email Triage/Manual/Calendar/COS Brief/Friday Assessment), Blocked By, Notes
