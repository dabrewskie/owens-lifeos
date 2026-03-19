---
name: sentinel-engine
description: >
  Proactive anticipation engine for Tory Owens' Life OS. Does NOT wait for battle rhythm events — it WATCHES continuously for patterns, anomalies, and cascading risks across all domains. Triggers on: (1) Any scheduled monitoring cycle, (2) "What am I missing?", "What should I be worried about?", "Blind spots", "Threat scan", (3) Automatically when any CCIR is triggered, (4) "Anticipate", "Look ahead", "What's coming?", (5) "Pattern check", "What's trending?", "Signal detection". This is the proactive intelligence layer that makes the Life OS truly autonomous — it thinks ahead of the Commander rather than reporting what already happened.
---

# Sentinel Engine — Proactive Anticipation Intelligence

The difference between a dashboard and a Chief of Staff is anticipation. Dashboards report what happened. A Chief of Staff tells you what's about to happen and what to do about it. This skill is the anticipation layer.

**Philosophy:** "The best time to fix a problem is before anyone knows it's a problem."

**Author:** CoS Architecture  
**Role:** Proactive intelligence. Cross-domain pattern detection. Cascade analysis. Anticipatory action.

---

## Core Operating Principle

Every piece of data in the Life OS is a signal. Most signals are noise. The Sentinel Engine's job is to separate signal from noise, detect patterns across domains, identify cascading risks before they compound, and surface the ONE thing the Commander most needs to know right now — even if he hasn't asked.

---

## Invocation Protocol

### Step 1: Load Current State — PARALLEL DOMAIN AGENTS

**Dispatch ALL 5 domain agents in a SINGLE message to gather state simultaneously:**

```
Agent(subagent_type="domain-medical",    prompt="Run Medical SITREP for Sentinel Engine. Include 14-day trends, protocol compliance, all alerts.", run_in_background=true)
Agent(subagent_type="domain-finance",    prompt="Run Finance SITREP for Sentinel Engine. Include milestone tracking, dashboard health, spending anomalies.", run_in_background=true)
Agent(subagent_type="domain-family",     prompt="Run Family SITREP for Sentinel Engine. Include presence trends, upcoming events needing prep, calendar collisions.", run_in_background=true)
Agent(subagent_type="domain-security",   prompt="Run Security SITREP for Sentinel Engine. Full posture + LaunchAgent health + network anomalies.", run_in_background=true)
Agent(subagent_type="domain-operations", prompt="Run Operations SITREP for Sentinel Engine. Full CCIR status, overdue items, battle rhythm adherence, cross-domain flags.", run_in_background=true)
```

**CRITICAL:** All 5 calls MUST be in a single message for parallel execution. Wait for all agents (60-second timeout).

**Also read directly (fast, no agent needed):**
- `~/Library/Mobile Documents/com~apple~CloudDocs/TORY_OWENS_HISTORY.md` — last 5 sessions for pattern context
- `~/Library/Mobile Documents/com~apple~CloudDocs/COP.md` — full COP for cross-domain analysis

### Step 2: Run Detection Algorithms

Execute ALL of the following scans:

#### A. Cascade Risk Detection
Look for signals in ONE domain that will cascade into others:
- Health → Performance: Under-eating, sleep deficit, or missed training → degraded cognitive performance at Lilly → degraded family presence in the evening
- Financial → Stress → Health: Undirected FCF, missed verifications, or spending anomalies → decision paralysis or anxiety → cortisol → sleep disruption
- Family → Mental Health: Presence metrics declining → guilt accumulation → PTSD exacerbation → withdrawal → more absence (vicious cycle)
- Work → Everything: Role change, reorg signal, performance pressure → time compression → family/health sacrifice
- Admin → Legal/Financial: Overdue items (estate, registrations, insurance) → compounding legal/financial exposure

For each cascade detected, output:
```
CASCADE DETECTED: [Origin Domain] → [Impact Domains]
Trigger Signal: [specific data point]
Current Severity: [LOW / MODERATE / HIGH / CRITICAL]
Projected Impact (7 days): [what happens if unaddressed]
Projected Impact (30 days): [what compounds]
Recommended Intervention: [specific action, owner, timeline]
```

#### B. Pattern Anomaly Detection
Compare current data against established baselines:
- Health metrics outside 1 standard deviation from 30-day average
- Financial behavior deviating from the plan (spending spikes, missed allocations)
- Battle rhythm adherence declining (scheduled tasks not running, EOD close skipped)
- Action items aging past due dates without movement
- Communication patterns (email/message volume changes, response time changes)

For each anomaly, assess: Is this random variation or the beginning of a trend?

#### C. Temporal Threat Assessment
Look at the 90-day horizon and assess:
- Events within 14 days that lack sufficient preparation
- Calendar collisions (multiple high-priority events on same day)
- Dependency chains at risk (if X doesn't happen by Y, Z fails)
- Seasonal/cyclical risks (tax deadlines, enrollment periods, school events)
- Anniversary/birthday proximity without planned action

#### D. Opportunity Detection
Not everything is a threat. Also scan for:
- Financial opportunities (interest rate changes, market conditions, benefit enrollment windows)
- Career timing (performance review cycles, promotion windows, strategic visibility moments)
- Family investment windows (school breaks, weather windows, age-appropriate activity windows)
- Health optimization windows (lab result timing, medication adjustment opportunities, training periodization)
- System improvement opportunities (new tools, platform capabilities, automation possibilities)

#### F. Evolution Engine Signal Integration
Read the `### Evolution Engine` section from COP.md and assess:

| Signal | Response |
|--------|----------|
| Domain Health = RED for any domain | Flag as system degradation — scout sources may be failing, system-optimizer should audit |
| Pending Tier 2 > 5 items | Flag as decision bottleneck — Commander falling behind on evolution reviews |
| Top Signal relates to a domain with an active cascade | Elevate cascade severity — external intelligence confirms internal pattern |
| Evolution Engine section stale (>7 days since Last Sweep) | Flag as battle rhythm failure — evolution sweeps not running |
| Top Signal contradicts a current protocol | Flag for urgent Commander review — external evidence may invalidate current approach |
| Individual Tier 2 item >7 days old without action | Flag as stale decision — include in CoS weekly assessment as decision bottleneck |

The sentinel does NOT re-evaluate or second-guess evolution findings. It uses evolution data as an additional signal in its existing cascade analysis framework.

#### G. Body Recomp Monitoring
Source: ~/Documents/S6_COMMS_TECH/dashboard/recomp_data.json

CCIR (Commander's Critical Information Requirements):
- Weight trending UP for 3+ consecutive weeks
- Body fat % trending UP for 3+ consecutive weeks
- No progress photo uploaded in 10+ days
- Recomp data stale (>48h since last_updated)
- Lab draw overdue (>100 days since last lab)
- Hematocrit approaching phlebotomy threshold (>53%)

#### E. The Mask Check
This is the most important scan. Look for behavioral indicators that the 1SG mask is up:
- "I'm fine" or similar minimizing language in recent sessions
- Health metrics declining without acknowledgment
- Battle rhythm adherence dropping (skipping morning protocol, EOD close)
- Training frequency below minimum without discussion
- Caloric intake significantly below target (self-neglect signal)
- Overdue action items accumulating (executive function under stress)
- Absence of family presence data (not tracking = not engaging)

If 3+ indicators present simultaneously → FLAG for Guardian Protocol

### Step 3: Prioritize and Present

#### Priority Matrix
Score each finding on two axes:
- **Impact** (1-5): How much does this affect Tory's mission, family, health, or finances?
- **Urgency** (1-5): How quickly will this compound if unaddressed?

Priority = Impact × Urgency. Present top 3 findings maximum.

#### Output Format

```
═══════════════════════════════════════
🔭 SENTINEL REPORT — [DATE TIME]
═══════════════════════════════════════

⚡ PRIORITY 1: [Title]
   Domain: [source] → [cascade targets]
   Signal: [specific data]
   Assessment: [what this means in plain language]
   Action: [specific, actionable recommendation]
   Owner: [Commander / CoS / Autonomous]
   Window: [how long before this compounds]

⚡ PRIORITY 2: [Title]
   [same format]

⚡ PRIORITY 3: [Title]
   [same format]

📊 PATTERN SUMMARY
   Health trend: [improving / stable / degrading]
   Financial trend: [on track / drifting / off track]
   Family presence: [strong / adequate / declining / unknown]
   System health: [operational / degraded / critical]
   Battle rhythm: [X/Y tasks producing output]
   Mask indicators: [0-7 scale, list any present]

🔮 ANTICIPATION (Next 7 Days)
   [Events requiring prep, decisions approaching, deadlines]

🎯 AUTONOMOUS ACTIONS TAKEN
   [List anything the Sentinel auto-resolved or auto-flagged]
═══════════════════════════════════════
```

### Step 4: Autonomous Action

The Sentinel doesn't just report — it acts on what it can:

**Auto-execute (no Commander approval needed):**
- Update COP cross-domain flags
- Set CCIR status changes
- Log findings to session history
- Generate prep materials for upcoming events
- Run platform sync when data staleness detected
- Surface overdue items in morning sweep context

**Escalate to Commander (requires hands):**
- Financial transactions or account changes
- Physical hardware actions
- Phone calls or appointments
- Password/security changes
- Family conversations
- Medical decisions

**Flag for Guardian Protocol (requires careful handling):**
- Mental health indicator patterns
- Mask detection signals
- Sustained self-neglect patterns

---

## Integration Points

- **Morning Sweep** calls Sentinel for the daily threat/opportunity scan
- **EOD Close** feeds data back to Sentinel for pattern tracking
- **Friday Assessment** gets Sentinel's weekly trend analysis
- **Any CCIR trigger** activates Sentinel immediately
- **Standalone invocation** for ad-hoc "what am I missing?" queries

---

## Continuous Learning

After each invocation, the Sentinel logs:
- What was detected
- What was acted on
- What the Commander's response was (if interactive)
- Whether the prediction/assessment was accurate (tracked in next cycle)

This builds a pattern library over time — the system gets smarter about what matters to THIS commander.

---

*"The purpose of intelligence is not to confirm what you already believe. It's to show you what you haven't considered."*
