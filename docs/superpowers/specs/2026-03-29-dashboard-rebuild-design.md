# Life OS Dashboard Rebuild — Priority-First Command Interface

**Date:** 2026-03-29
**Status:** Approved
**Author:** OverwatchTDO + Commander
**Scope:** Full dashboard rebuild with card-based action system, unified API, MCP Apps integration

---

## Problem Statement

The current dashboard is a **display layer** — it shows data across 6 tabs and 12 standalone HTML pages, but provides zero ability to act. The Commander must scan each domain manually (he is the trigger), context-switch to Formation or Claude Code to take action (he is the bottleneck), and has no way to close the loop from the dashboard itself (no feedback). 21 agents generate intelligence into 10+ separate JSON files that the Commander must mentally fuse.

**Core issues:**
1. Tabs organize by domain, but attention should be organized by priority
2. Cards show information but don't tell you what to DO
3. No write-back — every action requires leaving the dashboard
4. 12 fragmented HTML files with no unified navigation
5. 40+ JSON files with no fusion layer
6. Commander is the scanner, trigger, and closer for every finding

## Design Principles

1. **Priority over domain** — show what matters most, regardless of which domain it's in
2. **Actionable by default** — every card has numbered steps and action buttons
3. **Self-closing** — cards auto-resolve when the system confirms the condition is met
4. **Two surfaces, one system** — dashboard (desktop/mobile) and MCP Apps (Claude conversations) share the same data and action model
5. **Graceful degradation** — if any component fails, fall back to the next-best rendering
6. **The stack gets shorter as you act** — not longer as data accumulates

## Architecture Overview

### The Stack (Priority Queue)

The landing view is a single vertically-ordered list of **Action Cards**, ranked by priority score. The system (Overwatch, Anticipation Engine, standing patrols) generates prioritized findings. The Stack renders them in order.

**Vitals strip** (always visible, 6 KPIs max):
- Net Worth | FCF/mo | Weight | Protein 7d | Recovery Score | Open Actions

**Filter bar** (horizontal, not tabs):
- All | Money | Health | Family | Career | System | Resolved

Filters narrow The Stack. "All" is always default. "Resolved" shows today's closed cards.

**Empty state:** "All clear. Next Overwatch brief at [time]."

### Card State Machine

Every card follows:

```
DETECT -> INFORM -> ACT -> CONFIRM -> CLOSE
```

- **DETECT:** System identifies a finding (patrol output, threshold breach, deadline)
- **INFORM:** Card appears with context + why it matters + numbered steps
- **ACT:** Commander taps Done / Defer / Dismiss / Execute
- **CONFIRM:** System verifies action (remediation tracker, data threshold check)
- **CLOSE:** Card auto-removes or moves to Resolved history

### Responsive Layout

**Mobile (<768px):**
- Vitals: 3 per row, scrollable
- Stack: full-width cards, swipe gestures (left=dismiss, right=done)
- Drill-down: inline expand below card
- Filter: horizontally scrollable chips

**Desktop (>1024px):**
- Vitals: 6 across
- Stack: left 60% of viewport
- Drill-down: right 40% sticky side panel
- Filter: all visible, keyboard shortcuts (1-6 for domains)

---

## Data Model

### Card Schema (`action_queue.json`)

```json
{
  "cards": [
    {
      "id": "card_20260329_protein_gap",
      "created": "2026-03-29T06:45:00Z",
      "source": "anticipation_engine",
      "domain": "health",
      "priority": 2,
      "state": "active",
      "headline": "Protein at 56% of target yesterday",
      "why": "Chronic deficit impairs recovery and muscle retention during recomp",
      "steps": [
        "Add protein shake with lunch (40g)",
        "Log all meals in Cronometer today",
        "Target 70g+ by 3pm checkpoint"
      ],
      "actions": {
        "done": { "label": "Logged & on track", "writes_to": "pending_actions" },
        "defer": { "label": "Defer", "default_hours": 4 },
        "dismiss": { "label": "Not today", "reason_required": false }
      },
      "drill_down": {
        "type": "nutrition_detail",
        "data_source": "health/health_data.json",
        "path": "macros"
      },
      "auto_close": {
        "condition": "health.macros.protein.current >= 180",
        "check_source": "health/health_data.json"
      },
      "deferred_until": null,
      "deferred_count": 0,
      "resolved_at": null,
      "resolved_by": null
    }
  ],
  "meta": {
    "last_generated": "2026-03-29T06:45:00Z",
    "total_active": 7,
    "total_resolved_today": 3
  }
}
```

### Card Step Generation

Every card promises numbered, specific, actionable steps. Two mechanisms, phased:

**Phase 2 (ship): Step templates.** The card generator contains a template library mapping ~30 known signal types to step templates with variable substitution. Example:

```python
STEP_TEMPLATES = {
    "protein_gap": [
        "Add protein shake with lunch ({deficit_half}g)",
        "Log all meals in Cronometer today",
        "Target {checkpoint_target}g by 3pm checkpoint"
    ],
    "budget_overage": [
        "Review {category} transactions in Rocket Money",
        "Identify top 3 discretionary charges to cut or defer",
        "Freeze {category} spending for remainder of month if over by >10%"
    ],
    ...
}
```

Templates cover the known recurring signals. Novel findings (new Overwatch concerns, one-off opportunities) get a generic 2-step template: "1. Review details in drill-down panel 2. Take action or dismiss."

**Phase 5 (mature): Agent-generated steps.** Update each patrol agent to output a `steps` array in their findings. Agents have domain context to write better steps than templates. Card generator passes agent-generated steps through when present, falls back to templates when absent. Gradual migration — agents adopt the schema one at a time.

### Card Generation Pipeline

| Source | Generates | Default Priority |
|--------|-----------|-----------------|
| Anticipation Engine | Pattern detections, threshold breaches, upcoming deadlines | 1-3 |
| Overwatch briefs (3x/day) | Recommendations, concerns, challenges | 1-4 |
| Standing patrols (continuous) | Accountability, relationship flags, horizon events, opportunities | 2-5 |
| Budget sentinel | Spending alerts, category overages | 1-3 |
| Health pipeline | Recovery score actions, nutrition gaps, sleep flags | 1-4 |
| Remediation tracker | Confirmed fixes (auto-close other cards) | N/A |

### Priority Scoring (1-5)

- **1 — FLASH:** Safety, cascade failure, financial breach, health emergency
- **2 — ACT TODAY:** Overdue items, budget overage, chronic health gap, deadline within 48h
- **3 — ACT THIS WEEK:** Deferred items returning, patrol findings, optimization opportunities
- **4 — AWARENESS:** Trend observations, coaching points, horizon items 30+ days
- **5 — RESOLVED:** Auto-closed or user-closed, Resolved filter only

**Escalation factors:**
- Age > 48h and still active: priority -= 1 (more urgent)
- Deferred 2+ times: priority -= 1 (avoidance pattern)
- Overwatch flagged specifically: priority -= 1

**De-escalation:**
- Auto-close condition >80% met: priority += 1 (nearly resolving itself)

### Card Deduplication & Merging

- Deterministic IDs: `card_{date}_{source}_{signal_hash}`
- Same ID regenerated: update existing card, don't duplicate
- Related cards (3 protein alerts from different sources): merge into one consolidated card with combined steps
- Hard cap: 30 active cards max. Overflow to `card_overflow.json` for audit.

### Files Absorbed

| Current File | Absorbed Into |
|---|---|
| `pending_actions.json` | `action_queue.json` cards with state tracking |
| `alert_history.json` | `action_queue.json` resolved cards + `card_history.json` archive |
| `accountability_report.json` | Generated from card response patterns |
| `budget_alerts.json` | Cards generated by budget_sentinel |
| `life_horizons.json` | Cards generated by horizon-scanner |
| `opportunities.json` | Cards generated by opportunity-hunter |
| `relationship_intel.json` | Cards generated by relationship-intel |

Patrol output files still exist (agents still write to them). Card generator reads and fuses.

---

## UI Components

### Tech Stack

Vanilla HTML/JS/CSS with Web Components. No framework, no build step, no node_modules.

### File Structure

```
dashboard/
  index.html              <- shell: header, vitals, filter bar, containers
  css/
    tokens.css            <- design tokens (colors, spacing, typography)
    layout.css            <- grid, responsive breakpoints, side panel
    cards.css             <- card states, priority edges, animations
  js/
    engine.js             <- data loading, polling, card generator client
    cards.js              <- card rendering, state machine, action handlers
    drill-down.js         <- side panel / expand content renderers
    vitals.js             <- KPI strip logic
    mcp-client.js         <- MCP HTTP write-back
  components/
    action-card.js        <- Web Component: <action-card>
    vitals-strip.js       <- Web Component: <vitals-strip>
    drill-panel.js        <- Web Component: <drill-panel>
    progress-ring.js      <- Web Component: <progress-ring>
```

### Action Card Visual Design

```
+-----------------------------------------------------+
|# Protein at 56% of target yesterday       [Health]  |  <- priority edge + badge
|                                                       |
|  Chronic deficit impairs recovery and muscle          |  <- why
|  retention during recomp                              |
|                                                       |
|  +- STEPS ----------------------------------------+  |
|  | 1. Add protein shake with lunch (40g)          |  |  <- numbered steps
|  | 2. Log all meals in Cronometer today           |  |
|  | 3. Target 70g+ by 3pm checkpoint               |  |
|  +------------------------------------------------+  |
|                                                       |
|  [ Done ]  [ Defer v ]  [ Dismiss ]                   |  <- action buttons
+-----------------------------------------------------+
```

### Card Visual States

| State | Left Edge | Opacity | Position |
|-------|-----------|---------|----------|
| Active P1 | 3px red, pulsing glow | 100% | Top of stack |
| Active P2 | 3px amber | 100% | Sorted by age |
| Active P3 | 3px blue | 100% | Below P1-P2 |
| Active P4 | 3px dim gray | 85% | Bottom, collapsed default |
| Deferred | Dashed amber | 60% | Collapsed, shows return time |
| Resolved | Green edge, strikethrough | 40% | Resolved filter only |

### Card Cap in UI

- Display top 10 active cards
- "Show N more" expander for rest
- Priority 4-5 collapsed by default unless filtered

### Drill-Down Panels

| Card Domain | Drill-Down Content | Replaces |
|---|---|---|
| Health / Nutrition | Macro progress rings, 7-day sparklines, meal gap | health-protocol.html, recomp.html |
| Health / Recovery | Recovery breakdown, sleep chart, HRV, training load | health/health.html |
| Money / Budget | Category bars, burn rate, projected month-end | owens-future.html (budget) |
| Money / Net Worth | Asset donut, positions, growth trend | owens-future.html (wealth) |
| Markets | Watchlist, regime, theses | invest-intel.html |
| Family | Calendar 7-day, per-child time, bond health | (new) |
| Career | Director readiness, learning progress | learning.html (linked, not absorbed) |
| System | Orchestrator health, patrol freshness | evolution-intel.html |

### Design Language

Retained from current: dark theme, gold accents (#d4a55a), Playfair Display headers, DM Sans body, JetBrains Mono data.

Changes:
- Priority edge colors replace dot system
- Progress rings replace progress bars (more info-dense, better on mobile)
- Micro-animations: slide-up on resolve, fade-in on new, compress on defer
- Empty state: gold gradient card

---

## Backend & API

### `lifeos_api.py` — Unified Server (port 8077)

Python `http.server` subclass. No external dependencies.

**Static files:**
- `/` serves `index.html`
- `/css/*`, `/js/*`, `/components/*` serve assets

**REST API:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/cards` | GET | Active card queue, sorted by priority |
| `/api/cards/{id}/action` | POST | Done/defer/dismiss/execute |
| `/api/cards/history` | GET | Resolved cards (today, paginated) |
| `/api/vitals` | GET | KPI strip data (merged health + finance) |
| `/api/drill/{domain}` | GET | Drill-down data for domain |
| `/api/system/health` | GET | Orchestrator status, patrol freshness |
| `/api/system/refresh` | POST | Force card queue re-generation |

**Concurrency protection:**
- `fcntl.flock` on every read-modify-write of `action_queue.json`
- Atomic writes: `.tmp` -> validate -> rename

**Graceful degradation:**
- If `action_queue.json` missing/corrupt: return `degraded: true` with raw patrol data
- Dashboard detects degraded flag and renders read-only fallback (direct JSON reads, like today)
- Amber banner: "Running in degraded mode -- API offline"

### `card_generator.py` — Fusion Engine

**Inputs** (10 patrol output files):
- `superagent_state.json` (Overwatch concerns + recommendations)
- `alert_history.json` (budget, security, remediation alerts)
- `life_horizons.json` (upcoming milestones, deadlines)
- `relationship_intel.json` (bond health flags)
- `accountability_report.json` (pending recommendations)
- `opportunities.json` (unclaimed benefits, optimizations)
- `health/health_data.json` (recovery, nutrition, sleep)
- `pattern_prophet_output.json` (trend extrapolations)
- `formation_log.json` (deferred items returning)
- `task_health.json` (orchestrator failures)

**Output:** `action_queue.json`

**Schedule:** Orchestrator every 15 min + on-demand via API

**Logic:**
1. Read all patrol outputs
2. For each finding, generate deterministic card ID
3. If card exists and active: update, don't duplicate
4. If card exists and resolved: skip
5. If new: create with priority score, apply step template (or use agent-generated steps if present)
6. Merge related cards (same domain + similar signal)
7. Check auto-close conditions against current data
8. Remove cards whose source finding no longer exists
9. Enforce 30-card cap (overflow to `card_overflow.json`)
10. **P1 escalation:** if any new card is priority 1, trigger `s6_alert.py` iMessage (FLASH)
11. Atomic write to `action_queue.json`

### P1 iMessage Escalation

The dashboard is Tier 5 (pull-based, zero notifications) per the notification architecture standing order. But P1 FLASH cards represent safety, cascade failure, or financial breach. If a P1 card is generated and the Commander doesn't check the dashboard for hours, that's unacceptable silence on a critical finding.

**Rule:** When the card generator creates a NEW P1 card (not an update to an existing one), it calls `s6_alert.py` with a one-line summary. This respects the existing notification architecture — iMessage is already the FLASH channel. The card still appears in The Stack for action. The iMessage is the nudge that says "open the dashboard now."

Quiet hours (2200-0500) still apply — P1 FLASH sends regardless per existing s6_alert.py behavior.

### Write-Back Flow

**From dashboard:**
```
Browser -> POST /api/cards/{id}/action {action: "done"}
  -> API locks action_queue.json
  -> If card has auto_close condition: check condition NOW against current data
     -> If condition met: resolved_by = "auto_confirmed" (Commander was right)
     -> If condition not met: resolved_by = "commander" (trust the Commander, log the gap)
  -> Updates card state (resolved, timestamp)
  -> Updates pending_actions.json (marks item complete)
  -> Writes alert_history.json (classification: COMMANDER_ACTION)
  -> Unlocks, returns updated card list
  -> Browser removes card with animation
```

**Immediate auto-close check:** The 15-minute card generation cycle means auto-close conditions can lag. When the Commander taps "Done," the API checks the condition immediately rather than waiting for the next cycle. This eliminates the frustration of "I did the thing and the card is still yelling at me." The `POST /api/system/refresh` endpoint also re-runs all auto-close checks immediately.

**From MCP (iPhone/claude.ai):**
```
Claude -> MCP tool: card_action(id, "done")
  -> lifeos_mcp_server.py calls same write-back logic
  -> Returns confirmation + remaining count
```

### MCP Server Updates

New tools for `lifeos_mcp_server.py`:

| Tool | Purpose |
|------|---------|
| `get_action_queue` | Returns active cards (replaces get_action_items) |
| `card_action` | Done/defer/dismiss a card by ID |
| `render_action_stack` | Top N cards as MCP App interactive component |
| `render_drill_down` | Domain drill-down as MCP App chart/table |
| `render_vitals` | KPI strip as MCP App component |

### Streamable HTTP Migration

- Replace `SSEServerTransport` with `StreamableHTTPServerTransport` in `lifeos_mcp_http.py`
- Endpoint: `/sse` -> `/mcp`
- Add stateless session management
- Update Tailscale Funnel target
- Update claude.ai connector URL
- **Deadline: April 1, 2026**

### Learning Platform

**Not absorbed.** Stays on port 8083. Dashboard links to it from Career drill-down. Card generator can read `learning_data.json` and `mastery_state.json` for Director-readiness cards.

### Overwatch Brief Coexistence

Cards and Overwatch briefs serve different purposes and **both continue:**

- **Cards** are atomic, actionable, discrete. "Your protein is low. Here are 3 steps."
- **Overwatch briefs** are narrative synthesis, coaching, challenges. "You've been under-eating for 8 days, your deep sleep is cratering, and you have a Director presentation Tuesday. The mask is going up."

Overwatch generates cards for discrete actionable items AND continues writing narrative briefs to `overwatch-latest.md`. The brief may reference active cards ("I put 3 items in your Stack today — the protein one is the one that worries me most") but the brief is NOT replaced by cards. Cards handle the "what to do." Overwatch handles the "why it matters and what it means."

### Offline / Degraded Mode

**Problem:** 50/50 iPhone usage. Tailscale disconnects when VPN drops, on certain networks, or when Mac sleeps too long. Dashboard (:8443) and MCP server become unreachable.

**Phase 2 mitigation (ship):** Dashboard detects API failure and renders from cached data. On every successful API response, the dashboard writes the card queue and vitals to `localStorage`. When the API is unreachable, render the cached queue with an amber banner: "Offline — showing data from [timestamp]." Cards cannot be actioned offline, but the Commander can see what's pending.

**Phase 5 mitigation (future):** Lightweight PWA with service worker. Cache dashboard shell + last API responses. Enable offline viewing with full UI fidelity. Queue offline actions (done/defer/dismiss) and sync when connection restores.

---

## HTML Pages Consolidated

| Current File | Size | Absorbed Into |
|---|---|---|
| `owens-future.html` | 177KB | Money drill-down panels |
| `invest-intel.html` | 103KB | Markets drill-down |
| `health-protocol.html` | 51KB | Health drill-down |
| `network-map.html` | 62KB | System drill-down |
| `evolution-intel.html` | 28KB | System drill-down |
| `recomp.html` | 32KB | Health / Body Recomp drill-down |
| `predictions.html` | 48KB | Money drill-down |
| `hub.html` | 8KB | Replaced by dashboard landing |
| `lifeos-dashboard.html` | 40KB | Replaced by new `index.html` |
| `lifeos-v3.html` | 40KB | Duplicate, archived |
| `log.html` | 19KB | System drill-down |
| `learning.html` | 21KB | Linked (not absorbed) |

Originals archived to `dashboard/_archive/`.

---

## Build Sequence

### Phase 0: Emergency — Streamable HTTP (Day 1)
- Migrate `lifeos_mcp_http.py` SSE -> Streamable HTTP
- Update Funnel + connector URL
- Add `--bare` to `battle_rhythm_runner.sh`
- Add conditional `if` to SessionStart hooks
- **Exit:** MCP tools work from iPhone + desktop

### Phase 1: Foundation — Card Generator (Days 2-3)
- Build `card_generator.py` with atomic writes, dedup, merge, auto-close
- Build step template library (~30 signal types)
- Add P1 iMessage escalation via s6_alert.py
- Create `action_queue.json` schema
- Add to orchestrator (15 min cycle)
- **Exit:** Valid card queue from real patrol data, with steps, P1 alerts fire

### Phase 2: Core — API + Dashboard (Days 4-8)
- Build `lifeos_api.py` (static + REST, file locking, degraded mode)
- Immediate auto-close check on "Done" action (don't wait for 15-min cycle)
- Build new `index.html` + modular CSS/JS/components
- Action Card Web Component with full state machine
- Vitals strip, filter bar, card cap (10 visible)
- Write-back via POST
- Desktop side panel, mobile inline expand
- localStorage cache for offline/degraded rendering
- **Exit:** Cards render, actions write back, drill-down works for Health + Money, offline shows cached data

### Phase 3: Polish — Drill-Downs & Consolidation (Days 9-12)
- Build all 8 drill-down renderers
- Consolidate standalone HTML pages
- Archive originals
- **Exit:** All domains render, all pages absorbed

### Phase 4: MCP Apps (Days 13-16, after 2+ week stabilization)
- Add render_* tools to MCP server
- Add card_action tool
- Test iPhone + Desktop + web
- Update Formation to use rendered cards
- **Exit:** Interactive cards work in Claude conversations

### Phase 5: Continuous Optimization (Ongoing)
- Migrate Anticipation Engine rules into card generator
- Tune priority scoring from Commander response patterns
- Agent-generated steps: patrol agents output `steps` arrays directly, card generator passes through
- Add `initialPrompt` frontmatter to expensive agents
- Lazy-load drill-down data
- PWA service worker for full offline support with queued actions

---

## Risk Mitigations

| Risk | Mitigation |
|------|------------|
| SSE dies April 1 | Phase 0 is Day 1, independent |
| `action_queue.json` corruption | Atomic writes (.tmp -> rename), JSON validation |
| Concurrent file writes | `fcntl.flock` on every read-modify-write |
| API server down | Dashboard falls back to localStorage cached data |
| Card volume overwhelm | 30-card cap, 10 displayed, auto-merge, P4-5 collapsed |
| MCP Apps format instability | Deferred to Phase 4 after stabilization |
| Learning server absorption | Rejected -- stays separate |
| Standalone HTML loss | Archived before consolidation |
| P1 finding missed (dashboard not open) | Card generator triggers s6_alert.py iMessage on new P1 cards |
| Auto-close lag after Commander action | API checks auto-close condition immediately on "Done" tap |
| Novel findings lack good steps | Template fallback + Phase 5 agent-generated steps migration |
| Tailscale offline (iPhone) | localStorage cache renders last-known state with timestamp |
| Overwatch narrative lost to cards | Briefs continue alongside cards -- different purposes, both persist |

---

## Success Criteria

1. Commander opens dashboard and sees a prioritized list of what needs attention — not 6 tabs of data
2. Every card has specific numbered steps telling him exactly what to do
3. Done/Defer/Dismiss buttons work and cards disappear immediately
4. Cards auto-close when the system detects the condition is resolved
5. Same actions work from iPhone via MCP Apps in Claude conversations
6. Dashboard renders usefully on mobile with zero pinch-zoom
7. The Stack gets shorter as the Commander acts — empty state is the goal
8. System runs without Commander as trigger — patrols generate cards, auto-close resolves them, only human-required items surface
9. P1 cards trigger iMessage — Commander is never unaware of critical findings
10. Overwatch narrative briefs continue alongside cards — coaching and synthesis preserved
11. Dashboard works offline (cached state) when Tailscale is disconnected
