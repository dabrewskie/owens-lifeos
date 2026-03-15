---
name: evolution-engine
description: >
  Self-improving intelligence layer for Tory Owens' Life OS. Dispatches 7 parallel
  domain scouts to scan the external world, evaluates findings against Tory's context,
  auto-implements low-risk upgrades (Tier 1), queues high-risk changes for review (Tier 2),
  and feeds intelligence into the COP, morning sweep, and sentinel engine.
  Triggers on: "Evolution sweep", "Run the evolution engine", "System evolution",
  "What's new out there", "Upgrade scan", "Intelligence sweep".
  Runs autonomously on schedule: Sunday 2000 + Wednesday 2000.
---

# Evolution Engine — System Intelligence & Continuous Improvement

**Mission:** Continuously scan the external world across 7 domains, evaluate findings against the Commander's specific context, and autonomously upgrade the Life OS — making every skill sharper, every protocol more evidence-based, and every data source more current.

**Standing Authority:** Tiered. Tier 1 changes auto-implement. Tier 2 changes queue for Commander review.

---

## Invocation Protocol

### Step 0: Determine Sweep Type
- If today is Sunday → "Sunday Full Sweep" (include "Week Ahead" section in briefing)
- If today is Wednesday → "Wednesday Mid-Week Sweep" (include "Delta Since Sunday" section)
- If manually invoked → "Ad-Hoc Sweep" (standard briefing)

### Step 1: Pre-Sweep Snapshot
Create a rollback point before any changes:
```bash
cd ~/owens-lifeos && git add -A && git commit -m "pre-evolution-snapshot $(date +%Y-%m-%d)" --allow-empty && git tag "pre-evolution-$(date +%Y-%m-%d)" -f
```

### Step 2: Load Context
Read the following to understand current system state:
- `/Users/toryowens/Library/Mobile Documents/com~apple~CloudDocs/COP.md` — operational state
- `/Users/toryowens/.claude/projects/-Users-toryowens/memory/MEMORY.md` — system reference
- `/Users/toryowens/Library/Mobile Documents/com~apple~CloudDocs/evolution-intel-latest.md` — prior briefing (if exists, for delta comparison and learning loop)
- `/Users/toryowens/Library/Mobile Documents/com~apple~CloudDocs/evolution-metrics.json` — cumulative metrics

### Step 3: Dispatch Scouts
Dispatch ALL 7 scouts in a **single message with 7 parallel Agent tool calls**.

**Primary method** (when scout agent types are registered — i.e., they existed before session start):
- `subagent_type` = the scout name (e.g., "evolution-scout-ai")
- `model` = "opus"
- `run_in_background` = true
- `prompt` = "Run your domain scan protocol. Today is [DATE]. Return your findings in the standardized format."

**Fallback method** (if scout agent types are not available — e.g., first session after creation):
- Use `subagent_type` = "general-purpose" for each scout
- `model` = "opus"
- `run_in_background` = true
- `prompt` = Read the scout's agent file at `~/.claude/agents/evolution-scout-[domain].md` and embed its FULL content as the prompt, followed by: "Run your domain scan protocol. Today is [DATE]. Return your findings in the standardized format."

Scouts to dispatch:
1. evolution-scout-ai
2. evolution-scout-health
3. evolution-scout-finance
4. evolution-scout-veteran
5. evolution-scout-parenting
6. evolution-scout-career
7. evolution-scout-systems

Wait for all scouts to return (or timeout at 10 minutes).

### Step 4: Assess Completion
Count how many scouts returned results:
- **4+ of 7:** Full sweep — proceed with Tier 1 auto-implementation
- **Fewer than 4:** Partial sweep — queue ALL findings as Tier 2 only, no auto-implementation
- Log any failed scouts with domain name and error type
- Update consecutive failure counters in evolution-metrics.json

### Step 5: Deduplicate
Compare findings across all scout reports:
- **URL match** across scouts = definite duplicate → merge, keep highest confidence
- **Title >80% token overlap** across scouts = probable duplicate → review and merge
- Cross-domain findings: merge target_skills lists, tag with both domain labels

### Step 6: Score Each Finding
For each unique finding, assign:
- **Impact (1-5):** How much does this affect Tory's mission, family, health, or finances?
- **Feasibility (1-5):** How easy to implement? (1=architecture change, 5=one-line edit)
- **Confidence (1-5):** Source quality. Map from scout rating: HIGH=5, MEDIUM=3, LOW=1

**Priority Score = Impact × Feasibility × Confidence** (max 125)
Discard findings scoring below 15.

### Step 7: Classify Tier 1 vs Tier 2
A finding is **Tier 1 (auto-implement)** ONLY if ALL of the following are true:
1. `diff_estimate` ≤ 20 lines
2. Change is ADDITIVE (does not remove or replace existing content)
3. Does NOT touch MEMORY.md
4. Does NOT touch skill core operating instructions (only source lists, search terms, data references)
5. Does NOT touch COP sections other than Evolution Engine running estimate
6. The relevant domain's scout completed successfully
7. The sweep achieved minimum completion threshold (4/7)

Everything else is **Tier 2 (approval required)**.

### Step 8: Auto-Implement Tier 1 Changes
For each Tier 1 finding:
1. Read the target file
2. Make the additive change (append to source list, add data reference, etc.)
3. Log the exact diff (before/after) for the briefing

### Step 9: Push Tier 2 to Notion
For each Tier 2 finding, create a row in the Evolution Upgrade Queue database using the Notion MCP tools:
- Title: finding title
- Domain: scout domain (select: AI/Agent, Health, Financial, Veteran, Parenting, Career, Systems)
- Tier: "Approval Required"
- Status: "Proposed"
- Confidence: scout rating (HIGH, MEDIUM, LOW)
- Score: calculated priority score
- Target Skills: from finding
- Evidence URL: source URL
- Summary: finding summary + relevance
- Suggested Action: from finding
- Found Date: today

Also log Tier 1 auto-implemented changes to Notion with Tier: "Auto-Implemented", Status: "Implemented", Implemented Date: today.

### Step 10: Write iCloud Briefing
Write to: `/Users/toryowens/Library/Mobile Documents/com~apple~CloudDocs/evolution-intel-latest.md`

```markdown
# Evolution Intelligence Brief — [DATE]
## Sweep Type: [Sunday Full / Wednesday Mid-Week / Ad-Hoc]
## Completion: [N]/7 scouts returned | [Full/Partial] sweep

## Auto-Implemented Changes (Tier 1)
[For each: title, target skill, what was changed, evidence link, diff]
[If none: "No Tier 1 changes this cycle"]

## Awaiting Commander Review (Tier 2)
[Ranked by score. For each: title, domain, score, summary, suggested action, evidence link]
[If none: "No Tier 2 items this cycle"]

## Domain Highlights
### AI/Agent Architecture
[Top finding or "No actionable findings"]
### Health Optimization
[Top finding or "No actionable findings"]
### Financial/Market
[Top finding or "No actionable findings"]
### Veteran/Military
[Top finding or "No actionable findings"]
### Parenting/ADHD
[Top finding or "No actionable findings"]
### Leadership/Career
[Top finding or "No actionable findings"]
### Productivity/Systems
[Top finding or "No actionable findings"]

## Scout Failures
[Any scouts that failed, with error type]
[If none: "All scouts completed successfully"]

## [Week Ahead | Delta Since Sunday | Standard] (sweep-type dependent)
[Sunday: findings relevant to upcoming week events/deadlines]
[Wednesday: what changed since Sunday's sweep, fast-moving signals]
[Ad-Hoc: standard summary]

## Learning Loop Metrics
- Tier 1 changes this cycle: [N]
- Tier 2 items queued: [N]
- Tier 2 items pending from prior cycles: [N]
- Scout completion: [N]/7
- Source signal quality: [domain → HIGH/MED/LOW based on findings-to-searches ratio]
- Cumulative system upgrades (all time): [N]
```

### Step 11: Update COP
Read `/Users/toryowens/Library/Mobile Documents/com~apple~CloudDocs/COP.md`.
Find or create the `### Evolution Engine` section under STAFF RUNNING ESTIMATES and update:

```markdown
### Evolution Engine
**Last Sweep:** [DATE] — [Sunday Full / Wednesday Mid-Week / Ad-Hoc]
**System Upgrades This Month:** [count]
**Pending Tier 2 Items:** [count]
**Top Signal This Cycle:** [one-liner — highest-scoring finding]
**Domain Health:** AI [GREEN/AMBER/RED] | Health [status] | Finance [status] | Veteran [status] | Parenting [status] | Career [status] | Systems [status]
**Learning Loop:** [which domains producing actionable intel vs plateauing]
```

Domain Health:
- GREEN = scout completed + produced actionable findings
- AMBER = scout completed + no actionable findings
- RED = scout failed

### Step 12: Post-Sweep Commit
```bash
cd ~/owens-lifeos && git add -A && git commit -m "evolution-engine sweep $(date +%Y-%m-%d) — [N] Tier 1 changes applied"
```

### Step 13: Update Metrics & Failure Tracking
Read `/Users/toryowens/Library/Mobile Documents/com~apple~CloudDocs/evolution-metrics.json`.
Update:
- Increment `total_sweeps`
- Add to `total_tier1_implementations`, `total_tier2_proposed`
- Update `domain_findings_count` per domain
- Update `domain_consecutive_failures` (reset to 0 on success, increment on failure)
- Append to `sweep_history` (keep last 20 entries):
  ```json
  {"date": "YYYY-MM-DD", "type": "sunday/wednesday/adhoc", "scouts_completed": N, "tier1_count": N, "tier2_count": N}
  ```

If any scout has 2+ consecutive failures, add warning to the briefing.
If any scout has 3+ consecutive failures, flag for system-optimizer review in the COP section.

Write the updated metrics file.

---

## Rollback Procedure

If Commander says "Roll back the last evolution sweep" or "Undo evolution changes":
1. Find most recent tag: `git tag -l 'pre-evolution-*' | sort -r | head -1`
2. Restore: `cd ~/owens-lifeos && git checkout [tag] -- . && git commit -m "Rollback evolution sweep [date]"`
3. Update any Notion rows for that sweep's Tier 1 changes to Status: "Rolled Back"
4. Update COP Evolution Engine section to reflect rollback
5. Report what was rolled back

---

## Integration Notes
- **Morning sweep** reads `evolution-intel-latest.md` and surfaces Tier 1 changes as "Changes made overnight — review recommended" and Tier 2 items with age-based escalation
- **Sentinel engine** reads COP Evolution Engine section for cascade analysis signals
- **System optimizer** uses evolution data to track skill improvement trends
- **Weekly assessment** includes evolution metrics in Friday scorecard
