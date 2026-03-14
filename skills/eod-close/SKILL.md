---
name: eod-close
description: >
  Daily End of Day close-out for Tory Owens. Captures the day's data, updates
  COP running estimates, logs family presence, and prepares intelligence for
  tomorrow's morning sweep. Triggers on: "Close my day", "EOD", "Day close",
  "End of day", "Wrap up", "Night close", "Log the day". This is the primary
  daily COP writer — the morning sweep reads, the EOD close writes.
---

# EOD Close — Daily Data Capture & COP Writer

**Mission:** Capture the day before it fades. Log what happened, not what was planned. Update the COP so tomorrow's morning sweep starts with fresh intelligence.

---

## Why This Exists

The morning sweep is the reader. This is the writer. Without the EOD close, the COP decays daily — running estimates go stale, family presence goes untracked, health compliance becomes guesswork. The EOD close is the data backbone of the entire system.

---

## Procedure

### Step 1: Gather Today's Data
1. Read the COP: `~/Library/Mobile Documents/com~apple~CloudDocs/COP.md`
2. Read today's HISTORY entries: `~/Library/Mobile Documents/com~apple~CloudDocs/TORY_OWENS_HISTORY.md`
3. Check today's calendar events (gcal_list_events) — what was scheduled
4. Pull health data if available: `python3 ~/Documents/S6_COMMS_TECH/scripts/health_auto_export_reader.py`
5. Check Gmail for any significant items from today

### Step 1b: Check Active Watchlist
- **Plaid Approval (added 2026-03-14):** Search Gmail for emails from Plaid (no-reply@plaid.com, team@plaid.com) containing "approved", "access granted", or "production". If found: (1) update `~/wealth-builder/backend/.env.local` changing `PLAID_ENV=sandbox` to `PLAID_ENV=development`, (2) prominently notify Commander: "PLAID APPROVED — WealthBuilder ready to link real accounts at http://localhost:3000/plaid-link". Remove this watchlist item once Commander confirms real accounts are linked.

### Step 2: Deliver EOD Report

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EOD CLOSE — [DATE]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EXECUTED TODAY:
- [What got done — from calendar, history, context]

HEALTH:
- Macros: P Xg/210g | C Xg/130g | F Xg/71g | Cal X/2000
- Training: [yes/no/rest]
- Status: [GREEN/AMBER/RED]

FAMILY PRESENCE:
- Dinner together: [yes/no]
- Tonight's mission status: [completed/missed/partial]
- Quality time: [any 1:1 moments noted]

FINANCIAL:
- Any notable spending or financial events today

CARRY FORWARD:
- One thing that must happen tomorrow

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Step 3: Update the COP
- Update Medical running estimate if health data was pulled
- Update S1 (family) if presence data captured
- Update any action item statuses
- Set cross-domain flags if findings affect other domains
- Update `Last Updated` timestamps on modified sections

### Step 4: Log
- Append to `~/Library/Mobile Documents/com~apple~CloudDocs/TORY_OWENS_HISTORY.md`:
  `[Date] — EOD close. [1-2 sentence summary of the day]`

---

## Family Presence Tracking

This is the only daily touchpoint that captures family presence data. S1 depends on it.

| Metric | Target | How Captured |
|--------|--------|-------------|
| Family dinners/week | 5 | EOD close asks nightly, tallied Friday |
| 1:1 time with each child | 1x/week each | Noted when it happens |
| Phone-free hours at home | 6:30-8:00 PM | Self-reported or inferred |

If data isn't available (Tory didn't report), note the gap. Gaps are data too — a pattern of no EOD responses tells its own story.

---

## COP Synchronization Protocol (EOD Close)

**At Invocation Start:**
1. Read COP — check what morning sweep surfaced today
2. Check any flags set during the day

**At Invocation End:**
1. Update running estimates with today's data
2. Set new cross-domain flags if applicable
3. Update action item statuses (completed, in progress, blocked)
4. If a CCIR condition was triggered today, ensure it's prominently flagged

---

## Step 5: Cross-Platform Sync
After updating the COP, push changes to all Claude instances:
1. Run: `python3 ~/Documents/S6_COMMS_TECH/scripts/briefing_packet_generator.py`
2. Update the Notion COP Mirror page (under LifeOS) with any changed data
3. Log this EOD session to the Notion Session Log database
This ensures Desktop, Web, and iOS instances have tomorrow's context before the morning sweep.

---

## The Standard

The EOD close is not journaling. It's not reflection. It's a data capture operation. Fast, factual, complete. The goal is that tomorrow's morning sweep can open the COP and see today's truth — not yesterday's assumptions.
