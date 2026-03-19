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
EVOLUTION INTEL
━━━━━━━━━━━━━━━━━━━━━━━━
[See Evolution Intelligence section below for data pull]

━━━━━━━━━━━━━━━━━━━━━━━━
DAILY DEVOTION
━━━━━━━━━━━━━━━━━━━━━━━━
[One verse. One sentence of application to TODAY.
Rotate through the 6 Values Foundation principles:
Servant Leadership (Mark 10:45), Truth (Prov 12:22),
Stewardship (Luke 16:10), Grace Under Pressure (James 1:2-4),
Development of Others (Prov 27:17), Wisdom (Prov 4:7).
Connect to whatever today's biggest challenge is.
End with a one-line prayer intention for the day.
This is not performative — it's calibration.]

━━━━━━━━━━━━━━━━━━━━━━━━
COACHING CHALLENGE
━━━━━━━━━━━━━━━━━━━━━━━━
[One challenge from the Development Intelligence system.
Could be: a concept to think about during the day,
a leadership micro-practice to try in a meeting,
a question to sit with, a relationship action item.
Tracks to the 5 learning tracks and Director readiness gaps.
Not homework — a growth edge for today.]

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
ask Rylan one real question about his day" — that's a mission.

RELATIONSHIP TRACKER (rotate focus):
- Lindsey: When did you last ask what SHE needs? (Not family — her.)
- Rylan (14): When was the last 1-on-1 that was HIS choice? (Gaming counts.)
- Emory (7): What's she excited about right now?
- Harlan (3): Did you get floor time today?
Flag if any relationship has gone 7+ days without intentional 1-on-1.]

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

## Data Pull Protocol — PARALLEL DOMAIN AGENTS

**The morning sweep dispatches 5 domain agents in parallel.** This is a scatter-gather operation: dispatch all agents in a SINGLE message with 5 parallel Agent tool calls, wait for all to return, then synthesize into the brief.

### Step 1: Dispatch (ONE message, FIVE parallel Agent calls)

```
Agent(subagent_type="domain-medical",  prompt="Run Medical SITREP for morning sweep. Return structured YAML.", run_in_background=true)
Agent(subagent_type="domain-finance",  prompt="Run Finance SITREP for morning sweep. Return structured YAML.", run_in_background=true)
Agent(subagent_type="domain-family",   prompt="Run Family SITREP for morning sweep. Include today's calendar and next 7 days.", run_in_background=true)
Agent(subagent_type="domain-security", prompt="Run Security SITREP for morning sweep. Check LaunchAgent health.", run_in_background=true)
Agent(subagent_type="domain-operations", prompt="Run Operations SITREP for morning sweep. Flag overdue items and battle rhythm status.", run_in_background=true)
```

**CRITICAL:** All 5 calls MUST be in a single message to execute in parallel. Sequential dispatch defeats the purpose.

### Step 2: Gather (wait for all agents, 60-second timeout)

Collect the structured YAML from each domain agent. If an agent times out or fails, note it in the brief as "[DOMAIN] — data unavailable" and continue.

### Step 3: Synthesize

Map domain agent outputs to the brief structure:
- **HEALTH OPS** ← domain-medical SITREP
- **PROTOCOL COMPLIANCE** ← domain-medical protocol_compliance section
- **FINANCIAL PULSE** ← domain-finance SITREP
- **FAMILY OPS** ← domain-family SITREP (today's events, dinner plan, kids)
- **EVOLUTION INTEL** ← check evolution-intel-latest.md directly (fast read, not an agent)
- **TOP 3 PRIORITIES** ← synthesize from all domain alerts + overdue items from domain-operations
- **TODAY'S TRUTH** ← the most uncomfortable finding across ALL domains
- **TONIGHT'S MISSION** ← from domain-family presence data + calendar

### Step 4: Also check (fast reads, not agents)
- MEMORY.md for time-sensitive items
- HISTORY.md last 3 entries for recent context

## Body Recomp Snapshot

Read `~/Documents/S6_COMMS_TECH/dashboard/recomp_data.json`:
- Current weight + 4-week trend direction
- Current BF% + 4-week trend direction
- Days since last progress photo
- Current protocol phase + days in phase
- Dashboard: http://localhost:8082/recomp.html

---

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

## Evolution Intelligence (check each run)

Read: `/Users/toryowens/Library/Mobile Documents/com~apple~CloudDocs/evolution-intel-latest.md`

If the file exists and was updated within the last 48 hours:
- Surface any Tier 1 auto-implemented changes as: "Changes made overnight — review recommended: [list]"
- Surface any Tier 2 items <72hrs old as: "FYI — Evolution Engine found: [list top 3 by score]"
- Surface any Tier 2 items >72hrs old as: "ACTION REQUIRED — pending review: [list]"
- If no changes or findings: "Evolution Engine: all quiet"

If the file is >48hrs old or missing:
- "Evolution Engine: no recent sweep (last: [date or 'never'])"

---

## LLY Holdings & Catalyst Watch

**Data Source:** `~/Documents/S6_COMMS_TECH/dashboard/invest_intel_data.json`

At each morning sweep invocation:

1. **Read invest_intel_data.json** and locate LLY in the watchlist/holdings section
2. **Report in the brief:**
   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━
   LLY HOLDINGS & CATALYSTS
   ━━━━━━━━━━━━━━━━━━━━━━━━
   LLY: $[price] ([+/-X.XX%] today | [+/-X.XX%] week)
   RSU Value: 22.552 shares x $[price] = $[total]
   Vested: 7.293 shares ($[value]) | Unvested: 15.259 shares ($[value])
   Catalysts: [status of each — see below]
   ```

3. **Movement Alert:** If LLY moves >5% in a single day (up or down), flag prominently at the TOP of the brief:
   ```
   *** LLY ALERT: [+/-X.XX%] ($XXX.XX) — [direction] move ***
   RSU impact: [+/-$X,XXX] on 22.552 shares
   ```

4. **Catalyst Monitoring (web search each run):**
   - Search: `"orfoglipron FDA"` OR `"orfoglipron approval"` — report any news from last 48 hours
   - Search: `"orfoglipron Phase 3"` OR `"orfoglipron trial results"` — report any clinical updates
   - Search: `"Iran sanctions"` OR `"Iran conflict"` + `"market"` — report geopolitical headlines that could impact pharma/defense sectors
   - If any catalyst has material news: elevate to TOP 3 PRIORITIES with recommended action (hold/monitor/review)

5. **Strategy Reminder:** Commander directive 3/19/26 — HOLD all LLY. Do NOT sell in current environment. Key upside catalysts: orfoglipron FDA approval, Iran conflict resolution.

6. **Budget Sentinel Integration:** If `~/Documents/S6_COMMS_TECH/dashboard/budget_alerts.json` exists, check its summary status and include in FINANCIAL PULSE:
   - GREEN: "Budget Sentinel: all clear"
   - AMBER: "Budget Sentinel: [count] warnings — [top alert message]"
   - RED: "Budget Sentinel: [count] CRITICAL — [top alert message]"

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
