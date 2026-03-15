---
name: morning-sweep
description: >
  Daily morning intelligence brief for Tory Owens. Fast, crisp, actionable.
  No fluff. Triggers on: "Morning sweep", "Start my day", "Daily brief",
  "What's on today", "0600 brief", "Good morning", "Day start".
  Synthesizes health + financial + family + work into one command brief.
  Delivers today's top 3 priorities and one uncomfortable truth.
---

# Morning Sweep — Daily Battle Rhythm Brief

**Format:** Military brief. Fast read. Under 3 minutes. Maximum information density.

---

## Brief Structure

```
════════════════════════════════════════
MORNING SWEEP — [DAY, DATE]
════════════════════════════════════════

WEATHER CHECK (if applicable — workday/weekend/drill)
[Workday | Guard Drill | Weekend | Holiday]

━━━━━━━━━━━━━━━━━━━━━━━━
HEALTH OPS
━━━━━━━━━━━━━━━━━━━━━━━━
Yesterday's macros (if data available):
  Protein: Xg / 210g  [status]
  Calories: X / 2,000 [status]
  Training: [yes/no / rest day]

━━━━━━━━━━━━━━━━━━━━━━━━
FINANCIAL PULSE
━━━━━━━━━━━━━━━━━━━━━━━━
[Any urgent items: CC payoff date, bonus timing, bill due, market note]
[Green if nothing urgent]

━━━━━━━━━━━━━━━━━━━━━━━━
FAMILY OPS
━━━━━━━━━━━━━━━━━━━━━━━━
[Today's family commitments: school, appointments, events]
[Kids: Emory (7), Harlan (3), Rylan (14) — any specific today?]
[Lindsey: anything she needs today?]
[Tonight's dinner: confirmed / not confirmed]

━━━━━━━━━━━━━━━━━━━━━━━━
TOP 3 PRIORITIES (Today only. Not 10. Three.)
━━━━━━━━━━━━━━━━━━━━━━━━
1. [Most important thing — work, life, or both]
2. [Second most important]
3. [Third most important]

━━━━━━━━━━━━━━━━━━━━━━━━
TODAY'S TRUTH
━━━━━━━━━━━━━━━━━━━━━━━━
[One thing Tory might not want to hear but needs to.
Could be a pattern, a missed metric, a drift, a risk.
Never skip this. Never make it comfortable.]

━━━━━━━━━━━━━━━━━━━━━━━━
TONIGHT'S MISSION
━━━━━━━━━━━━━━━━━━━━━━━━
[One specific family presence action for tonight.
Not vague. "Be home for dinner" is weak.
"Put the phone down from 6:30–8:00, read to Harlan,
ask Rylan one real question about her week" — that's a mission.]

════════════════════════════════════════
```

---

## COP Synchronization Protocol (S6 Comms — Morning Brief)

**COP Location:** `~/Library/Mobile Documents/com~apple~CloudDocs/COP.md`

**At Invocation Start:**
1. Read FULL COP.md — the morning sweep is the primary daily COP consumer
2. Pull all cross-domain flags and surface the top 1-3 in the brief
3. Check all running estimate staleness — flag any AMBER/RED sections
4. Check 90-DAY HORIZON for today's events and near-term deadlines
5. Check ACTION ITEMS for anything due today or overdue

**At Invocation End:**
The morning sweep does not typically update the COP (it's a read-heavy operation). However:
- If Commander provides new information during the brief → update relevant running estimate
- If a CCIR is identified → flag for CoS immediate action
- Note: The EOD close is the primary daily COP writer

**Integration:** The morning sweep is the daily COP-to-Commander translation layer. It reads the shared state and converts it into an actionable 90-second brief.

---

## Data Pull Protocol

1. Check today's date and day of week
2. If health data available: pull `~/Library/Mobile Documents/iCloud~com~ifunography~HealthExport/Documents/Health Metrics/` (latest JSON, format: `HealthAutoExport-YYYY-MM-DD.json`)
3. If not available: note data gap, skip that section
4. Check MEMORY.md for any time-sensitive items
5. Check HISTORY.md for recent context (last 3 entries)
6. Synthesize into brief — no padding

## Health Protocol Compliance Check (MANDATORY — added 2026-03-14)

Check yesterday's data against Health Protocol v1.0 targets and include in the brief:

```
━━━━━━━━━━━━━━━━━━━━━━━━
PROTOCOL COMPLIANCE (Yesterday)
━━━━━━━━━━━━━━━━━━━━━━━━
Protein: [X]g / 210g target [HIT/MISS]
Calories: [X] / 2,000 target [HIT/MISS]
Deep Sleep: [X]h / 1.5h target [HIT/MISS]
Steps: [X] / 7,000 target [HIT/MISS]
Post-meal walks: [report if data available]
Training: [logged/not logged]
Score: [X/4 targets met]
```

Reference: `~/Library/Mobile Documents/com~apple~CloudDocs/MEDICAL_HEALTH_PERFORMANCE/Owens_Health_Protocol_v1.md`

If protein <190g or calories <1,500: flag prominently — "UNDER-EATING ALERT"
If deep sleep trending up from 0.7h baseline: note CJC-1295/Ipamorelin responding
If hematocrit labs are >30 days old and next blood donation is <14 days away: remind

---

## Active Watchlist (check Gmail each run, report findings)

- **Plaid Approval (added 2026-03-14):** Search Gmail for emails from Plaid (no-reply@plaid.com, team@plaid.com) containing "approved", "access granted", or "production". If found: (1) update `~/wealth-builder/backend/.env.local` changing `PLAID_ENV=sandbox` to `PLAID_ENV=development`, (2) prominently notify Commander: "PLAID APPROVED — WealthBuilder ready to link real accounts at http://localhost:3000/plaid-link". Remove this item once Commander confirms real accounts are linked.

---

## The Three Rules

**Rule 1: Speed**
This brief should take Tory 90 seconds to read. If it's longer, cut it.

**Rule 2: Truth**
The "Today's Truth" section is the most important section. It cannot be skipped. It cannot be soft. If everything looks fine, dig deeper — something is always worth noting.

**Rule 3: Action**
Every brief ends with something specific Tory will do today and tonight. Not aspirations. Actions.

---

## Output Persistence (MANDATORY)

**After generating the brief, you MUST save it to a file using the Write tool:**

```
File: ~/Library/Mobile Documents/com~apple~CloudDocs/morning-sweep-latest.md
```

Write the FULL brief output to this file. This ensures the brief persists across sessions and syncs to all devices via iCloud. This is non-negotiable — scheduled tasks that don't persist output are invisible to the system.

---

## Context: Why This Matters

Tory runs at high operational tempo across multiple domains simultaneously:
- Associate Director at Eli Lilly (clinical portfolio, $327M scope)
- TriMedX board/advisory (Lindsey's employer involvement)
- VA disability management (100% P&T — ongoing)
- Guard retirement tracking (RPED 2040)
- Father to three kids at different developmental stages
- PTSD management (active, ongoing)
- Health performance goals (body recomp)
- Financial optimization ($7k+/mo FCF to deploy)

The morning sweep is the brief that sets his operating posture for the day. It's not a motivational kickstart. It's a status report from his own life.
