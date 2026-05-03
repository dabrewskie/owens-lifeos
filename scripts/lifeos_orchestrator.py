#!/usr/bin/env python3
"""
Life OS Orchestrator — Single process replaces 13 LaunchAgents.

Runs every 15 minutes via launchd. Each cycle:
  1. Reads schedule dict to find tasks due NOW
  2. Executes each due task as a subprocess with timeout
  3. Records results to task_health.json
  4. Alerts Commander via iMessage if critical task fails 3x consecutive
  5. Writes single rotating log

Usage:
  python3 lifeos_orchestrator.py             # Normal run (execute due tasks)
  python3 lifeos_orchestrator.py --dry-run   # Show what would run, don't execute
  python3 lifeos_orchestrator.py --status    # Print task health summary
  python3 lifeos_orchestrator.py --run TASK  # Force-run a specific task by name
"""

import json
import os
import subprocess
import sys
import time
import fcntl
from datetime import datetime, timedelta
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────
SCRIPTS_DIR = Path.home() / "Documents" / "S6_COMMS_TECH" / "scripts"
DASHBOARD_DIR = Path.home() / "Documents" / "S6_COMMS_TECH" / "dashboard"
LOG_DIR = SCRIPTS_DIR / "cleanup_logs"
LOCK_FILE = SCRIPTS_DIR / ".orchestrator.lock"
HEALTH_FILE = DASHBOARD_DIR / "task_health.json"
LOG_FILE = LOG_DIR / "orchestrator.log"
PYTHON = "/Library/Developer/CommandLineTools/usr/bin/python3"

# Max log size before rotation (1MB)
MAX_LOG_BYTES = 1_000_000
# Max consecutive failures before alerting
ALERT_THRESHOLD = 3

# ── Schedule ──────────────────────────────────────────────────────────
# Each task defines:
#   script: filename in SCRIPTS_DIR
#   schedule: cron-like dict with keys: hours, minutes, weekdays, interval_min
#     - hours/minutes: list of (hour, minute) tuples for calendar-based runs
#     - weekdays: optional list of weekday numbers (0=Mon, 6=Sun) to restrict
#     - interval_min: run every N minutes (alternative to hours/minutes)
#   timeout: max seconds before kill
#   critical: if True, alerts after ALERT_THRESHOLD consecutive failures
#   args: optional list of extra arguments

TASKS = {
    "invest_intel": {
        "script": "invest_intel_updater.py",
        "schedule": {"hours": [(6, 23), (16, 47)]},
        # QRF_014 2026-05-02: timeout raised 360->600. Script makes 3 sequential Claude API calls
        # (28,000 output tokens total) + ~77 yfinance calls. Observed runtime 344-405s (avg 375s).
        # Prior 360s timeout was below the runtime envelope — borderline on fast days, fatal on slow.
        "timeout": 600,
        "critical": True,
    },
    "market_alerts": {
        "script": "market_alert_checker.py",
        "schedule": {"hours": [(7, 0), (9, 30), (12, 0), (15, 30)]},
        "timeout": 30,
        "critical": False,
    },
    "budget_sentinel": {
        "script": "budget_sentinel.py",
        "schedule": {"hours": [(7, 0)], "weekdays": [0]},  # Monday 0700
        "timeout": 60,
        "critical": True,
    },
    "health_dashboard": {
        "script": "health_dashboard_updater.py",
        "schedule": {"hours": [(6, 30)]},
        "timeout": 60,
        "critical": False,
    },
    "recovery_score": {
        "script": "recovery_score_calculator.py",
        "schedule": {"hours": [(6, 45)]},
        "timeout": 60,
        "critical": False,
    },
    "training_plan": {
        "script": "training_plan_generator.py",
        "schedule": {"hours": [(6, 50)]},
        "timeout": 30,
        "critical": False,
    },
    "cop_dashboard": {
        "script": "dashboard_updater.py",
        "schedule": {"interval_min": 60},
        "timeout": 30,
        "critical": True,
    },
    # Cost Sentinel — guardrail added 2026-04-23 after the ANTHROPIC_API_KEY
    # leak incident. Scans shell env files, LaunchAgent plists, the runner,
    # and running orchestrator processes for any re-introduction of the raw
    # API key (which would silently override Max subscription OAuth and cause
    # ~$10/day in raw-API billing). RED status fires CRITICAL iMessage.
    "cost_sentinel": {
        "script": "cost_sentinel.py",
        "schedule": {"interval_min": 240},  # every 4 hours
        "timeout": 30,
        "critical": True,
    },
    # Sync Watcher — guardrail added 2026-04-28 by MDMP staff (Overwatch + Prophet + CoS).
    # Prophet's #1 silent-failure prediction post-TFMF deployment: handoff items in
    # iCloud/_SYNC/FOR_CODE.md or FOR_DESKTOP.md sit unprocessed because no agent watches
    # them. Both surfaces report GREEN while real work goes undone. This task closes that
    # blind spot — checks both files every 6h, alerts PRIORITY if non-empty content has
    # not been processed within THRESHOLD_HOURS (24h default).
    "sync_watcher": {
        "script": "sync_watcher.py",
        "schedule": {"interval_min": 360},  # every 6 hours
        "timeout": 30,
        "critical": False,
    },
    # State Aggregator — Single Source of Truth for the dashboard.
    # Built 2026-04-28 to fix the 4/19 GUI audit's diagnosis: agent staff
    # writes to JSON set A, dashboard reads from JSON set B, intersection ZERO.
    # Plus today's TFMF added a third silo at ~/tfmf_data/.
    # This task reads ALL three flows every 5 min and produces unified_state.json,
    # which lifeos_api.py serves at /api/unified_state and the canonical
    # lifeos-dashboard.html consumes via single fetch.
    "state_aggregate": {
        "script": "state_aggregator.py",
        "schedule": {"interval_min": 5},  # every 5 minutes
        "timeout": 30,
        "critical": True,
    },
    "gui_compile": {
        "script": "gui_compiler.py",
        "schedule": {"interval_min": 5},
        "timeout": 30,
        "critical": True,
    },
    "state_synth": {
        "script": "state_synthesizer.py",
        "schedule": {"interval_min": 5},
        "timeout": 30,
        "critical": True,
    },
    # QRF Watchdog — Commander mandate 2026-05-01: any monitored surface
    # offline >30 min auto-dispatches the QRF playbook (deterministic repair
    # first, claude -p QRF agent escalation second). Catches silent rot the
    # exit-code-only orchestrator can't see (parse_error=True, empty profiles,
    # stale JSON behind a fresh-looking task_health row). Cooldown enforced
    # inside the watchdog so a 15-min cron tick never causes dispatch storms.
    "qrf_watchdog": {
        "script": "qrf_watchdog.py",
        "schedule": {"interval_min": 15},
        "timeout": 720,  # allow one playbook command to run end-to-end
        "critical": True,
    },
    # QRF Coverage Audit — weekly Monday 0600 sweep that grows watchdog
    # coverage as new dashboards/JSONs/services come online (NCC, PCC, future
    # surfaces). Probes lsof + filesystem + watchdog SURFACES, applies safe
    # additions to qrf_extra_surfaces.json (which the watchdog auto-loads),
    # and reports any uncovered dashboards (SO #16) + orphan surfaces. Skips
    # auto-add for surfaces unhealthy on first probe — those need triage,
    # not silent monitoring.
    "qrf_coverage_audit": {
        "script": "qrf_coverage_audit.py",
        "schedule": {"hours": [(6, 0)], "weekdays": [0]},  # Monday 0600
        "timeout": 120,
        "critical": False,
    },
    # Phase 1 Macro Redesign — 30-day backtest. Commander mandate 2026-05-01:
    # close the loop on the macro removal. No-ops until 2026-05-31, then runs
    # Mondays 0700. On +3pp ensemble lift recommends Phase 2; on +5pp queues
    # Phase 2 dispatch in qrf_extra_surfaces.json for next Overwatch brief.
    "phase1_backtest": {
        "script": "phase1_backtest.py",
        "schedule": {"hours": [(7, 0)], "weekdays": [0]},  # Monday 0700
        "timeout": 60,
        "critical": False,
    },
    # TFMF Shared Context mirror — copies the 5 .md files from iCloud into
    # the dashboard docroot so the tfmf-shared-context.html renderer can
    # fetch them. Without this, the dashboard tile is an orphan link
    # pointing to files that aren't HTTP-served. Hourly cadence is fine —
    # operator preferences/profile change rarely.
    "tfmf_shared_context_sync": {
        "script": "sync_tfmf_shared_context.py",
        "schedule": {"interval_min": 60},
        "timeout": 30,
        "critical": False,
    },
    "formation_v2_morning": {
        "script": "formation_v2.py",
        "args": ["--send-morning"],
        "schedule": {"hours": [(6, 0)]},  # 0600 daily
        "timeout": 30,
        "critical": False,
    },
    "financial_sync": {
        "script": "lifeos_data_sync.py",
        "schedule": {"interval_min": 60},
        "timeout": 60,
        "critical": True,
    },
    # RETIRED 2026-03-27: network_scan and network_watchdog replaced by
    # Network Command Center (localhost:8085). NCC runs continuous ARP discovery,
    # port scanning, IDS, and threat intel — all features these scripts provided.
    # Health checked via network_command_health task below.
    # Original scripts kept in scripts/ for reference.
    "file_cleanup": {
        "script": "file_cleanup_agent.py",
        "schedule": {"hours": [(2, 0)], "weekdays": [6]},  # Sunday 0200
        "timeout": 300,
        "critical": False,
    },
    "card_generator": {
        "script": "card_generator.py",
        "schedule": {"interval_min": 15},
        "timeout": 30,
        "critical": True,
    },
    "rocket_money": {
        "script": "rocket_money_ingest.py",
        "schedule": {"hours": [(7, 0)]},
        "timeout": 60,
        "critical": False,
    },
    "cc_payoff_monitor": {
        "script": "cc_payoff_monitor.py",
        "schedule": {"hours": [(7, 30)]},
        "timeout": 30,
        "critical": False,
    },
    # maintenance_alert: Daily 0710 (after rocket_money 0700, before cc_payoff 0730).
    # Reads dashboard/maintenance.json, computes due/overdue, creates Apple
    # Reminders for AMBER/RED items, fires iMessage when HIGH-tier items hit
    # lead-time or go overdue. Per Commander 2026-04-30 "C — full build now".
    # Notification architecture: Reminders for tasks, iMessage for HIGH-tier
    # transitions only. Calendar reserved for booked appointments (per SO).
    "maintenance_alert": {
        "script": "maintenance_alert.py",
        "schedule": {"hours": [(7, 10)]},
        "timeout": 60,
        "critical": False,
    },
    "calendar_mirror": {
        "script": "calendar_mirror.py",
        "schedule": {"interval_min": 60},
        "timeout": 60,
        "critical": False,
    },
    "pcc_mirror_health": {
        "script": "pcc_mirror_health.py",
        "schedule": {"interval_min": 15},
        "timeout": 15,
        "critical": False,
    },
    # truth_warden: Cross-platform reconciliation patrol (SO #12 enforcer).
    # Runs every 4h offset from pulse-monitor windows. Detects intent-vs-data
    # divergence, sync-no-op, mirror drift, stale-cached API responses.
    # Findings -> dashboard/truth_warden.json + alert_history (closed-loop).
    # Inaugural deployment 2026-04-29 after PCC scan_date Thu/Wed off-by-one
    # bug went undetected for ~14 days.
    "truth_warden": {
        "script": "truth_warden.py",
        "schedule": {"hours": [(2, 30), (6, 30), (10, 30), (14, 30), (18, 30), (22, 30)]},
        "timeout": 60,
        "critical": False,
    },
    "pcc_wed_reminder": {
        "script": "pcc_wed_check.py",
        "args": ["--mode", "reminder"],
        "schedule": {"hours": [(7, 0)], "weekdays": [2]},  # Wednesday 0700
        "timeout": 30,
        "critical": False,
    },
    "pcc_wed_verify": {
        "script": "pcc_wed_check.py",
        "args": ["--mode", "verify"],
        "schedule": {"hours": [(12, 0)], "weekdays": [2]},  # Wednesday 1200
        "timeout": 30,
        "critical": False,
    },
    "recomp_ingest": {
        "script": "recomp_ingestion.py",
        "schedule": {"hours": [(6, 32)]},
        "timeout": 60,
        "critical": False,
    },
    "substance_correlator": {
        "script": "substance_sleep_correlator.py",
        "schedule": {"hours": [(7, 15)]},
        "timeout": 30,
        "critical": False,
    },
    "sleep_optimizer": {
        "script": "sleep_optimization_engine.py",
        "schedule": {"hours": [(7, 30)]},
        "timeout": 60,
        "critical": False,
    },
    "learning_tracker": {
        "script": "learning_tracker.py",
        "schedule": {"hours": [(7, 20)]},
        "timeout": 30,
        "critical": False,
    },
    # RETIRED 2026-04-23 (Commander directive — noise prune):
    #   mastery_decay — dependent on dead Dev Portal (port 8083, 28d down).
    # ── Battle Rhythm (headless Claude Code skill invocation) ──────
    # ── Battle Rhythm: all use 480s orchestrator timeout (60s buffer over runner's 420s)
    "battle_morning": {
        "script": "battle_rhythm_runner.sh",
        "schedule": {"hours": [(6, 0)]},
        "timeout": 660,
        "critical": True,
        "args": ["morning"],
    },
    "battle_eod": {
        "script": "battle_rhythm_runner.sh",
        "schedule": {"hours": [(21, 0)]},
        "timeout": 660,
        "critical": True,
        "args": ["eod"],
    },
    "battle_cop_sync": {
        "script": "battle_rhythm_runner.sh",
        "schedule": {"hours": [(12, 10)]},
        "timeout": 900,  # Increased from 660 — runner increased to 840s, 60s outer buffer
        "critical": True,
        "args": ["sync"],
    },
    "battle_data": {
        "script": "data_pipeline.py",
        "schedule": {"hours": [(7, 30)]},
        "timeout": 180,
        "critical": False,
    },
    # RETIRED 2026-04-23 (Commander directive — noise prune):
    #   evolution_sweep — redundant with evolve_daily; RED 31 days.
    # ── Prediction Resolution Engine: daily 1615 (after US close, before EOD sweep)
    # 2026-04-19 Commander's directive — closes ACTIVE predictions where resolve_by <= today,
    # writes hit/miss to accuracy_log. This feeds the honest scoreboard replacing the 26.7% lie.
    # Pure Python (no AI call) — runs fast (<30s per 20 predictions).
    "prediction_resolution": {
        "script": "battle_rhythm_runner.sh",
        "schedule": {"hours": [(16, 15)], "weekdays": [0, 1, 2, 3, 4]},  # Mon-Fri 1615
        "timeout": 300,
        "critical": False,
        "args": ["resolution"],
    },
    # ── Predictive Engine: re-migrated 2026-04-21 from archived LaunchAgents
    # Timeline: com.s4.{macro-scout,stock-analyst,scenario-modeler} archived 2026-03-18;
    # never migrated into orchestrator. Result: prediction_data.json frozen at
    # 2026-03-19T18:00 for 33 days (Commander caught via predictions.html staleness).
    # synthesis_engine.py is the automatic final step of each of these modules,
    # so no separate task for it or portfolio_updater. resolution_engine is already
    # covered by prediction_resolution above. Schedule preserves archived cadence.
    # Starting non-critical to absorb any data_source rot from the 33-day silence;
    # flip stock_analyst to critical after 7 days stable.
    "macro_scout": {
        "script": "predictive_engine/macro_scout.py",
        "schedule": {"interval_min": 60},
        "timeout": 240,  # HTTP: FRED + F&G + calendar + synthesis; self-gates is_market_hours
        "critical": False,
    },
    "stock_analyst": {
        "script": "predictive_engine/stock_analyst.py",
        "schedule": {"hours": [(6, 45), (17, 0)], "weekdays": [0, 1, 2, 3, 4]},
        "timeout": 900,  # ~20 tickers × Claude + 3s finviz throttle + synthesis
        "critical": False,  # Flip to True after 7 days stable
    },
    "scenario_modeler": {
        "script": "predictive_engine/scenario_modeler.py",
        "schedule": {"hours": [(18, 0)], "weekdays": [0, 1, 2, 3, 4]},
        "timeout": 300,  # Single Claude call (3-5 scenarios) + synthesis
        "critical": False,
    },
    # ── OverwatchTDO: outer envelope = runner timeout + 60s buffer
    # 2026-03-23 Evolution: 660→780s (runner 600→720s) — evening runs hit 600-620s.
    # 2026-04-26 QRF_009: morning/midday envelope 780→900s. Runner stays 720s.
    # Root cause: orchestrator.log grown to 11K+ lines; unbounded read pushed
    # morning run from 623s (4/25) to 742s (4/26) = TIMEOUT. Two-part fix:
    # (1) prompt now scopes log read to last 200 lines (primary fix, cuts load);
    # (2) envelope increase from 780→900s provides 180s buffer over 720s runner
    # (same pattern as evolve_daily QRF_008). Both fixes applied together.
    "overwatch_morning": {
        "script": "battle_rhythm_runner.sh",
        "schedule": {"hours": [(5, 30)]},
        "timeout": 960,  # EE-Cycle13 2026-05-03: empirical 617s; runner 720s + 60s envelope buffer = 780s.
                         # Increased to 960s (was 900) for additional headroom on high-load mornings.
        "critical": True,
        "args": ["overwatch"],
    },
    "overwatch_midday": {
        "script": "battle_rhythm_runner.sh",
        "schedule": {"hours": [(12, 5)]},
        "timeout": 960,  # EE-Cycle13 2026-05-03: matched morning. empirical 616s; consistent timeout class.
        "critical": True,
        "args": ["overwatch"],
    },
    "overwatch_evening": {
        "script": "battle_rhythm_runner.sh",
        "schedule": {"hours": [(20, 0)]},
        "timeout": 420,  # Lighter evening mode — target <300s, 420s outer envelope
        "critical": True,
        "args": ["overwatch-evening"],
    },
    # ── Morning Formation ───────────────────────────────────────────────
    # Assembles formation_packet.json from existing data for iPhone session.
    # Runs at 0545 — after Overwatch morning (0530), before Commander's
    # expected Formation window (0630-0730). Pure JSON assembly, <5 sec.
    # Added 2026-03-25 per Morning Formation Protocol spec.
    "formation_packet": {
        "script": "formation_packet_generator.py",
        "schedule": {"hours": [(5, 45)]},
        "timeout": 30,
        "critical": True,
    },
    # Claude CLI version guard — detects silent auto-updates, runs smoke test, rolls back if broken.
    # qrf_003 escalation (2026-03-25): v2.1.83 auto-updated at 02:24 and broke ALL headless tasks.
    # Runs at 02:30 (after typical ~02:00 auto-update window) and 10:00 (mid-morning verification).
    # Evolution Engine 2026-03-25: new guard added as production safety net.
    "claude_version_guard_0230": {
        "script": "claude_version_guard.py",
        "schedule": {"hours": [(2, 30)]},
        "timeout": 90,
        "critical": True,
    },
    "claude_version_guard_1000": {
        "script": "claude_version_guard.py",
        "schedule": {"hours": [(10, 0)]},
        "timeout": 90,
        "critical": False,
    },
    # Regenerates BRIEFING_PACKET.md for claude.ai Project.
    # Runs daily at 0550 — after formation_packet (0545), before Commander's
    # Formation window (0630-0730). Keeps claude.ai Project data fresh.
    # Added 2026-03-25 — was previously manual-only, caused 11-day staleness.
    "briefing_packet": {
        "script": "briefing_packet_generator.py",
        "schedule": {"hours": [(5, 50)]},
        "timeout": 30,
        "critical": True,
    },
    # Watches iCloud for Formation responses, updates downstream JSONs.
    # Every 15 min — matches orchestrator cycle. Silent when no new files.
    "formation_ingest": {
        "script": "formation_ingest.py",
        "schedule": {"interval_min": 15},
        "timeout": 30,
        "critical": True,
    },
    "battle_rhythm_ingest": {
        "script": "battle_rhythm_ingestor.py",
        "schedule": {"interval_min": 60},
        "timeout": 30,
        "critical": False,
    },
    # ── OverwatchTDO Standing Patrols ────────────────────────────────
    # RETIRED 2026-04-23 (Commander directive — "they are noise"):
    #   patrol_horizon, patrol_relationship, patrol_opportunity.
    #   Commander confirmed outputs not read. JSONs fed nothing downstream
    #   of value. Save tokens + noise.
    "patrol_accountability": {
        "script": "battle_rhythm_runner.sh",
        "schedule": {"hours": [(19, 0)]},
        "timeout": 540,  # Evolution Engine 2026-03-26: increased from 420 (empirically hit 372s > 360s runner limit)
        "critical": True,
        "args": ["accountability"],
    },
    "patrol_prophet": {
        "script": "battle_rhythm_runner.sh",
        "schedule": {"hours": [(19, 30)], "weekdays": [6]},  # Sunday 1930 only (2026-04-23: reduced from daily — 1 HISTORY ref/month didn't justify daily claude -p)
        "timeout": 660,
        "critical": False,
        "args": ["prophet"],
    },
    # patrol_pulse: 2026-04-23 Commander directive — reduced from 6/day to 3/day.
    # Kept: 0600 (start of operational day), 1400 (mid-day), 2200 (pre-sleep).
    # Retired: 0200, 1000, 1800. Overnight pulse check was redundant with watchdog.
    "patrol_pulse_0600": {
        "script": "battle_rhythm_runner.sh",
        "schedule": {"hours": [(6, 0)]},
        "timeout": 420,  # Runner 360s + 60s buffer (EE-Cycle12 2026-05-02: pulse_2200 empirical 310.5s TIMEOUT; 300→360s)
        "critical": True,
        "args": ["pulse"],
    },
    "patrol_pulse_1400": {
        "script": "battle_rhythm_runner.sh",
        "schedule": {"hours": [(14, 0)]},
        "timeout": 420,  # Runner 360s + 60s buffer (EE-Cycle12 2026-05-02: pulse_2200 empirical 310.5s TIMEOUT; 300→360s)
        "critical": True,
        "args": ["pulse"],
    },
    "patrol_pulse_2200": {
        "script": "battle_rhythm_runner.sh",
        "schedule": {"hours": [(22, 0)]},
        "timeout": 420,  # Runner 360s + 60s buffer (EE-Cycle12 2026-05-02: pulse_2200 empirical 310.5s TIMEOUT; 300→360s)
        "critical": True,
        "args": ["pulse"],
    },
    "evolve_daily": {
        "script": "battle_rhythm_runner.sh",
        "schedule": {"hours": [(0, 0)]},
        # 2026-04-29 Evolution Cycle 9: shifted from 23:00 → 00:00 (midnight).
        # Root cause: Max subscription cap exhausts between 20:58-21:59 nightly.
        # Empirical reset window: 23:10-23:50 ET (variable by ~40 min day-to-day).
        # 23:00 schedule falls BEFORE the reset on both observed nights (4/27, 4/28).
        # Midnight is definitively post-reset regardless of variance. See QRF_012a.
        "timeout": 1080,  # Evolution 2026-04-22: runner 750→900s; outer 810→960s. 2026-04-27 QRF_010: scope fix applied (alert_history + evolution_journal scoped); outer 960→1080s (180s buffer over 900s runner) as defense-in-depth while scope fix proves out over next 3 runs.
        "critical": False,
        "args": ["evolve-daily"],
    },
    "evolution_dashboard_adapter": {
        "script": "evolution_dashboard_adapter.py",
        "schedule": {"hours": [(0, 15)]},  # 15 min after evolve_daily (shifted 23:15 → 00:15 with evolve_daily)
        "timeout": 30,
        "critical": False,
        "args": [],
    },
    # ── Weekly Agents ────────────────────────────────────────────────
    # RETIRED 2026-04-23 (Commander directive — noise prune, 6 tasks):
    #   evolve_weekly       — never succeeded; evolve_daily covers this ground.
    #   patrol_network      — never succeeded; career network handled manually/quarterly.
    #   patrol_shield       — Commander confirmed output not read ("noise").
    #   patrol_legacy       — 0 HISTORY refs; kids' letters authored by Commander directly.
    #   patrol_ecosystem    — 605h stale output; claude_version_guard covers breakage risk.
    # ── Scout Dispatch: staggered weekly — 2 scouts/day Mon-Wed, 1 Thu at 0400
    "scout_dispatch_mon": {
        "script": "scout_dispatcher.py",
        "schedule": {"hours": [(4, 0)], "weekdays": [0]},  # Monday 0400
        "timeout": 900,
        "critical": False,
        "args": [],
    },
    "scout_dispatch_tue": {
        "script": "scout_dispatcher.py",
        "schedule": {"hours": [(4, 0)], "weekdays": [1]},  # Tuesday 0400
        "timeout": 900,
        "critical": False,
        "args": [],
    },
    "scout_dispatch_wed": {
        "script": "scout_dispatcher.py",
        "schedule": {"hours": [(4, 0)], "weekdays": [2]},  # Wednesday 0400
        "timeout": 900,
        "critical": False,
        "args": [],
    },
    "scout_dispatch_thu": {
        "script": "scout_dispatcher.py",
        "schedule": {"hours": [(4, 0)], "weekdays": [3]},  # Thursday 0400
        "timeout": 600,
        "critical": False,
        "args": [],
    },
    "intel_card_generator": {
        "script": "intelligence_card_generator.py",
        "schedule": {"hours": [(4, 30)]},  # Daily 0430 — after any scout run
        "timeout": 120,
        "critical": False,
        "args": [],
    },
    # ── Network Command Center health check ────────────────────────
    # Verifies the Network Command Center API (localhost:8085) is responding.
    # Every 15 min — matches orchestrator cycle. Alerts if down 3x consecutive.
    # Added 2026-03-27 for Network Command Center integration.
    "network_command_health": {
        "script": "network_command_health.sh",
        "schedule": {"interval_min": 15},
        "timeout": 10,
        "critical": True,
    },
    # ── Weekly Spend Pulse (Rocket Money 7-day pull) ───────────────
    # Friday 17:00 — drives Rocket Money export → fetches link from Gmail
    # → ingests via fixed rocket_money_ingest.py (dedupe + merge-safe as
    # of 2026-05-01) → writes spend_pulse_7d → iMessages Commander.
    # Critical: depends on Playwright Chrome having a live Rocket Money
    # session. If session expired, agent must alert Commander to re-auth.
    "battle_weekly_spend": {
        "script": "battle_rhythm_runner.sh",
        "schedule": {"hours": [(17, 0)], "weekdays": [4]},  # Friday 1700
        "timeout": 900,  # full pipeline incl. ~3 min Gmail wait
        "critical": True,
        "args": ["weekly-spend-pulse"],
    },
    # ── Weekly PayPal Pulse (Emergency Fund balance check) ─────────
    # Friday 17:15 — 15 min after spend pulse so Playwright is warm.
    # Drives Playwright to PayPal Savings, scrapes total + Emergency
    # Fund goal balance, updates owens_future_data.json milestones,
    # iMessages Commander on weekly delta. Catches stale-tracking like
    # the 5-week drift discovered 2026-05-01 ($5K stale → $9,843 actual).
    "battle_weekly_paypal": {
        "script": "battle_rhythm_runner.sh",
        "schedule": {"hours": [(17, 15)], "weekdays": [4]},  # Friday 1715
        "timeout": 360,  # UI scrape only, no email wait
        "critical": True,
        "args": ["weekly-paypal-pulse"],
    },
    # ── Monthly Financial Forensics (CFP/CPA-grade analysis) ───────
    # Polls daily 0700, but the runner case GUARDS to only execute on
    # the 1st of each month (orchestrator schema lacks monthdays). On
    # day 1, dispatches financial-reviewer agent to produce a full
    # personal income statement: fixed/variable/discretionary split,
    # subscription audit, tax-bucket awareness, lifecycle ramps, and
    # actionable findings. Output to iCloud as monthly forensics file.
    # Catches the kind of drift discovered 2026-05-01 (broken category
    # mapper, fake $1,156 subscription number, hidden Lilly-bonus-masked
    # April deficit). Replaces ad-hoc forensics with battle rhythm.
    "battle_monthly_forensics": {
        "script": "battle_rhythm_runner.sh",
        "schedule": {"hours": [(7, 0)]},  # daily — runner guards to day 1
        "timeout": 1200,  # full agent dispatch + write, ~7-15 min observed
        "critical": True,
        "args": ["monthly-forensics"],
    },
}


# ── Health State ──────────────────────────────────────────────────────

def load_health() -> dict:
    """Load task health state from disk."""
    if HEALTH_FILE.exists():
        try:
            return json.loads(HEALTH_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"meta": {"created": now_iso()}, "tasks": {}}


def save_health(health: dict):
    """Atomically write task health state.

    Before writing, any task entry that exists in the JSON but is no longer
    present in the TASKS dict is automatically set to RETIRED status.  This
    prevents QRF from having to manually re-retire the same entries every time
    the orchestrator cycles (root cause of qrf_007/008/009a/011b repeat pattern).
    """
    ts = now_iso()
    health["meta"]["updated"] = ts

    for task_id, entry in health.get("tasks", {}).items():
        if task_id not in TASKS and entry.get("status") != "RETIRED":
            entry["status"] = "RETIRED"
            if "retired_at" not in entry:
                entry["retired_at"] = ts
            if "retired_reason" not in entry:
                entry["retired_reason"] = "Auto-retired: task removed from TASKS dict."

    tmp = HEALTH_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(health, indent=2))
    tmp.rename(HEALTH_FILE)


def get_task_health(health: dict, name: str) -> dict:
    """Get or create health record for a task."""
    if name not in health["tasks"]:
        health["tasks"][name] = {
            "status": "UNKNOWN",
            "last_run": None,
            "last_success": None,
            "last_error": None,
            "consecutive_failures": 0,
            "total_runs": 0,
            "total_failures": 0,
        }
    return health["tasks"][name]


# ── Scheduling ────────────────────────────────────────────────────────

def is_due(task_cfg: dict, task_health: dict, now: datetime) -> bool:
    """Check if a task should run this cycle (15-min granularity)."""
    sched = task_cfg["schedule"]

    if "interval_min" in sched:
        # Interval-based: run if last run was >= interval_min ago
        last = task_health.get("last_run")
        if not last:
            return True
        try:
            last_dt = datetime.fromisoformat(last)
            elapsed = (now - last_dt).total_seconds() / 60
            return elapsed >= sched["interval_min"]
        except (ValueError, TypeError):
            return True

    if "hours" in sched:
        # Calendar-based: run if current time is within 15 min of a scheduled slot
        # AND we haven't already run in this window
        for hour, minute in sched["hours"]:
            scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            delta = abs((now - scheduled).total_seconds())
            if delta <= 900:  # within 15-minute window
                # Check weekday restriction
                if "weekdays" in sched:
                    if now.weekday() not in sched["weekdays"]:
                        continue
                # Check we haven't run in this window already
                # FIX 2026-03-26 Evolution Engine: Compare last_run to SCHEDULED time,
                # not to now. The old check (now - last_run < 900s) fails when a task
                # completes and then the next cycle fires 15+ min later — last_run is
                # now >900s from now even though it ran in the same window. This caused
                # double-execution of battle_eod (20:48 + 21:06) and overwatch_evening.
                last = task_health.get("last_run")
                if last:
                    try:
                        last_dt = datetime.fromisoformat(last)
                        if abs((last_dt - scheduled).total_seconds()) < 900:
                            continue  # Already ran this window
                    except (ValueError, TypeError):
                        pass
                return True

    return False


# ── Execution ─────────────────────────────────────────────────────────

def run_task(name: str, task_cfg: dict) -> tuple[bool, str, float]:
    """Execute a task script. Returns (success, output, duration_seconds)."""
    script_path = SCRIPTS_DIR / task_cfg["script"]
    if not script_path.exists():
        return False, f"Script not found: {script_path}", 0.0

    # Shell scripts run directly; Python scripts run via PYTHON interpreter
    if str(script_path).endswith(".sh"):
        args = ["/bin/bash", str(script_path)] + task_cfg.get("args", [])
    else:
        args = [PYTHON, str(script_path)] + task_cfg.get("args", [])
    timeout = task_cfg.get("timeout", 120)

    start = time.monotonic()
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(SCRIPTS_DIR),
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        duration = time.monotonic() - start
        output = (result.stdout or "") + (result.stderr or "")
        output = output[-2000:]  # Keep last 2000 chars

        if result.returncode == 0:
            return True, output.strip(), duration
        elif result.returncode == 75:
            # 2026-04-29: EX_TEMPFAIL — battle_rhythm_runner.sh emits 75 on
            # rate-limit hits (Max subscription cap exhausted). Treat as
            # transient/deferred rather than hard failure so we don't pollute
            # CCIR #9 with false RED status. Caller checks output prefix
            # 'RATE_LIMIT' to distinguish.
            return False, f"DEFERRED (rate-limit): {output.strip()}", duration
        else:
            return False, f"Exit code {result.returncode}: {output.strip()}", duration

    except subprocess.TimeoutExpired:
        duration = time.monotonic() - start
        return False, f"TIMEOUT after {timeout}s", duration
    except Exception as e:
        duration = time.monotonic() - start
        return False, f"Exception: {str(e)}", duration


# ── Alerting ──────────────────────────────────────────────────────────

def send_alert(name: str, error: str):
    """Alert Commander via s6_alert.py."""
    try:
        sys.path.insert(0, str(SCRIPTS_DIR))
        from s6_alert import alert, CRITICAL
        alert(
            CRITICAL,
            f"Orchestrator: {name} failed {ALERT_THRESHOLD}x",
            f"Task '{name}' has failed {ALERT_THRESHOLD} consecutive times.\n"
            f"Last error: {error[:300]}\n"
            f"Fix the script or mark non-critical.",
        )
    except Exception as e:
        log_msg(f"ALERT DELIVERY FAILED for {name}: {e}")


# ── Logging ───────────────────────────────────────────────────────────

def log_msg(msg: str):
    """Append to rotating log file."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}\n"

    # Rotate if too large
    if LOG_FILE.exists() and LOG_FILE.stat().st_size > MAX_LOG_BYTES:
        rotated = LOG_FILE.with_suffix(".log.1")
        if rotated.exists():
            rotated.unlink()
        LOG_FILE.rename(rotated)

    with open(LOG_FILE, "a") as f:
        f.write(line)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ── Lock ──────────────────────────────────────────────────────────────

def acquire_lock():
    """Prevent overlapping orchestrator runs."""
    try:
        lock_fd = open(LOCK_FILE, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
        return lock_fd
    except (IOError, OSError):
        return None


# ── Main ──────────────────────────────────────────────────────────────

def run_cycle(dry_run=False, force_task=None):
    """Main orchestrator cycle."""
    now = datetime.now()
    health = load_health()
    ran = 0
    skipped = 0

    tasks_to_run = TASKS.items()
    if force_task:
        if force_task not in TASKS:
            print(f"Unknown task: {force_task}")
            print(f"Available: {', '.join(TASKS.keys())}")
            return
        tasks_to_run = [(force_task, TASKS[force_task])]

    for name, cfg in tasks_to_run:
        th = get_task_health(health, name)

        # Check if due (skip check if force-running)
        if not force_task and not is_due(cfg, th, now):
            skipped += 1
            continue

        if dry_run:
            print(f"  WOULD RUN: {name} ({cfg['script']})")
            ran += 1
            continue

        # Execute
        log_msg(f"START {name}")
        success, output, duration = run_task(name, cfg)

        # Update health
        th["last_run"] = now_iso()
        th["total_runs"] = th.get("total_runs", 0) + 1

        if success:
            th["status"] = "GREEN"
            th["last_success"] = now_iso()
            th["consecutive_failures"] = 0
            th["last_duration"] = round(duration, 1)
            th["last_error"] = None
            log_msg(f"OK    {name} ({duration:.1f}s)")
        elif output.startswith("DEFERRED (rate-limit)"):
            # 2026-04-29: rate-limit deferred — not a failure, just capacity.
            # Status DEFERRED instead of RED. consecutive_failures NOT incremented.
            # No alert. Task will retry on next scheduled cycle.
            th["status"] = "DEFERRED"
            th["last_error"] = output[:500]
            th["last_duration"] = round(duration, 1)
            log_msg(f"DEFER {name} ({duration:.1f}s): rate-limit, retry next cycle")
        else:
            th["status"] = "RED"
            th["last_error"] = output[:500]
            th["consecutive_failures"] = th.get("consecutive_failures", 0) + 1
            th["total_failures"] = th.get("total_failures", 0) + 1
            th["last_duration"] = round(duration, 1)
            log_msg(f"FAIL  {name} ({duration:.1f}s): {output[:200]}")

            # Alert if critical and threshold reached
            if cfg.get("critical") and th["consecutive_failures"] >= ALERT_THRESHOLD:
                send_alert(name, output)
                th["last_alert"] = now_iso()

        ran += 1

    save_health(health)

    total = len(TASKS)
    green = sum(1 for t in health["tasks"].values() if t.get("status") == "GREEN")
    red = sum(1 for t in health["tasks"].values() if t.get("status") == "RED")

    if dry_run:
        print(f"\nDry run: {ran} tasks would run, {skipped} skipped")
    else:
        log_msg(f"CYCLE {ran} ran, {skipped} skipped | {green}/{total} GREEN, {red} RED")


def print_status():
    """Print task health summary."""
    health = load_health()
    print("=" * 60)
    print("  Life OS Orchestrator — Task Health")
    print("=" * 60)
    updated = health.get("meta", {}).get("updated", "never")
    print(f"  Last cycle: {updated}")
    print()

    for name, cfg in TASKS.items():
        th = health.get("tasks", {}).get(name, {})
        status = th.get("status", "UNKNOWN")
        icon = {"GREEN": "G", "RED": "R", "AMBER": "A", "UNKNOWN": "?"}.get(status, "?")
        crit = "CRIT" if cfg.get("critical") else "    "
        last = th.get("last_run", "never")
        fails = th.get("consecutive_failures", 0)
        fail_str = f" [{fails}x FAIL]" if fails > 0 else ""
        print(f"  [{icon}] {crit} {name:<22} last: {last}{fail_str}")

    total = len(TASKS)
    green = sum(
        1 for t in health.get("tasks", {}).values() if t.get("status") == "GREEN"
    )
    print()
    print(f"  {green}/{total} GREEN | Updated: {updated}")
    print("=" * 60)


def main():
    if "--status" in sys.argv:
        print_status()
        return

    if "--dry-run" in sys.argv:
        print("Life OS Orchestrator — DRY RUN")
        run_cycle(dry_run=True)
        return

    if "--run" in sys.argv:
        idx = sys.argv.index("--run")
        if idx + 1 < len(sys.argv):
            task_name = sys.argv[idx + 1]
            lock = acquire_lock()
            if not lock:
                print("Another orchestrator is running. Use --status to check.")
                return
            run_cycle(force_task=task_name)
            return
        else:
            print("Usage: --run TASK_NAME")
            return

    # Normal execution: acquire lock and run cycle
    lock = acquire_lock()
    if not lock:
        log_msg("SKIP — another instance running")
        return

    log_msg("CYCLE START")
    try:
        run_cycle()
    except Exception as e:
        log_msg(f"CYCLE ERROR: {e}")
        raise


if __name__ == "__main__":
    main()
