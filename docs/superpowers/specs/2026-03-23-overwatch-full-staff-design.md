# OverwatchTDO Full Staff Architecture — Design Spec

**Date:** 2026-03-23
**Author:** Claude (Opus 4.6) + Commander Tory Owens
**Status:** APPROVED — executing

## Vision

OverwatchTDO becomes a true command structure with 21 agents across 4 tiers. The system gives Tory the combined capabilities of a personal board of advisors, concierge medical practice, wealth management team, executive coach, research department, and family conscience — all running autonomously, all learning, all compounding.

## Architecture: Hub-and-Spoke with Standing Patrols

Overwatch is the synthesizer of intelligence that's already flowing. Standing patrols run before his scheduled briefs, feeding pre-gathered intelligence. On-demand agents are dispatched when Overwatch identifies a need during his runs.

## Agent Roster (21 Total)

### Tier 1: Operations Staff (keep the machine running)

| Agent | Model | Schedule | Purpose |
|-------|-------|----------|---------|
| `qrf-repair` (v2) | Sonnet | On task failure + Overwatch dispatch | Expanded self-healing with cascade awareness, repair playbook, post-repair verification |
| `evolution-engine` (v2) | Sonnet (daily) / Opus (weekly) | Daily 2300 + Sunday 1800 + on demand | Dual-track learning (system + life), knowledge synthesis, anticipation rule generation |
| `pulse-monitor` | Haiku | Every 4h (0200,0600,1000,1400,1800,2200) | Watches the watchers — orchestrator health, Overwatch run verification, disk/service checks |
| `domain-security` | Haiku | On Overwatch dispatch | IT/infra health (unchanged) |

### Tier 2: Intelligence Staff (know what's true)

| Agent | Model | Schedule | Purpose |
|-------|-------|----------|---------|
| `deep-researcher` | Opus | On demand | Evidence-based research with PubMed/bioRxiv/ClinicalTrials/ChEMBL/web + iCloud archiving |
| `simulation-engine` | Opus | On demand | Predictive modeling for life decisions — financial, career, health, family scenarios |
| `pattern-prophet` | Sonnet | Daily 1930 | Trend extrapolation + threshold prediction on Tory's life data |
| `opportunity-hunter` | Sonnet | Daily 0525 | Proactive scanning for benefits, career, financial, family opportunities |
| `life-horizon-scanner` | Sonnet | Daily 0500 | Life-stage event awareness — developmental milestones, birthdays, deadlines, RPED countdown |
| `domain-medical` | Haiku | On Overwatch dispatch | Health data pull (unchanged) |
| `domain-finance` | Haiku | On Overwatch dispatch | Financial data pull (unchanged) |
| `domain-family` | Haiku | On Overwatch dispatch | Calendar/presence data (unchanged) |
| `domain-operations` | Haiku | On Overwatch dispatch | Tasks/deadlines (unchanged) |

### Tier 3: Coaching Staff (develop the man)

| Agent | Model | Schedule | Purpose |
|-------|-------|----------|---------|
| `accountability-tracker` | Sonnet | Daily 1900 | Recommendation follow-through measurement, time-to-action tracking |
| `relationship-intel` | Sonnet | Daily 0515 | Bond health monitoring — date nights, 1-on-1 time, mention frequency, coaching homework |
| `comms-prep` | Sonnet | On demand | Conversation preparation — framing, emotional landmines, timing, ISTJ communication coaching |
| `narrative-engine` | Sonnet | On demand (milestone detected) | Story arc capture — milestone documentation, transformation timeline |
| `devils-advocate` | Opus | After every Overwatch brief draft | Challenges Overwatch's conclusions — reads brief cold with no history context |

### Tier 4: Protection & Legacy (guard the family, build the story)

| Agent | Model | Schedule | Purpose |
|-------|-------|----------|---------|
| `shield-agent` | Sonnet | Wednesday 0600 | Family protection audit — insurance, estate docs, beneficiaries, benefits verification |
| `network-cartographer` | Sonnet | Monday 0600 | Career network mapping — VP sponsors, ERGs, LinkedIn, conference opportunities |
| `legacy-builder` | Sonnet | Friday 1900 | Tangible artifacts — letters to kids, family timelines, annual summaries, book material |

## Daily Battle Rhythm

```
0200  pulse-monitor (Haiku)
0500  life-horizon-scanner (Sonnet)
0515  relationship-intel (Sonnet)
0525  opportunity-hunter (Sonnet)
0530  OVERWATCH MORNING (Sonnet) — reads all feeds, dispatches as needed
0600  pulse-monitor (Haiku)
0630  health_dashboard (existing)
0645  recovery_score (existing)
...   existing orchestrator schedule
1000  pulse-monitor (Haiku)
1200  OVERWATCH MIDDAY (Sonnet) — course correction
1400  pulse-monitor (Haiku)
1800  pulse-monitor (Haiku)
1900  accountability-tracker (Sonnet)
1930  pattern-prophet (Sonnet)
2000  OVERWATCH EVENING (Sonnet) — close the loop
2200  pulse-monitor (Haiku)
2300  evolution-engine daily (Sonnet)
```

Weekly: Evolution Engine life learning (Sun 1800), Network Cartographer (Mon 0600), Shield Agent (Wed 0600), Legacy Builder (Fri 1900)

## Overwatch Execution Protocol v2

### PHASE 1 — GATHER
Read pre-gathered intelligence (standing patrol outputs). Dispatch domain agents in parallel only if data is stale (>4h).

### PHASE 2 — THINK
Synthesize all inputs. Draft brief using The Arc, The Intersection, The Silence, The Challenge, The Continuity, The Horizon.

### PHASE 3 — CHALLENGE
Dispatch devils-advocate with draft. Agent reads cold — no journal, no state. Returns critique. Overwatch integrates or rejects with reasoning.

### PHASE 4 — ACT
Dispatch agents based on findings: qrf-repair (faults), deep-researcher (knowledge gaps), narrative-engine (milestones), comms-prep (conversations), simulation-engine (decisions).

### PHASE 5 — PUBLISH
Write brief, journal, state. Alert if critical.

### PHASE 6 — LEARN
Log dispatches and findings. Escalate aged accountability items. Flag threshold crossings.

## Alert Classification

- **LEVEL 4 FLASH** — Immediate iMessage. Safety, system cascade failure, 2+ missed Overwatch runs.
- **LEVEL 3 PRIORITY** — Hourly batched iMessage. Ignored recommendations 5+ days, bond RED, time-sensitive opportunities, recurring failures.
- **LEVEL 2 ROUTINE** — Next Overwatch brief. Aging items, AMBER metrics, improvements implemented.
- **LEVEL 1 LOG** — Agent output file only. Nominal status, minor fixes, routine captures.

Quiet hours: 2200-0500 (PRIORITY holds, FLASH still sends).

## Silence Detection Protocol

The system watches for absence of expected signal:
- No Lindsey mentions 7+ days
- No kid 1-on-1 logged 14+ days per child
- Date night frequency below 1x/2 weeks
- Commander system absence 48+ hours
- No health export 3+ days
- No workout 7+ days
- No nutrition tracking 3+ days
- Commander absence >72 hours → FLASH

## Inter-Agent Communication

All communication via files (standing patrols) or dispatch returns (on-demand). Key feed patterns:
- QRF repair log → Evolution Engine (learning loop)
- Evolution Engine → Anticipation Engine rules + Overwatch prompt updates (teaching loop)
- Deep Researcher archive → Evolution Engine (knowledge synthesis on 3+ new files)
- Accountability Tracker → Overwatch (escalation loop)
- Pattern Prophet → Overwatch + Shield Agent (risk awareness)
- Relationship Intel → Overwatch + Comms Prep (bond health → conversation preparation)

## Freshness Protocol

- <4h: FRESH | 4-12h: STALE | 12-24h: DEGRADED (re-dispatch) | >24h: EXPIRED
- Weekly agents: 8-day freshness window

## New Data Files

All in `~/Documents/S6_COMMS_TECH/dashboard/`:
- `life_horizons.json`, `relationship_intel.json`, `accountability_report.json`
- `pattern_prophet_output.json`, `opportunities.json`, `pulse_status.json`
- `qrf_repair_log.json`, `narrative_arc.json`, `network_map.json`, `shield_status.json`
- `alert_history.json`

Research archive: `~/Library/Mobile Documents/com~apple~CloudDocs/RESEARCH_ARCHIVE/`

## Estimated Cost

~$50-80/month for full autonomous operation (~38 agent runs/day).

## Implementation Sequence

1. Write all 14 new/redesigned agent files
2. Update overwatch-tdo.md with v2 execution protocol and full staff roster
3. Add orchestrator tasks for standing patrols
4. Create symlinks for new agents
5. Create RESEARCH_ARCHIVE directory
6. Update MEMORY.md with new architecture
7. Push to GitHub
