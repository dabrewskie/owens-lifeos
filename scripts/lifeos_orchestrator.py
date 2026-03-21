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
        "timeout": 120,
        "critical": True,
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
    "cop_dashboard": {
        "script": "dashboard_updater.py",
        "schedule": {"interval_min": 60},
        "timeout": 30,
        "critical": True,
    },
    "financial_sync": {
        "script": "lifeos_data_sync.py",
        "schedule": {"interval_min": 60},
        "timeout": 60,
        "critical": True,
    },
    "network_scan": {
        "script": "network_scanner.py",
        "schedule": {"hours": [(3, 0)]},
        "timeout": 120,
        "critical": False,
    },
    "network_watchdog": {
        "script": "network_watchdog.py",
        "schedule": {"interval_min": 30},
        "timeout": 90,
        "critical": False,
    },
    "file_cleanup": {
        "script": "file_cleanup_agent.py",
        "schedule": {"hours": [(2, 0)], "weekdays": [6]},  # Sunday 0200
        "timeout": 300,
        "critical": False,
    },
    "rocket_money": {
        "script": "rocket_money_ingest.py",
        "schedule": {"hours": [(7, 0)]},
        "timeout": 60,
        "critical": False,
    },
    "recomp_ingest": {
        "script": "recomp_ingestion.py",
        "schedule": {"hours": [(6, 32)]},
        "timeout": 60,
        "critical": False,
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
    """Atomically write task health state."""
    health["meta"]["updated"] = now_iso()
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
                last = task_health.get("last_run")
                if last:
                    try:
                        last_dt = datetime.fromisoformat(last)
                        if abs((now - last_dt).total_seconds()) < 900:
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
            log_msg(f"OK    {name} ({duration:.1f}s)")
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
        icon = {"GREEN": "G", "RED": "R", "UNKNOWN": "?"}[status]
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
