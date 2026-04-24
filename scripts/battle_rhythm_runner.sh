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
# across 30+ daily orchestrator calls. Belt-and-suspenders with ~/.zprofile
# and com.lifeos.orchestrator.plist.
unset ANTHROPIC_API_KEY

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/cleanup_logs"
ICLOUD="$HOME/Library/Mobile Documents/com~apple~CloudDocs"
CLAUDE_BIN="$HOME/.local/bin/claude"
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
        PROMPT="/sweep morning"
        OUTPUT_FILE="$ICLOUD/morning-sweep-latest.md"
        TIMEOUT=300
        ;;
    eod)
        PROMPT="/sweep eod"
        OUTPUT_FILE="$ICLOUD/eod-close-latest.md"
        TIMEOUT=300
        ;;
    sync)
        PROMPT="/sweep sync"
        OUTPUT_FILE="$ICLOUD/cop-sync-latest.md"
        TIMEOUT=180
        ;;
    data)
        PROMPT="/sweep data"
        OUTPUT_FILE="$ICLOUD/data-ingest-latest.md"
        TIMEOUT=180
        ;;
    overwatch)
        # Determine time-of-day context
        HOUR=$(date +"%H")
        if [ "$HOUR" -lt 10 ]; then
            TOD="morning"
        elif [ "$HOUR" -lt 16 ]; then
            TOD="midday"
        else
            TOD="evening"
        fi
        PROMPT="You are OverwatchTDO. This is your scheduled ${TOD} run. Read your journal (last 5 entries from ~/Documents/S6_COMMS_TECH/dashboard/superagent_journal.md) and state file (~/Documents/S6_COMMS_TECH/dashboard/superagent_state.json). Read the COP. Read the latest health data. Read pending_actions.json and task_health.json. Check battle rhythm file ages. Then think across everything and write your brief. Write output to ~/Library/Mobile Documents/com~apple~CloudDocs/overwatch-latest.md. Append your journal entry. Update your state file. If anything is critical, send iMessage via python3 ~/Documents/S6_COMMS_TECH/scripts/s6_alert.py."
        OUTPUT_FILE="$ICLOUD/overwatch-latest.md"
        TIMEOUT=300
        CLAUDE_EXTRA_ARGS="--agent overwatch-tdo"
        ;;
    status)
        PROMPT="/sweep status"
        OUTPUT_FILE=""
        TIMEOUT=120
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
    help|*)
        echo "Usage: $0 {morning|eod|sync|data|overwatch|status|test}"
        echo ""
        echo "Runs battle rhythm skills via headless Claude Code."
        echo "Output written to iCloud for cross-platform sync."
        exit 0
        ;;
esac

log "START $MODE"

# Build command arguments
CMD_ARGS=(-p "$PROMPT" --dangerously-skip-permissions --model sonnet --max-budget-usd 15.00)

# Add agent flag if set (used by overwatch mode)
if [ -n "${CLAUDE_EXTRA_ARGS:-}" ]; then
    # shellcheck disable=SC2206
    CMD_ARGS+=($CLAUDE_EXTRA_ARGS)
fi

# Run Claude in headless mode with macOS-compatible timeout
run_with_timeout "$TIMEOUT" "$CLAUDE_BIN" "${CMD_ARGS[@]}"
EXIT_CODE=$?

RESULT=$(cat "$TMPOUT" 2>/dev/null || echo "")

if [ $EXIT_CODE -eq 124 ]; then
    log "TIMEOUT $MODE after ${TIMEOUT}s"
    echo "TIMEOUT"
    exit 1
elif [ $EXIT_CODE -ne 0 ]; then
    log "FAIL $MODE (exit $EXIT_CODE): $(echo "$RESULT" | tail -5)"
    echo "FAIL: exit $EXIT_CODE"
    exit 1
fi

# Validate output — catch budget exhaustion and other Claude errors that exit 0
if echo "$RESULT" | grep -qi "exceeded.*budget\|error:.*budget\|error:.*api.*key\|ECONNREFUSED"; then
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
