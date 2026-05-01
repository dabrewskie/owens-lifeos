#!/bin/bash
# ─────────────────────────────────────────────────────────────────
# Battle Rhythm Runner — Headless Claude Code skill invocation
#
# Runs battle rhythm skills (morning-sweep, eod-close, cop-sync, etc.)
# via `claude -p` in non-interactive mode. Called by the orchestrator
# or cron at scheduled times.
#
# Usage:
#   ./battle_rhythm_runner.sh morning    # Morning sweep
#   ./battle_rhythm_runner.sh eod        # End of day close
#   ./battle_rhythm_runner.sh sync       # COP sync
#   ./battle_rhythm_runner.sh data       # Data pipeline ingest
#   ./battle_rhythm_runner.sh overwatch   # OverwatchTDO superagent
#   ./battle_rhythm_runner.sh evolution  # Weekly evolution sweep
#   ./battle_rhythm_runner.sh resolution # Daily prediction resolution (NEW 2026-04-19)
#   ./battle_rhythm_runner.sh status     # System status check
#   ./battle_rhythm_runner.sh test       # Quick test (2+2)
# ─────────────────────────────────────────────────────────────────

set -uo pipefail
# Note: -e intentionally omitted — the run_with_timeout function needs
# to handle non-zero exits from kill/wait without the script aborting

# COST LEAK DEFENSE (2026-04-23): Force `claude -p` to use the Max
# subscription's OAuth token by unsetting any raw API key that may have
# leaked into the environment. If ANTHROPIC_API_KEY is set, Claude Code's
# auth precedence bills the raw API instead of the subscription — ~$10/day
# across 30+ daily orchestrator calls. Belt-and-suspenders with ~/.zprofile.
unset ANTHROPIC_API_KEY

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/cleanup_logs"
ICLOUD="$HOME/Library/Mobile Documents/com~apple~CloudDocs"
CLAUDE_BIN="$HOME/.local/bin/claude"
CCIR_GEN="$SCRIPT_DIR/ccir_generator.py"
SYS_HEALTH="$SCRIPT_DIR/system_health_check.py"
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
TMPOUT=$(mktemp /tmp/battle_rhythm.XXXXXX)

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Log function
log() {
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] BATTLE_RHYTHM: $*" >> "$LOG_DIR/battle_rhythm.log"
}

# Cleanup temp file on exit
cleanup() { rm -f "$TMPOUT"; }
trap cleanup EXIT

# ─────────────────────────────────────────────────────────────────
# CCIR refresh — deterministic pre-step for sweeps that need fresh
# Commander's Critical Information Requirements state. Fast (<1s),
# idempotent, safe to run repeatedly. Failure is logged but does NOT
# abort the sweep (AI path uses prior ccir_cards.json as fallback).
# ─────────────────────────────────────────────────────────────────
refresh_ccirs() {
    if [ ! -f "$CCIR_GEN" ]; then
        log "CCIR_GEN missing at $CCIR_GEN — skipping"
        return 0
    fi
    local out
    out=$(python3 "$CCIR_GEN" 2>&1) || {
        log "CCIR_REFRESH FAIL: $out"
        return 0  # non-fatal
    }
    log "CCIR_REFRESH OK: $out"
}

# ─────────────────────────────────────────────────────────────────
# System health check — infrastructure/plumbing probes. Runs AFTER
# refresh_ccirs so the most recent CCIR state is preserved; this script
# only touches entries with domain='system' in ccir_cards.json.
# Fast (<3s), idempotent, safe to run repeatedly. Failure is logged but
# does NOT abort the sweep.
# ─────────────────────────────────────────────────────────────────
refresh_system_health() {
    if [ ! -f "$SYS_HEALTH" ]; then
        log "SYS_HEALTH missing at $SYS_HEALTH — skipping"
        return 0
    fi
    local out
    out=$(python3 "$SYS_HEALTH" 2>&1) || {
        log "SYS_HEALTH FAIL: $out"
        return 0  # non-fatal
    }
    log "SYS_HEALTH OK: $out"
}

# macOS-compatible timeout: run command in background, kill after N seconds
run_with_timeout() {
    local max_seconds="$1"
    shift
    "$@" > "$TMPOUT" 2>&1 &
    local pid=$!
    local elapsed=0
    while kill -0 "$pid" 2>/dev/null; do
        sleep 5
        elapsed=$((elapsed + 5))
        if [ "$elapsed" -ge "$max_seconds" ]; then
            kill "$pid" 2>/dev/null || true
            sleep 2
            # Force kill if still alive
            kill -9 "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
            return 124  # timeout exit code
        fi
    done
    wait "$pid" 2>/dev/null
    local exit_code=$?
    return $exit_code
}

# Check Claude CLI exists
if [ ! -x "$CLAUDE_BIN" ]; then
    log "ERROR: Claude CLI not found at $CLAUDE_BIN"
    exit 1
fi

MODE="${1:-help}"

case "$MODE" in
    morning)
        # 2026-04-21 QRF: /sweep morning replaced with inline prompt — /sweep slash command
        # broken in claude CLI v2.1.114+ ("Unknown command: /sweep"). Same fix pattern
        # used for 'evolution' mode on 2026-04-19. Inline prompt mirrors SKILL.md procedure.
        refresh_ccirs          # Fresh CCIR state (domain metrics)
        refresh_system_health  # Fresh infra state (plumbing)
        PROMPT="You are Tory Owens' morning sweep agent. Run the MORNING SWEEP for today. Procedure: (1) Dispatch 5 domain agents in parallel (domain-medical, domain-finance, domain-family, domain-security, domain-operations) to gather overnight data; (2) Pull today's and tomorrow's calendar events; (3) Read ~/Documents/S6_COMMS_TECH/dashboard/pending_actions.json for anticipation engine output; (4) Read ~/Documents/S6_COMMS_TECH/dashboard/task_health.json for orchestrator health. Then write the canonical morning brief to ~/Library/Mobile Documents/com~apple~CloudDocs/morning-sweep-latest.md using this template: # MORNING SWEEP — [Day, Month Date, Year] | Status line | ## BLUF | ## HEALTH OPS | ## FINANCIAL INTEL | ## FAMILY OPS | ## LIFE ADMIN | ## DAILY DEVOTION | ## COACHING CHALLENGE | ## TODAY'S BATTLE PLAN | ## UNCOMFORTABLE TRUTH. After writing, run: python3 ~/Documents/S6_COMMS_TECH/scripts/lifeos_data_sync.py"
        OUTPUT_FILE="$ICLOUD/morning-sweep-latest.md"
        TIMEOUT=600
        CLAUDE_EXTRA_ARGS="--agent life-intelligence"
        ;;
    eod)
        # 2026-04-21 QRF: /sweep eod replaced with inline prompt — same root cause as morning.
        refresh_ccirs          # End-of-day threshold re-evaluation
        refresh_system_health  # End-of-day infra health
        PROMPT="You are Tory Owens' EOD close agent. Run the END OF DAY CLOSE for today. Procedure: (1) Read today's calendar for what was scheduled; (2) Run python3 ~/Documents/S6_COMMS_TECH/scripts/health_auto_export_reader.py for health data; (3) Check Gmail for significant items; (4) Read ~/Library/Mobile Documents/com~apple~CloudDocs/COP.md for current state. Then write the canonical EOD close to ~/Library/Mobile Documents/com~apple~CloudDocs/eod-close-latest.md using this template: # EOD CLOSE — [Day, Month Date, Year] | ## EXECUTED TODAY | ## HEALTH OPS | ## FAMILY PRESENCE | ## FINANCIAL INTEL | ## CARRY FORWARD | ## FLAGS. After writing: (a) Update COP.md running estimates and action item status; (b) Append today's family presence to ~/Documents/S6_COMMS_TECH/dashboard/presence_log.json (ask Commander if no data: dinner present? phone down? 1-on-1 time?); (c) Run python3 ~/Documents/S6_COMMS_TECH/scripts/lifeos_data_sync.py"
        OUTPUT_FILE="$ICLOUD/eod-close-latest.md"
        TIMEOUT=600
        CLAUDE_EXTRA_ARGS="--agent life-intelligence"
        ;;
    sync)
        # 2026-04-21 QRF: /sweep sync replaced with inline prompt — same root cause.
        refresh_ccirs          # Dashboard needs fresh CCIRs for COP sync
        refresh_system_health  # COP sync carries infra state too
        PROMPT="You are Tory Owens' COP sync agent. Run the COP SYNC. Procedure: STEP 0 — Process completion queue FIRST: read ~/Library/Mobile Documents/com~apple~CloudDocs/completion_queue.jsonl, process unprocessed entries (find matching COP action items by action_id/description, mark COMPLETE, set processed=true, rewrite file). Then STEP 1 — Read full ~/Library/Mobile Documents/com~apple~CloudDocs/COP.md and check every section timestamp for staleness (0-7 days GREEN, 8-14 AMBER, 15+ RED). STEP 2 — Dispatch 5 domain agents in parallel for stale sections (domain-medical, domain-finance, domain-family, domain-security, domain-operations). STEP 3 — Update stale COP sections with fresh data. STEP 4 — Route cross-domain flags. STEP 5 — Evaluate each CCIR against current data. STEP 6 — Run python3 ~/Documents/S6_COMMS_TECH/scripts/lifeos_data_sync.py. STEP 7 — Write output to ~/Library/Mobile Documents/com~apple~CloudDocs/cop-sync-latest.md"
        OUTPUT_FILE="$ICLOUD/cop-sync-latest.md"
        TIMEOUT=840  # Increased from 600 — cop-sync dispatches 5 domain agents, empirically times out at ~430-600s
        CLAUDE_EXTRA_ARGS="--agent life-intelligence"
        ;;
    data)
        # 2026-04-21 QRF: /sweep data replaced with inline prompt — same root cause.
        PROMPT="You are Tory Owens' data pipeline agent. Run the DATA PIPELINE INGEST. Procedure: (1) Run python3 ~/Documents/S6_COMMS_TECH/scripts/health_auto_export_reader.py; (2) Run python3 ~/Documents/S6_COMMS_TECH/scripts/recomp_ingestion.py; (3) Check Downloads for Rocket Money CSV — if found, run python3 ~/Documents/S6_COMMS_TECH/scripts/rocket_money_ingest.py; (4) Pull today's calendar via MCP gcal_list_events; (5) Report data freshness for all sources; (6) Run python3 ~/Documents/S6_COMMS_TECH/scripts/lifeos_data_sync.py; (7) Write output to ~/Library/Mobile Documents/com~apple~CloudDocs/data-ingest-latest.md"
        OUTPUT_FILE="$ICLOUD/data-ingest-latest.md"
        TIMEOUT=540
        CLAUDE_EXTRA_ARGS="--agent life-intelligence"
        ;;
    overwatch)
        # NEW ARCHITECTURE 2026-04-30: slim prompt, single input file.
        # state_synthesizer.py builds overwatch_input.json with the full system snapshot
        # in <5s of pure Python. Overwatch reads ONLY that file → no per-call file gathering
        # in the LLM call → expected duration <300s, well under the 480s timeout envelope.
        # Run synthesizer just-in-time so the snapshot reflects the current minute.
        python3 "$SCRIPT_DIR/state_synthesizer.py" >> "$LOG_DIR/state_synth.log" 2>&1 || \
            log "WARN: state_synthesizer failed; Overwatch will use prior snapshot"

        HOUR=$(date +"%H")
        if   [ "$HOUR" -lt 10 ]; then TOD="morning"
        elif [ "$HOUR" -lt 16 ]; then TOD="midday"
        else                          TOD="evening"
        fi
        PROMPT="You are OverwatchTDO. ${TOD} run.

Read EXACTLY ONE FILE: ~/Documents/S6_COMMS_TECH/dashboard/overwatch_input.json

That JSON contains the full system snapshot — COP, CCIR, action_queue, pending_actions,
task_health, health_vitals, iron_discipline state, scans, formation, watchdog, drift,
active_concerns, previous_overwatch_brief, journal_recent, orchestrator_log_recent,
battle_rhythm_freshness, agent_freshness, financial_snapshot, family_pulse,
calendar_peek_24h, and rocket_money status. Everything you need is in there.

Do NOT read any other files. The synthesizer already gathered them.

Synthesize across the snapshot and write your brief to:
  ~/Library/Mobile Documents/com~apple~CloudDocs/overwatch-latest.md

Then append a short journal entry to:
  ~/Documents/S6_COMMS_TECH/dashboard/superagent_journal.md

Then update active_concerns in:
  ~/Documents/S6_COMMS_TECH/dashboard/superagent_state.json
(Refresh last_seen for re-fired patterns. Mark resolved concerns. Add NEW concerns
when you spot novel patterns in the snapshot.)

If anything is critical (RED status, hard deadlines today/tomorrow, accountability
gaps >7 days), send iMessage via:
  python3 ~/Documents/S6_COMMS_TECH/scripts/s6_alert.py

Brief structure:
- BLUF: top 3 issues right now
- WHAT'S WORKING: 2-3 wins / on-track items
- WHAT'S DRIFTING: 2-3 things showing slow degradation
- WHAT NEEDS DECISION: 1-2 things requiring Tory's input
- COUNSEL (one paragraph): the long view from the mantled frame"
        OUTPUT_FILE="$ICLOUD/overwatch-latest.md"
        TIMEOUT=600  # EE-Cycle11 2026-05-01: 150KB overwatch_input.json at ~3.3s/KB → 495s empirical
                     # (exceeded 480s → TIMEOUT). Cap reduction in state_synthesizer targets ~115KB → ~380s
                     # steady state. 600s provides 100s safety headroom. Orchestrator outer=900s unchanged.
        CLAUDE_EXTRA_ARGS="--agent overwatch-tdo"
        ;;
    overwatch-evening)
        # NEW ARCHITECTURE 2026-04-30: same single-input-file pattern.
        python3 "$SCRIPT_DIR/state_synthesizer.py" >> "$LOG_DIR/state_synth.log" 2>&1 || \
            log "WARN: state_synthesizer failed; evening Overwatch will use prior snapshot"

        PROMPT="You are OverwatchTDO running EVENING REFLECTION (lighter brief).

Read EXACTLY ONE FILE: ~/Documents/S6_COMMS_TECH/dashboard/overwatch_input.json

Focus on:
- accountability section (resolutions today, deferrals, dismissals)
- formation reply (if logged today)
- macros_today vs target (did Tory hit fuel doctrine)
- iron_discipline.today_session (was it logged)
- 1 sentence: what was the day's win, what was missed

Write a SHORT (<=30 line) reflection to:
  ~/Library/Mobile Documents/com~apple~CloudDocs/overwatch-latest.md

Append journal entry. Update state file if material concerns shifted.
Do NOT dispatch Devil's Advocate or other agents."
        OUTPUT_FILE="$ICLOUD/overwatch-latest.md"
        TIMEOUT=240  # was 360; lighter mode, smaller snapshot read
        CLAUDE_EXTRA_ARGS="--agent overwatch-tdo"
        ;;
    evolution)
        # 2026-04-19: replaced dead `/sentinel evolve` slash command (unregistered
        # in current claude CLI → "Unknown command: /sentinel") with the working
        # --agent evolution-engine invocation pattern used by evolve-daily/-weekly.
        # Sunday 1800 weekly cadence fed by lifeos_orchestrator.TASKS['evolution_sweep'].
        PROMPT="You are the evolution-engine agent running the WEEKLY EVOLUTION SWEEP. Read qrf_repair_log.json, task_health.json, orchestrator.log, pulse_status.json, alert_history.json, superagent_journal.md, superagent_state.json, accountability_report.json, relationship_intel.json, pattern_prophet_output.json, and the last 30 days of health/financial data. Run the full 7-scout learning protocol: detect patterns across the week, synthesize Deep Researcher archives if 3+ new files exist, write new anticipation rules if warranted, update evolution_data.json and evolution_journal.md, teach Overwatch new correlations. Alert via python3 ~/Documents/S6_COMMS_TECH/scripts/s6_alert.py on any FLASH-worthy discovery."
        OUTPUT_FILE="$ICLOUD/evolution-sweep-latest.md"
        TIMEOUT=840  # 7 scouts + Opus synthesis; empirically 600s not enough
        CLAUDE_EXTRA_ARGS="--agent evolution-engine --model opus"
        ;;
    status)
        PROMPT="/sweep status"
        OUTPUT_FILE=""
        TIMEOUT=120
        ;;
    health)
        # Infrastructure health check only — no AI call, fast (<5s).
        # Useful for cron between sweeps or manual invocation.
        refresh_system_health
        log "health-only run complete"
        echo "OK: system health refreshed"
        exit 0
        ;;
    resolution)
        # 2026-04-19 — Commander's directive. Wire predictive_engine/resolution_engine.py
        # into daily battle rhythm. Closes out ACTIVE predictions where resolve_by <= today,
        # writes hit/miss to accuracy_log, updates status to RESOLVED_WIN/RESOLVED_LOSS/EXPIRED.
        # This is the engine that makes the new scoreboard honest.
        # Pure Python — no Claude call, no timeout wrapper needed.
        RESOLVE_SCRIPT="$SCRIPT_DIR/predictive_engine/resolution_engine.py"
        if [ ! -f "$RESOLVE_SCRIPT" ]; then
            log "RESOLUTION missing at $RESOLVE_SCRIPT — skipping"
            echo "SKIP: resolution_engine.py not found"
            exit 0
        fi
        log "RESOLUTION: starting"
        cd "$SCRIPT_DIR" && python3 -m predictive_engine.resolution_engine 2>&1 | tee -a "$LOG_DIR/resolution.log"
        RC=${PIPESTATUS[0]}
        if [ "$RC" -eq 0 ]; then
            log "RESOLUTION: OK"
            echo "OK: resolution engine complete"
            # Chain accuracy aggregator — recomputes HC/RN/Abstain tier
            # segmentation + SPY benchmark + trust-window state, then
            # writes enriched accuracy block back to prediction_data.json.
            # The dashboard accuracy panel reads this on next refresh.
            log "AGGREGATOR: starting"
            cd "$SCRIPT_DIR" && python3 -m predictive_engine.accuracy_aggregator 2>&1 | tee -a "$LOG_DIR/accuracy_aggregator.log"
            ARC=${PIPESTATUS[0]}
            if [ "$ARC" -eq 0 ]; then
                log "AGGREGATOR: OK"
                echo "OK: accuracy aggregator complete"
            else
                log "AGGREGATOR: FAIL (rc=$ARC)"
                echo "WARN: accuracy aggregator rc=$ARC — resolution succeeded but dashboard not updated"
            fi
        else
            log "RESOLUTION: FAIL (rc=$RC)"
            echo "FAIL: resolution engine rc=$RC"
        fi
        exit $RC
        ;;
    test)
        # Quick smoke test — does claude -p work at all?
        log "Running smoke test..."
        RESULT=$("$CLAUDE_BIN" -p "Say exactly: BATTLE_RHYTHM_TEST_OK" --model sonnet 2>&1 | head -5)
        if echo "$RESULT" | grep -q "BATTLE_RHYTHM_TEST_OK"; then
            log "Smoke test PASSED"
            echo "PASS: Claude headless mode working"
        else
            log "Smoke test FAILED: $RESULT"
            echo "FAIL: $RESULT"
        fi
        exit 0
        ;;
    # ── Standing Patrol Agents (OverwatchTDO's staff) ──────────────
    horizon)
        PROMPT="You are the life-horizon-scanner agent. Run your full scan protocol: check Google Calendar for the next 30/60/90 days, check kids' developmental milestones, birthdays, school deadlines, RPED countdown, insurance/benefit deadlines. Write output to ~/Documents/S6_COMMS_TECH/dashboard/life_horizons.json. Alert via python3 ~/Documents/S6_COMMS_TECH/scripts/s6_alert.py if any event inside 7 days has no calendar event."
        OUTPUT_FILE=""
        TIMEOUT=540  # Evolution 2026-04-22: empirically 434s, exceeding 420s limit (3x TIMEOUT); 540s provides 106s headroom
        CLAUDE_EXTRA_ARGS="--agent life-horizon-scanner"
        ;;
    relationship)
        PROMPT="You are the relationship-intel agent. Run your full scan: check Google Calendar for date nights and 1-on-1 time with each child, scan system files for family member mentions, check coaching homework status. Write output to ~/Documents/S6_COMMS_TECH/dashboard/relationship_intel.json. Alert via python3 ~/Documents/S6_COMMS_TECH/scripts/s6_alert.py if any bond is in RED."
        OUTPUT_FILE=""
        TIMEOUT=540  # Evolution 2026-04-22: empirically 433.6s, exceeding 420s limit (3x TIMEOUT); 540s matches horizon headroom
        CLAUDE_EXTRA_ARGS="--agent relationship-intel"
        ;;
    opportunity)
        PROMPT="You are the opportunity-hunter agent. Run your full scan: check VA benefits, career opportunities, financial optimizations, military discounts, scholarship opportunities. Write output to ~/Documents/S6_COMMS_TECH/dashboard/opportunities.json."
        OUTPUT_FILE=""
        TIMEOUT=600  # Evolution Engine 2026-03-26: empirically hit 488s, exceeded 480s limit; 600s provides 112s headroom
        CLAUDE_EXTRA_ARGS="--agent opportunity-hunter"
        ;;
    accountability)
        PROMPT="You are the accountability-tracker agent. Run your full audit: read superagent_state.json for pending recommendations, check COP changes, git commits, health data, calendar events for evidence of action. Write output to ~/Documents/S6_COMMS_TECH/dashboard/accountability_report.json. Update superagent_state.json with acted/ignored status. Alert via python3 ~/Documents/S6_COMMS_TECH/scripts/s6_alert.py if any critical recommendation ignored 5+ days."
        OUTPUT_FILE=""
        TIMEOUT=480  # Evolution Engine 2026-03-26: empirically hit 372s, exceeded 360s limit (2nd timeout for this task); 480s provides 108s headroom
        CLAUDE_EXTRA_ARGS="--agent accountability-tracker"
        ;;
    prophet)
        # NEW ARCHITECTURE 2026-04-30: same single-input-file pattern as Overwatch.
        # Per Tory directive 'Prophet and Overwatch see all' — both agents read the
        # same overwatch_input.json snapshot. Prophet differs only in PROMPT (extracts
        # trends/thresholds) and OUTPUT (pattern_prophet_output.json).
        python3 "$SCRIPT_DIR/state_synthesizer.py" >> "$LOG_DIR/state_synth.log" 2>&1 || \
            log "WARN: state_synthesizer failed; Prophet will use prior snapshot"

        PROMPT="You are Pattern Prophet. Read EXACTLY ONE FILE: ~/Documents/S6_COMMS_TECH/dashboard/overwatch_input.json

That JSON contains the full system snapshot. Everything you need is in there. Do NOT
read any other files.

Your job: extrapolate trends. Identify threshold crossings in the next 30/60/90 days.
Surface inflection points. Be specific — name dates, ranges, confidence levels.

Output to: ~/Documents/S6_COMMS_TECH/dashboard/pattern_prophet_output.json

Schema:
{
  \"generated_at\": ISO,
  \"predictions\": [{\"by_date\":\"YYYY-MM-DD\",\"label\":\"...\",\"confidence\":\"high|med|low\",\"detail\":\"...\"}],
  \"inflection_points\": [{\"metric\":\"...\",\"current\":N,\"projected\":N,\"crosses_at\":\"YYYY-MM-DD\"}],
  \"key_dates\": [{\"date\":\"YYYY-MM-DD\",\"event\":\"...\"}],
  \"narrative\": \"2-3 paragraph synthesis\"
}

Cover at minimum: weight trajectory (Iron Discipline cut), FCF/E-fund timeline,
training progression (per week numbering), scan compliance, sleep/HRV trend,
financial milestones (RPED gap, debt payoff), career/family thresholds.

Anchor every prediction to actual snapshot data. Do not hallucinate."
        OUTPUT_FILE=""
        TIMEOUT=360  # was 600; new architecture targets <240s
        CLAUDE_EXTRA_ARGS="--agent pattern-prophet"
        ;;
    pulse)
        PROMPT="You are the pulse-monitor agent. Run your full heartbeat check: verify orchestrator is running (task_health.json), check Overwatch last run (superagent_state.json), verify critical JSON freshness, check dashboard server on port 8077, check disk space, verify standing patrol outputs. Write to ~/Documents/S6_COMMS_TECH/dashboard/pulse_status.json. Alert via python3 ~/Documents/S6_COMMS_TECH/scripts/s6_alert.py on FLASH conditions."
        OUTPUT_FILE=""
        TIMEOUT=300  # Increased from 180 — pulse_2200 hitting limits, needs headroom for AI inference variance
        CLAUDE_EXTRA_ARGS="--agent pulse-monitor"
        ;;
    evolve-daily)
        # 2026-04-26 QRF RCA: orchestrator.log has grown to 11K+ lines (546KB). Prior prompt said
        # "Read orchestrator.log" with no scope limit — agent loaded the full file, pushing context
        # window from ~674s (4/24) to 924s TIMEOUT (4/25, +37%). Log rotates at 1MB so the
        # unbounded read will continue growing until rotation. Fix: explicitly scope to last 200
        # lines (covers ~3 most recent cycles, sufficient for pattern detection). The full log
        # is preserved for manual inspection — this is a read-scope fix, not a truncation.
        PROMPT="You are the evolution-engine agent running your DAILY SYSTEM LEARNING track. Read qrf_repair_log.json, task_health.json, the LAST 200 LINES of orchestrator.log (do not read the full file — it exceeds context budget), pulse_status.json, anticipation engine output, and alert_history.json. Detect patterns, write new anticipation rules if warranted, update evolution_data.json and evolution_journal.md."
        OUTPUT_FILE=""
        TIMEOUT=900  # Evolution 2026-04-22: empirically 724s = 96.6% of 750s limit — critical risk; 900s provides 176s headroom. 2026-04-26: scope fix reduces context load; timeout retained as safety margin.
        CLAUDE_EXTRA_ARGS="--agent evolution-engine"
        ;;
    evolve-weekly)
        PROMPT="You are the evolution-engine agent running your WEEKLY LIFE LEARNING track (Opus). Read superagent_journal.md, superagent_state.json, accountability_report.json, relationship_intel.json, health data trends, pattern_prophet_output.json. Detect LIFE patterns across weeks. Synthesize Deep Researcher archives if 3+ new files exist. Update evolution_data.json and evolution_journal.md. Teach Overwatch new correlations."
        OUTPUT_FILE=""
        TIMEOUT=900
        CLAUDE_EXTRA_ARGS="--agent evolution-engine --model opus"
        ;;
    network)
        PROMPT="You are the network-cartographer agent. Run your weekly career network scan: map VP-level sponsors at Lilly, check ERG opportunities, identify conferences, review LinkedIn strategy, assess relationship health with key stakeholders. Write to ~/Documents/S6_COMMS_TECH/dashboard/network_map.json."
        OUTPUT_FILE=""
        TIMEOUT=480
        CLAUDE_EXTRA_ARGS="--agent network-cartographer"
        ;;
    shield)
        PROMPT="You are the shield-agent. Run your weekly protection audit: check insurance adequacy, estate document currency, beneficiary verification, identity protection status, benefits verification (VA, Chapter 35, CHAMPVA, property tax). Write to ~/Documents/S6_COMMS_TECH/dashboard/shield_status.json. Alert via python3 ~/Documents/S6_COMMS_TECH/scripts/s6_alert.py on any PRIORITY findings."
        OUTPUT_FILE=""
        TIMEOUT=480
        CLAUDE_EXTRA_ARGS="--agent shield-agent"
        ;;
    legacy)
        PROMPT="You are the legacy-builder agent. Run your weekly capture: read narrative_arc.json, relationship_intel.json, superagent_journal.md, and overwatch-latest.md. Update kids' letters with new material. Update milestone timeline. If first Friday of month, update book material chapters. Write artifacts to ~/Library/Mobile Documents/com~apple~CloudDocs/Family/Legacy/."
        OUTPUT_FILE=""
        TIMEOUT=600
        CLAUDE_EXTRA_ARGS="--agent legacy-builder"
        ;;
    ecosystem-scan)
        PROMPT="You are the ecosystem-scanner agent. Run your full scan protocol: search for Anthropic platform updates from the last 7 days (Claude Code releases, API changes, MCP improvements, iOS/Desktop updates, model changes, deprecations). Read the current system architecture from MEMORY.md. Compare what's new against what the Life OS currently uses. Write a SITREP to ~/Documents/S6_COMMS_TECH/dashboard/ecosystem_scan.json with fields: scan_date, new_capabilities (array), retired_or_deprecated (array), recommended_upgrades (array with priority/effort/impact), risk_notes, next_scan. Also write human-readable output to ~/Library/Mobile Documents/com~apple~CloudDocs/ecosystem-scan-latest.md. If any BREAKING change detected (retired models, removed APIs, security advisories), alert via python3 ~/Documents/S6_COMMS_TECH/scripts/s6_alert.py."
        OUTPUT_FILE=""
        TIMEOUT=540
        CLAUDE_EXTRA_ARGS="--agent ecosystem-scanner"
        ;;
    scout-dispatch)
        PROMPT="UNUSED"  # scout_dispatcher.py handles its own prompts
        OUTPUT_FILE=""
        TIMEOUT=900  # 2 scouts × 300s each + overhead
        ;;
    help|*)
        echo "Usage: $0 {morning|eod|sync|data|overwatch|evolution|status|test|health}"
        echo "       $0 {horizon|relationship|opportunity|accountability|prophet|pulse}"
        echo "       $0 {evolve-daily|evolve-weekly|network|shield|legacy|ecosystem-scan|scout-dispatch}"
        echo ""
        echo "Runs battle rhythm skills and standing patrol agents via headless Claude Code."
        echo "Output written to iCloud or dashboard JSON for cross-platform sync."
        exit 0
        ;;
esac

log "START $MODE"

# Build command arguments
# 2026-04-24 RCA/FIX: --bare removed. Per `claude -p --help`:
#   "--bare ... Anthropic auth is strictly ANTHROPIC_API_KEY or apiKeyHelper
#    via --settings (OAuth and keychain are never read)."
# When the 2026-04-23 cost-leak defense added `unset ANTHROPIC_API_KEY` above,
# --bare lost its only auth source and every headless task returned
# "Not logged in · Please run /login" for ~24h. Rolling back the claude CLI
# version was chasing a ghost — 2.1.119 was innocent. Replacement flags
# achieve the same minimal-output goal while staying OAuth-compatible:
#   --output-format text  → clean text (no markdown wrapper, matches guard)
#   --no-session-persistence → skip disk writes for session state
CMD_ARGS=(-p "$PROMPT" --output-format text --no-session-persistence --dangerously-skip-permissions --model sonnet --max-budget-usd 15.00)

# Add agent flag if set (used by overwatch mode)
if [ -n "${CLAUDE_EXTRA_ARGS:-}" ]; then
    # shellcheck disable=SC2206
    CMD_ARGS+=($CLAUDE_EXTRA_ARGS)
fi

# ─────────────────────────────────────────────────────────────────
# SO #14 V3 DETECTOR — auth/flag conflict pre-flight
# Catches the class of failure that took headless tasks dark for ~24h
# starting 2026-04-23 14:06: `--bare` with `unset ANTHROPIC_API_KEY` has
# zero auth sources (per `claude -p --help`: "--bare ... Anthropic auth
# is strictly ANTHROPIC_API_KEY ... OAuth and keychain are never read").
# If anyone re-introduces --bare to CMD_ARGS without restoring the API key,
# fail loud at pre-flight instead of silently breaking 30+ tasks/day.
# ─────────────────────────────────────────────────────────────────
if [[ " ${CMD_ARGS[*]} " == *" --bare "* ]] && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    log "PREFLIGHT FAIL ($MODE): --bare in CMD_ARGS with no ANTHROPIC_API_KEY (SO #14 detector — see RCA 2026-04-24)"
    echo "PREFLIGHT FAIL: --bare requires ANTHROPIC_API_KEY (OAuth never read by --bare). See SO #14 detector."
    exit 2
fi

# Direct python scripts bypass claude -p
if [[ "$MODE" == "scout-dispatch" ]]; then
    run_with_timeout "$TIMEOUT" python3 "$SCRIPT_DIR/scout_dispatcher.py"
    EXIT_CODE=$?
    RESULT=$(cat "$TMPOUT" 2>/dev/null || echo "")
else
    # Run Claude in headless mode with macOS-compatible timeout
    run_with_timeout "$TIMEOUT" "$CLAUDE_BIN" "${CMD_ARGS[@]}"
    EXIT_CODE=$?
    RESULT=$(cat "$TMPOUT" 2>/dev/null || echo "")
fi

if [ $EXIT_CODE -eq 124 ]; then
    log "TIMEOUT $MODE after ${TIMEOUT}s"
    echo "TIMEOUT"
    exit 1
elif [ $EXIT_CODE -ne 0 ]; then
    # ── SO #14 V3 DETECTOR — rate limit specific detection ──────────
    # 2026-04-29 QRF_012: "You've hit your limit" exits with code 1 and
    # looks identical to any other failure in the orchestrator log. Three
    # consecutive evenings (4/27, 4/28) of battle_eod/pulse_2200/evolve_daily
    # all failed with this message, silently appearing as generic "exit 1".
    # Root cause: Max subscription usage cap exhausted by evening; resets
    # ~23:10-23:50 ET (rolling 5-hour window). Fix: detect the string and
    # emit a distinct log tag (RATE_LIMIT) so Overwatch and QRF can pattern-
    # match it as a capacity issue, not a script bug.
    if echo "$RESULT" | grep -qi "you've hit your limit\|hit your limit"; then
        RESET_TIME=$(echo "$RESULT" | grep -oi "resets [0-9:apm]* ([^)]*)" | head -1)
        log "RATE_LIMIT $MODE: Max subscription cap exhausted. ${RESET_TIME}. Deferred — orchestrator retries when cap recovers."
        echo "RATE_LIMIT: Max subscription cap exhausted. ${RESET_TIME}"
        # 2026-04-29: exit 75 (EX_TEMPFAIL) so orchestrator knows this is a
        # transient capacity issue, not a hard failure. Orchestrator should
        # mark task DEFERRED (not RED) and retry on next scheduled cycle.
        # Previously exit 1 made all rate-limit hits indistinguishable from
        # real failures, polluting CCIR #9 with false RED status.
        exit 75
    fi
    log "FAIL $MODE (exit $EXIT_CODE): $(echo "$RESULT" | tail -5)"
    echo "FAIL: exit $EXIT_CODE"
    exit 1
fi

# Validate output length and content
RESULT_LEN=${#RESULT}

# Minimum output check — real skill output should be >50 chars
if [ "$RESULT_LEN" -lt 50 ]; then
    log "FAIL $MODE (trivial output, ${RESULT_LEN} chars): $(echo "$RESULT" | head -3)"
    echo "FAIL: Output too short (${RESULT_LEN} chars) — likely error, not real output"
    exit 1
fi

# Check for API/system errors — only on short outputs (<500 chars) to avoid
# false positives from legitimate agent content that mentions error-like phrases.
# Real API errors are short; real agent briefs are long.
# FIX: 2026-03-26 — overwatch_evening falsely rejected because its analysis
# text contained error-like phrases (matched by case-insensitive grep).
if [ "$RESULT_LEN" -lt 500 ] && echo "$RESULT" | grep -qi "exceeded.*budget\|error:.*budget\|Exceeded USD budget\|error:.*api.*key\|ECONNREFUSED\|unauthorized\|rate.limit"; then
    log "FAIL $MODE (bad output): $(echo "$RESULT" | head -3)"
    echo "FAIL: Claude produced error output"
    exit 1
fi

# Write output to file if specified
if [ -n "${OUTPUT_FILE:-}" ] && [ -n "$RESULT" ]; then
    echo "$RESULT" > "$OUTPUT_FILE"
    LINES=$(echo "$RESULT" | wc -l | tr -d ' ')
    log "OK $MODE — wrote $LINES lines to $OUTPUT_FILE"
    echo "OK: Output written to $OUTPUT_FILE"
else
    log "OK $MODE (no file output)"
    echo "OK: $MODE completed"
fi
