---
name: family
description: >
  Family check, Kids, Rylan, Emory, Harlan, Lindsey, Calendar check,
  Week ahead, Am I overbooked, Am I okay, How am I really doing,
  Check on me, Guardian protocol.
  Unified family operations covering per-child tracking, calendar intelligence,
  spouse coordination, and behavioral monitoring for the whole Owens family.
---

# Family — Mission Priority One

Consolidates: family-ops, kid-tracker, calendar-intel, guardian-protocol

**Sub-mode detection:** Match user intent:
- "Family check", "Lindsey" → **check**
- "Kids", "Rylan", "Emory", "Harlan" → **kids**
- "Calendar check", "Week ahead", "Am I overbooked" → **calendar**
- "Am I okay", "How am I really doing", "Check on me", "Guardian protocol" → **guardian**

## Standing Orders
1. **Family First** — family needs override convenience. Always.
2. **Track per-child** — never group the kids. Each child is a unique mission with unique needs.
3. **Presence data matters** — quality time logged is a metric. Track it.

## Family Roster
| Member | Age | Notes |
|--------|-----|-------|
| Lindsey | — | Spouse. Marriage is the foundation. |
| Rylan | 14 | BOY. ADHD. Adderall + Fluoxetine. Needs structure + patience. |
| Emory | 7 | Growing fast. Track school, social, activities. |
| Harlan | 3 | Toddler. Track development milestones. |

## Sub-Mode: check
### Procedure
1. Pull COP S1 (Personnel/Family) section.
2. Surface current family status — any open issues, upcoming events, needs.
3. Check spouse coordination — date nights scheduled? Marriage maintenance on track?
4. Assess family tempo — are we running too hot or appropriately balanced?
5. Flag anything that needs Commander attention.
### Output Format
- Family status BLUF
- Per-member status
- Upcoming family events
- Action items

## Sub-Mode: kids
### Procedure
1. Pull per-child data from COP and HISTORY.md.
2. For each child (or specified child):
   - School/development status
   - Medical/behavioral notes (especially Rylan: ADHD management, medication effectiveness)
   - Activities and commitments
   - Quality time logged recently
   - Any concerns or wins to celebrate
3. Surface per-child recommendations.
### Output Format
- Per-child status card
- Medication/behavioral tracking (Rylan)
- Development milestones (Harlan)
- Recommendations

## Sub-Mode: calendar
### Procedure
1. Pull Google Calendar data for requested period (default: next 7 days).
2. Categorize events: work, family, personal, medical, recurring.
3. Calculate schedule density — flag overbooked days (> 6 hours committed).
4. Check for conflicts or double-bookings.
5. Identify family time blocks — are they protected?
6. Surface prep needed for upcoming events.
### Output Format
- Week-ahead calendar summary
- Density assessment
- Conflict flags
- Family time check
- Prep requirements

## Sub-Mode: guardian
### Procedure
1. This is a welfare check on Commander. Treat it seriously.
2. Aggregate signals: sleep trends, stress indicators, calendar density, workout compliance.
3. Check for burnout indicators: skipped workouts, poor sleep streak, calendar overload.
4. Review therapy cadence and social connection.
5. Assess work-life balance honestly.
6. Deliver truth — not comfort. But deliver it with respect.
### Output Format
- Honest welfare assessment
- Signal inventory (what the data says)
- Risk flags
- Specific recommendations (not platitudes)
- "Commander, here's what I see..."

## Shared Data Sources
- `~/Library/Mobile Documents/com~apple~CloudDocs/COP.md` (S1 section)
- `~/Documents/S6_COMMS_TECH/data/HISTORY.md`
- Google Calendar (via MCP)
