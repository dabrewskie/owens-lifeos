# Dashboard Rebuild — Phases 0-2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate MCP transport (emergency), build the card fusion engine, and ship the priority-first command interface dashboard with write-back actions.

**Architecture:** Card generator reads 10 patrol output JSON files and fuses them into a single `action_queue.json`. A Python API server serves the dashboard static files and REST endpoints for card actions. Dashboard renders a priority-sorted stack of action cards with Done/Defer/Dismiss buttons that write back via the API. localStorage caches data for offline/degraded rendering.

**Tech Stack:** Python 3.9 stdlib (`http.server`, `json`, `fcntl`), vanilla HTML/JS/CSS, Web Components, MCP SDK (`mcp>=1.26.0`)

**Spec:** `docs/superpowers/specs/2026-03-29-dashboard-rebuild-design.md`

**Security note:** Dashboard uses innerHTML for rendering trusted local JSON data. All data sources are local files written by system scripts — no user input, no external content. Dashboard is served locally and over Tailscale (authenticated network). DOM sanitization is not required for this threat model.

**Key paths:**
- Scripts: `~/Documents/S6_COMMS_TECH/scripts/`
- Dashboard: `~/Documents/S6_COMMS_TECH/dashboard/`
- MCP HTTP: `~/Documents/S6_COMMS_TECH/scripts/lifeos_mcp_http.py`
- MCP Server: `~/Documents/S6_COMMS_TECH/scripts/lifeos_mcp_server.py`
- Orchestrator: `~/Documents/S6_COMMS_TECH/scripts/lifeos_orchestrator.py`
- Battle rhythm: `~/Documents/S6_COMMS_TECH/scripts/battle_rhythm_runner.sh`
- Alert system: `~/Documents/S6_COMMS_TECH/scripts/s6_alert.py`

---

## Phase 0: Emergency — Streamable HTTP Migration

### Task 1: Migrate MCP transport from SSE to Streamable HTTP

**Files:**
- Modify: `~/Documents/S6_COMMS_TECH/scripts/lifeos_mcp_http.py`

- [ ] **Step 1: Check MCP SDK version supports Streamable HTTP**

```bash
cd ~/Documents/S6_COMMS_TECH/scripts && source lifeos-mcp-venv/bin/activate && python3 -c "import mcp; print(mcp.__version__)"
```

Requires >= 1.26.0.

- [ ] **Step 2: Update lifeos_mcp_http.py — change transport from SSE to Streamable HTTP**

Change `mcp.run(transport="sse")` to `mcp.run(transport="streamable-http")`. Update docstring: endpoint changes from `/sse` to `/mcp`. Update print statements. Full replacement file content:

```python
#!/usr/bin/env python3
"""
lifeos_mcp_http.py — Streamable HTTP transport for Life OS MCP Server

Wraps the existing lifeos_mcp_server.py and serves it over Streamable HTTP
via Tailscale Funnel. Enables iPhone and web Claude instances to connect
directly to the Life OS MCP server with live data access.

Security:
  - Tailscale Funnel provides HTTPS with Let's Encrypt cert
  - Host header validation for Tailscale domain
  - No OAuth — authless server (claude.ai supports this)

Usage:
  python3 lifeos_mcp_http.py              # Start server (default port 8078)
  python3 lifeos_mcp_http.py --port 8078  # Custom port

claude.ai Custom Connector URL:
  https://torys-macbook-pro.tail416e3a.ts.net/mcp

Requires: lifeos-mcp-venv with mcp>=1.26.0, uvicorn, starlette
"""
from __future__ import annotations

import argparse

from lifeos_mcp_server import mcp
from mcp.server.transport_security import TransportSecuritySettings


def main():
    parser = argparse.ArgumentParser(description="Life OS MCP HTTP Server")
    parser.add_argument("--port", type=int, default=8078)
    parser.add_argument("--host", default="0.0.0.0",
                        help="Listen address (default: all interfaces for Funnel proxy)")
    args = parser.parse_args()

    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    )

    print(f"Life OS MCP Server — Streamable HTTP transport")
    print(f"Listening on {args.host}:{args.port}")
    print(f"Endpoint: /mcp")
    print(f"Funnel URL: https://torys-macbook-pro.tail416e3a.ts.net/mcp")
    print(f"Tools: {len(mcp._tool_manager._tools)} available")

    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Restart MCP server and verify startup**

```bash
pkill -f lifeos_mcp_http || true
cd ~/Documents/S6_COMMS_TECH/scripts && source lifeos-mcp-venv/bin/activate && python3 lifeos_mcp_http.py &
```

Verify output shows "Streamable HTTP transport" and "Endpoint: /mcp".

- [ ] **Step 4: Verify Tailscale Funnel still proxies correctly**

```bash
tailscale funnel status
```

Port 443 -> localhost:8078 should be unchanged. New `/mcp` endpoint is served on same port.

- [ ] **Step 5: Update claude.ai connector URL**

Manual step: In claude.ai Settings -> Connectors -> "Life OS" -> Edit URL:
Old: `https://torys-macbook-pro.tail416e3a.ts.net/sse`
New: `https://torys-macbook-pro.tail416e3a.ts.net/mcp`

- [ ] **Step 6: Verify MCP tools work from iPhone**

Open claude.ai on iPhone, ask Claude to call `get_cop`. Confirm it returns live COP data.

- [ ] **Step 7: Restart LaunchAgent if needed**

```bash
launchctl kickstart -k gui/$(id -u)/com.lifeos.mcp-http
```

- [ ] **Step 8: Commit**

```bash
cd ~/Documents/S6_COMMS_TECH && git add scripts/lifeos_mcp_http.py && git commit -m "fix: migrate MCP transport SSE -> Streamable HTTP (April 1 deadline)"
```

### Task 2: Add --bare flag to battle rhythm runner

**Files:**
- Modify: `~/Documents/S6_COMMS_TECH/scripts/battle_rhythm_runner.sh`

- [ ] **Step 1: Read the runner and find all `claude -p` invocations**

Read `battle_rhythm_runner.sh`. Find lines matching `$CLAUDE_BIN -p` — add `--bare` after `-p` on each. This skips hooks/plugins/LSP on automated headless runs.

- [ ] **Step 2: Add --bare to all headless claude invocations**

For each line like `$CLAUDE_BIN -p "prompt..."`, change to `$CLAUDE_BIN -p --bare "prompt..."`. Do NOT add `--bare` to the test command or any interactive invocations.

- [ ] **Step 3: Test with the test mode**

```bash
cd ~/Documents/S6_COMMS_TECH/scripts && ./battle_rhythm_runner.sh test
```

Verify it completes without error.

- [ ] **Step 4: Commit**

```bash
cd ~/Documents/S6_COMMS_TECH && git add scripts/battle_rhythm_runner.sh && git commit -m "perf: add --bare to headless claude calls in battle rhythm runner"
```

### Task 3: Add conditional if field to SessionStart hooks

**Files:**
- Modify: `~/.claude/settings.json`

- [ ] **Step 1: Check if --bare already skips hooks entirely**

```bash
claude --help 2>&1 | grep -i bare
```

If `--bare` skips all hooks, this task is already handled by Task 2. Verify by running a `--bare` session and checking if memory_expander/anticipation_engine output appears. If hooks are skipped, mark this task complete.

- [ ] **Step 2: If hooks still fire on --bare, add conditional `if` field**

Read `~/.claude/settings.json`, find SessionStart hooks for `memory_expander.py` and `anticipation_engine.py`. Add `"if": "!headless"` or equivalent syntax per Claude Code docs.

- [ ] **Step 3: Commit note**

Settings are in `~/.claude/` (not in git). Document the change in the next commit message.

---

## Phase 1: Foundation — Card Generator

### Task 4: Build card_generator.py — core skeleton with paths and helpers

**Files:**
- Create: `~/Documents/S6_COMMS_TECH/scripts/card_generator.py`

- [ ] **Step 1: Create the file with imports, paths, constants, and helper functions**

```python
#!/usr/bin/env python3
"""
Card Generator — Fusion engine for Life OS dashboard.

Reads 10 patrol output files, fuses findings into a single prioritized
action_queue.json. Each card has: headline, why, steps, actions, auto-close
conditions, and priority scoring with escalation.

Usage:
  python3 card_generator.py           # Normal run (generate queue)
  python3 card_generator.py --dry-run # Show what would be generated
  python3 card_generator.py --status  # Print current queue summary
"""

import fcntl
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

DASHBOARD_DIR = Path.home() / "Documents" / "S6_COMMS_TECH" / "dashboard"
SCRIPTS_DIR = Path.home() / "Documents" / "S6_COMMS_TECH" / "scripts"
HEALTH_DIR = DASHBOARD_DIR / "health"

QUEUE_FILE = DASHBOARD_DIR / "action_queue.json"
OVERFLOW_FILE = DASHBOARD_DIR / "card_overflow.json"

SOURCES = {
    "superagent": DASHBOARD_DIR / "superagent_state.json",
    "alerts": DASHBOARD_DIR / "alert_history.json",
    "horizons": DASHBOARD_DIR / "life_horizons.json",
    "relationships": DASHBOARD_DIR / "relationship_intel.json",
    "accountability": DASHBOARD_DIR / "accountability_report.json",
    "opportunities": DASHBOARD_DIR / "opportunities.json",
    "health": HEALTH_DIR / "health_data.json",
    "prophet": DASHBOARD_DIR / "pattern_prophet_output.json",
    "formation": DASHBOARD_DIR / "formation_log.json",
    "task_health": DASHBOARD_DIR / "task_health.json",
}

MAX_ACTIVE_CARDS = 30
NOW = datetime.now()
DRY_RUN = "--dry-run" in sys.argv
STATUS_ONLY = "--status" in sys.argv


def load_json(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def card_id(source: str, signal_type: str, date_str: str = None) -> str:
    date_str = date_str or NOW.strftime("%Y%m%d")
    raw = f"{source}_{signal_type}_{date_str}"
    short_hash = hashlib.md5(raw.encode()).hexdigest()[:8]
    return f"card_{date_str}_{source}_{short_hash}"


def atomic_write(path: Path, data):
    tmp = path.parent / f".{path.name}.tmp"
    content = json.dumps(data, indent=2, default=str)
    json.loads(content)  # validate
    tmp.write_text(content)
    tmp.rename(path)
```

- [ ] **Step 2: Verify it runs**

```bash
cd ~/Documents/S6_COMMS_TECH/scripts && python3 -c "from card_generator import *; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd ~/Documents/S6_COMMS_TECH && git add scripts/card_generator.py && git commit -m "feat: card_generator.py skeleton with paths and helpers"
```

### Task 5: Add step template library

**Files:**
- Modify: `~/Documents/S6_COMMS_TECH/scripts/card_generator.py`

- [ ] **Step 1: Add STEP_TEMPLATES dict and resolve_steps function**

Add after `atomic_write`:

```python
GENERIC_STEPS = [
    "Review details in the drill-down panel",
    "Take action or dismiss",
]

STEP_TEMPLATES = {
    "protein_gap": [
        "Add protein shake with next meal ({deficit_half}g target)",
        "Log all meals in Cronometer today",
        "Target {checkpoint_target}g protein by 3pm",
    ],
    "calorie_deficit": [
        "Eat a full meal NOW — minimum 500 kcal",
        "Log in Cronometer immediately after eating",
        "Target {target_cal} kcal by end of day",
    ],
    "deep_sleep_low": [
        "No screens 1 hour before bed tonight",
        "Take magnesium glycinate 400mg at 9pm",
        "Set bedroom temp to 65-68F",
    ],
    "overtraining_risk": [
        "Take today as active recovery — Zone 2 only or full rest",
        "Hit protein target ({protein_target}g) to support recovery",
        "Review recovery score tomorrow before training",
    ],
    "hrv_drop": [
        "Reduce training intensity today — light movement only",
        "Prioritize sleep tonight (in bed by 10pm)",
        "Check HRV again tomorrow morning",
    ],
    "recovery_red": [
        "REST DAY — no training, light walking only",
        "Focus on nutrition: {protein_target}g protein, {target_cal} kcal minimum",
        "In bed by 9:30pm, no screens after 9pm",
    ],
    "recovery_yellow": [
        "Moderate training only — follow program, no extras",
        "Hit all nutrition targets today",
        "Add 30 min to normal sleep window",
    ],
    "health_data_stale": [
        "Check iCloud sync on iPhone (Settings > [name] > iCloud)",
        "Open Health Auto Export app and force sync",
        "Verify data appears in dashboard within 30 minutes",
    ],
    "budget_overage": [
        "Review {category} transactions in Rocket Money",
        "Identify top 3 discretionary charges to cut or defer",
        "Freeze {category} spending for remainder of month if over >10%",
    ],
    "spending_spike": [
        "Unusual spending detected in {category}: ${amount}",
        "Verify transaction in Rocket Money — authorized?",
        "If unauthorized, freeze Chase card and report",
    ],
    "task_failure": [
        "Check orchestrator log: ~/Documents/S6_COMMS_TECH/scripts/cleanup_logs/orchestrator.log",
        "Run task manually: python3 ~/Documents/S6_COMMS_TECH/scripts/{script}",
        "If persistent, check file permissions and Python path",
    ],
    "patrol_stale": [
        "{patrol_name} output is {age}h old (expected <{max_age}h)",
        "Check orchestrator status: python3 lifeos_orchestrator.py --status",
        "Force-run: python3 lifeos_orchestrator.py --run {task_name}",
    ],
    "cop_stale": [
        "COP is {age}h old — run cop-sync to refresh",
        "Check if battle_cop_sync task is healthy in orchestrator",
        "Manual sync: /sweep sync",
    ],
    "relationship_flag": [
        "No {person} 1-on-1 time in {days} days",
        "Schedule 30 min dedicated time this week",
        "Put it on the calendar with a location (Tesla nav sync)",
    ],
    "bond_red": [
        "{relationship} bond health is RED — attention needed NOW",
        "Have a direct conversation today — see /comms prep",
        "Block 1 hour on calendar this week for reconnection",
    ],
    "deadline_approaching": [
        "{item} due in {days} days ({due_date})",
        "Block focused time on calendar today",
        "Identify and remove blockers — escalate if needed",
    ],
    "overdue_action": [
        "{item} is OVERDUE (was due {due_date})",
        "Complete today or reschedule with explicit new date",
        "If blocked, document blocker and escalate",
    ],
    "unclaimed_benefit": [
        "Unclaimed benefit: {benefit}",
        "Estimated value: ${value}/year",
        "Action: {action_step}",
    ],
}


def resolve_steps(signal_type: str, variables: dict = None) -> list:
    templates = STEP_TEMPLATES.get(signal_type, GENERIC_STEPS)
    if not variables:
        return list(templates)
    resolved = []
    for tmpl in templates:
        try:
            resolved.append(tmpl.format(**variables))
        except KeyError:
            resolved.append(tmpl)
    return resolved
```

- [ ] **Step 2: Test template resolution**

```bash
cd ~/Documents/S6_COMMS_TECH/scripts && python3 -c "
from card_generator import resolve_steps
print(resolve_steps('protein_gap', {'deficit_half': 45, 'checkpoint_target': 150}))
print(resolve_steps('unknown_signal'))
"
```

Expected: resolved steps with numbers, then generic 2-step fallback.

- [ ] **Step 3: Commit**

```bash
cd ~/Documents/S6_COMMS_TECH && git add scripts/card_generator.py && git commit -m "feat: step template library — 20+ signal types with variable substitution"
```

### Task 6: Build source extractors

**Files:**
- Modify: `~/Documents/S6_COMMS_TECH/scripts/card_generator.py`

- [ ] **Step 1: Add extractor functions for health, overwatch, alerts, horizons, task_health, relationships, opportunities**

Each extractor reads one source file and returns a list of card candidate dicts. Add after `resolve_steps`. The extractors should cover:

- `extract_health(data)` — protein gap, calorie deficit, deep sleep, recovery score (red/yellow)
- `extract_superagent(data)` — active concerns, pending recommendations
- `extract_alerts(data)` — recent non-remediation alerts (<48h old)
- `extract_horizons(data)` — milestones within 90 days
- `extract_task_health(data)` — tasks with 3+ consecutive failures
- `extract_relationships(data)` — RED bond status
- `extract_opportunities(data)` — unclaimed, undismissed opportunities

Each card candidate must have: `id`, `source`, `domain`, `priority`, `headline`, `why`, `steps`, `drill_down`, and optionally `auto_close`.

Register all extractors in a dict: `EXTRACTORS = {"health": extract_health, ...}`

Implementation should follow the patterns in the spec — use `card_id()` for deterministic IDs, `resolve_steps()` for step templates.

- [ ] **Step 2: Test extractors with real data**

```bash
cd ~/Documents/S6_COMMS_TECH/scripts && python3 -c "
from card_generator import *
for name, fn in EXTRACTORS.items():
    data = load_json(SOURCES.get(name, Path('/dev/null')))
    cards = fn(data)
    print(f'{name}: {len(cards)} cards')
    for c in cards[:2]:
        print(f'  P{c[\"priority\"]} [{c[\"domain\"]}] {c[\"headline\"][:60]}')
"
```

- [ ] **Step 3: Commit**

```bash
cd ~/Documents/S6_COMMS_TECH && git add scripts/card_generator.py && git commit -m "feat: card source extractors — 7 patrol sources with domain-specific card generation"
```

### Task 7: Build main generate() with dedup, scoring, auto-close, P1 alerts, and CLI

**Files:**
- Modify: `~/Documents/S6_COMMS_TECH/scripts/card_generator.py`

- [ ] **Step 1: Add priority scoring, auto-close checking, and merge logic**

Functions needed:
- `score_priority(card, existing=None)` — apply escalation (age >48h, deferred 2+x, Overwatch-flagged) and de-escalation (auto-close >80% met). Clamp 1-5.
- `merge_cards(candidates)` — group by domain + first headline word, keep highest priority, combine steps.
- `check_auto_close(card)` — parse `condition` string (e.g., "health.macros.protein.current >= 180"), navigate dotted path in source JSON, evaluate comparison.

- [ ] **Step 2: Add the main `generate()` function**

Pipeline:
1. Read all 10 source files
2. Run extractors, collect candidates
3. Load existing `action_queue.json`
4. Merge related candidates
5. For each candidate: if existing and resolved, skip; if existing and active, update with escalation; if new, create
6. Check auto-close conditions on all active cards
7. Preserve today's resolved cards for history
8. Sort: active by priority then age, resolved at end
9. Enforce 30-card cap, overflow to `card_overflow.json`
10. If new P1 cards, call `s6_alert.py` with FLASH
11. Atomic write to `action_queue.json`

- [ ] **Step 3: Add `_send_p1_alert(cards)` function**

Import `s6_alert.send_alert` and call with CRITICAL severity for new P1 cards.

- [ ] **Step 4: Add `print_status()` and `__main__` block**

Status prints active/deferred/resolved counts and top 10 cards. Main block dispatches to `print_status()` or `generate()` based on CLI flags.

- [ ] **Step 5: Test dry-run**

```bash
cd ~/Documents/S6_COMMS_TECH/scripts && python3 card_generator.py --dry-run 2>&1 | head -40
```

- [ ] **Step 6: Test real generation**

```bash
cd ~/Documents/S6_COMMS_TECH/scripts && python3 card_generator.py && python3 card_generator.py --status
```

- [ ] **Step 7: Commit**

```bash
cd ~/Documents/S6_COMMS_TECH && git add scripts/card_generator.py dashboard/action_queue.json && git commit -m "feat: card generator full pipeline — dedup, scoring, auto-close, P1 alerts"
```

### Task 8: Add card_generator to orchestrator

**Files:**
- Modify: `~/Documents/S6_COMMS_TECH/scripts/lifeos_orchestrator.py`

- [ ] **Step 1: Add card_generator task to TASKS dict**

```python
    "card_generator": {
        "script": "card_generator.py",
        "schedule": {"interval_min": 15},
        "timeout": 30,
        "critical": True,
    },
```

- [ ] **Step 2: Verify and force-run**

```bash
cd ~/Documents/S6_COMMS_TECH/scripts && python3 lifeos_orchestrator.py --run card_generator
```

- [ ] **Step 3: Commit**

```bash
cd ~/Documents/S6_COMMS_TECH && git add scripts/lifeos_orchestrator.py && git commit -m "feat: add card_generator to orchestrator — 15 min cycle"
```

---

## Phase 2: Core — API Server + Dashboard

### Task 9: Build lifeos_api.py — unified static + REST server

**Files:**
- Create: `~/Documents/S6_COMMS_TECH/scripts/lifeos_api.py`

- [ ] **Step 1: Create the server with static file serving and all API endpoints**

Python `http.server` subclass serving from `DASHBOARD_DIR`. API endpoints:
- `GET /api/cards` — active + deferred cards from `action_queue.json`
- `POST /api/cards/{id}/action` — done/defer/dismiss with file locking and immediate auto-close check
- `GET /api/cards/history` — today's resolved cards
- `GET /api/vitals` — merged KPI data from health + finance JSONs
- `GET /api/drill/{domain}` — domain-specific drill-down data
- `GET /api/system/health` — server uptime, queue freshness
- `POST /api/system/refresh` — subprocess call to card_generator.py

Must include: `fcntl.flock` on card action writes, CORS headers, OPTIONS handler, atomic writes via `.tmp` + rename.

- [ ] **Step 2: Test all endpoints**

```bash
cd ~/Documents/S6_COMMS_TECH/scripts && python3 lifeos_api.py &
sleep 2
curl -s http://localhost:8077/api/vitals | python3 -m json.tool
curl -s http://localhost:8077/api/cards | python3 -m json.tool | head -20
curl -s http://localhost:8077/api/system/health | python3 -m json.tool
kill %1
```

- [ ] **Step 3: Commit**

```bash
cd ~/Documents/S6_COMMS_TECH && git add scripts/lifeos_api.py && git commit -m "feat: lifeos_api.py — unified static + REST API server"
```

### Task 10: Build dashboard shell — index.html + CSS

**Files:**
- Create: `~/Documents/S6_COMMS_TECH/dashboard/css/tokens.css`
- Create: `~/Documents/S6_COMMS_TECH/dashboard/css/layout.css`
- Create: `~/Documents/S6_COMMS_TECH/dashboard/css/cards.css`
- Create: `~/Documents/S6_COMMS_TECH/dashboard/index.html`

- [ ] **Step 1: Create css/ directory**

```bash
mkdir -p ~/Documents/S6_COMMS_TECH/dashboard/css
```

- [ ] **Step 2: Write tokens.css**

Design tokens: colors (carried from existing dashboard — `--bg`, `--gold`, `--green`, `--red`, `--amber`, `--blue`), priority edge colors (`--p1` through `--p4`), spacing, radius, fonts, transitions. Plus base resets (box-sizing, body font/background).

- [ ] **Step 3: Write layout.css**

Header, filter bar (horizontal scrollable with active state), main grid (single column mobile, 60/40 split desktop with sticky side panel), stack container, show-more expander, empty state, degraded banner, mobile breakpoints.

- [ ] **Step 4: Write cards.css**

Action card (priority left edge, hover, state variants for P1-P4/deferred/resolved), P1 pulse animation, card header (headline + domain badge), why text, steps (numbered with counter-increment + gold numbered circles), action buttons (done=green, defer=amber, dismiss=gray), defer dropdown, expand/collapse animation, entrance/exit animations, vitals strip (grid of KPI boxes), mobile responsive.

- [ ] **Step 5: Write index.html**

Minimal shell: font imports, CSS links, degraded banner (hidden), header, filter nav with All/Money/Health/Family/Career/System/Markets/Resolved buttons, vitals div, main with stack + side-panel, `<script type="module" src="js/engine.js">`.

- [ ] **Step 6: Verify HTML loads in browser**

```bash
cd ~/Documents/S6_COMMS_TECH/scripts && python3 lifeos_api.py &
open http://localhost:8077/
```

- [ ] **Step 7: Commit**

```bash
cd ~/Documents/S6_COMMS_TECH && git add dashboard/index.html dashboard/css/ && git commit -m "feat: dashboard shell — index.html with design tokens, layout, and card CSS"
```

### Task 11: Build engine.js — data loading, rendering, actions, filters, offline

**Files:**
- Create: `~/Documents/S6_COMMS_TECH/dashboard/js/engine.js`

- [ ] **Step 1: Write engine.js with all core functionality**

Sections needed:
- **API client** — `fetchAPI(path)` with localStorage cache on success, fallback to cache on failure, `postAPI(path, body)` for actions
- **Data loading** — `loadAll()` fetches cards + vitals in parallel, renders both, sets poll interval (60s)
- **Vitals rendering** — `renderVitals()` populates KPI strip from vitals data
- **Card rendering** — `renderStack()` filters by current domain, separates P1-3 from P4-5, caps visible at 10, renders each card with headline/why/steps/actions, "show more" expander
- **Card actions** — `handleCardAction(e)` reads action/cardId from button data attributes, optimistic UI (card-exit animation), POST to API, reload after 500ms
- **Drill-down** — `toggleDrillDown(cardEl)` opens side panel on desktop / inline expand on mobile, fetches `/api/drill/{domain}`, renders basic domain views (Health: macro progress bars, Money: KPI grid)
- **Filters** — click handler on filter bar, keyboard shortcuts 1-7 + 0, `updateFilterCounts()`
- **Offline** — `showDegraded(ts)` / `hideDegraded()` for amber banner
- **Init** — `loadAll()` on page load, `setInterval(loadAll, 60000)`

- [ ] **Step 2: Test in browser — full flow**

```bash
cd ~/Documents/S6_COMMS_TECH/scripts && pkill -f lifeos_api || true && python3 lifeos_api.py &
open http://localhost:8077/
```

Verify: vitals render, cards render with priority edges, Done/Defer/Dismiss work, filters narrow the stack, empty state shows when cleared, keyboard shortcuts work.

- [ ] **Step 3: Test mobile viewport**

Chrome DevTools device toolbar, iPhone 14 (390x844). Verify: 3 vitals per row, full-width cards, tappable buttons, scrollable filters.

- [ ] **Step 4: Test offline mode**

Load page (caches data), stop server (`pkill -f lifeos_api`), reload. Verify amber banner + cached cards render.

- [ ] **Step 5: Commit**

```bash
cd ~/Documents/S6_COMMS_TECH && git add dashboard/js/engine.js && git commit -m "feat: engine.js — data loading, card rendering, actions, filters, offline cache"
```

### Task 12: Update start_dashboard.sh

**Files:**
- Modify: `~/Documents/S6_COMMS_TECH/dashboard/start_dashboard.sh`

- [ ] **Step 1: Replace simple HTTP server with lifeos_api.py**

```bash
#!/bin/bash
# Start Life OS Dashboard API Server
cd "$(dirname "$0")"
SCRIPTS_DIR="$HOME/Documents/S6_COMMS_TECH/scripts"
PYTHON="/Library/Developer/CommandLineTools/usr/bin/python3"
pkill -f lifeos_api || true
sleep 1
exec $PYTHON "$SCRIPTS_DIR/lifeos_api.py" --port 8077
```

- [ ] **Step 2: Test**

```bash
bash ~/Documents/S6_COMMS_TECH/dashboard/start_dashboard.sh &
sleep 2
curl -s http://localhost:8077/api/system/health
kill %1
```

- [ ] **Step 3: Commit**

```bash
cd ~/Documents/S6_COMMS_TECH && git add dashboard/start_dashboard.sh && git commit -m "feat: start_dashboard.sh launches lifeos_api.py"
```

### Task 13: Add MCP card tools to lifeos_mcp_server.py

**Files:**
- Modify: `~/Documents/S6_COMMS_TECH/scripts/lifeos_mcp_server.py`

- [ ] **Step 1: Add get_action_queue tool**

Register new `@mcp.tool()` function that reads `action_queue.json`, returns active + deferred cards as JSON string.

- [ ] **Step 2: Add card_action tool**

Register `@mcp.tool()` with params: `card_id: str`, `action: str` ("done"/"defer"/"dismiss"), `defer_hours: int = 4`. Uses `fcntl.flock` for safe read-modify-write. Returns success + remaining count.

- [ ] **Step 3: Ensure imports are present**

Add `import fcntl` and `from datetime import timedelta` if not already imported.

- [ ] **Step 4: Restart and verify tool count**

```bash
pkill -f lifeos_mcp_http || true
cd ~/Documents/S6_COMMS_TECH/scripts && source lifeos-mcp-venv/bin/activate && python3 lifeos_mcp_http.py &
```

Tool count should be +2 from previous.

- [ ] **Step 5: Commit**

```bash
cd ~/Documents/S6_COMMS_TECH && git add scripts/lifeos_mcp_server.py && git commit -m "feat: add get_action_queue and card_action MCP tools"
```

### Task 14: End-to-end integration test

- [ ] **Step 1: Full pipeline test**

```bash
cd ~/Documents/S6_COMMS_TECH/scripts
python3 card_generator.py
pkill -f lifeos_api || true && python3 lifeos_api.py &
sleep 2
curl -s http://localhost:8077/api/cards | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Active: {len([c for c in d[\"cards\"] if c[\"state\"]==\"active\"])}'))"
open http://localhost:8077/
```

- [ ] **Step 2: Test dashboard card actions in browser**

Click Done, Defer, Dismiss. Switch to Resolved filter. Verify all transitions.

- [ ] **Step 3: Test MCP tools work in parallel**

Call `get_action_queue` from Claude. Call `card_action` to mark a card done. Verify dashboard reflects the change on next refresh.

- [ ] **Step 4: Test Tailscale access**

```bash
open https://torys-macbook-pro.tail416e3a.ts.net:8443/
```

- [ ] **Step 5: Commit if any fixes were needed**

```bash
cd ~/Documents/S6_COMMS_TECH && git add -A && git commit -m "fix: integration test fixes for dashboard rebuild"
```

---

## Post-Implementation Notes

**What's next (separate plans):**
- Phase 3: Full drill-down renderers for all 8 domains + consolidate 12 HTML pages
- Phase 4: MCP App render tools (after 2+ week MCP Apps stabilization)
- Phase 5: PWA, agent-generated steps, priority tuning from response patterns
