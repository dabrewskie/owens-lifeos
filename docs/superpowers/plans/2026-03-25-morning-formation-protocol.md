# Morning Formation Protocol — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a daily interactive morning check-in system that closes the human/system feedback loop — enabling the Commander to confirm priorities, provide subjective inputs, and give the system ground truth for continuous learning.

**Architecture:** Formation Packet Generator (Python, 0545 via orchestrator) assembles JSON from existing data files -> iCloud sync -> claude.ai iPhone interactive session (5 steps) -> Commander saves response artifact to iCloud -> Formation Ingest (Python, every 15 min via orchestrator) parses responses and updates all downstream JSONs + formation_log.json for learning.

**Tech Stack:** Python 3.9, JSON, iCloud file sync, claude.ai Project system prompt, iOS Shortcuts

**Spec:** `docs/superpowers/specs/2026-03-25-morning-formation-protocol-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `~/Documents/S6_COMMS_TECH/scripts/formation_packet_generator.py` | Create | Read existing JSONs, assemble formation_packet.json, write to iCloud |
| `~/Documents/S6_COMMS_TECH/scripts/formation_ingest.py` | Create | Watch iCloud folder, parse responses, update downstream JSONs |
| `~/Documents/S6_COMMS_TECH/dashboard/formation_log.json` | Create | Append-only daily log of Commander inputs and priority responses |
| `~/Library/Mobile Documents/com~apple~CloudDocs/FORMATION_PACKET.json` | Create (runtime) | Daily packet for iPhone session |
| `~/Library/Mobile Documents/com~apple~CloudDocs/FORMATION_RESPONSES/` | Create (dir) | Commander saves response artifacts here |
| `~/Library/Mobile Documents/com~apple~CloudDocs/FORMATION_RESPONSES/processed/` | Create (dir) | Processed responses moved here |
| `~/Documents/S6_COMMS_TECH/scripts/lifeos_orchestrator.py` | Modify | Add `formation_packet` and `formation_ingest` tasks |
| `~/owens-lifeos/agents/overwatch-tdo.md` | Modify | Add instruction to read formation_log.json |
| `~/Documents/S6_COMMS_TECH/scripts/lifeos_mcp_server.py` | Modify | Add `get_formation_packet` tool |
| `~/Documents/S6_COMMS_TECH/scripts/briefing_packet_generator.py` | Modify | Include Formation status section |

---

### Task 1: Create iCloud Directory Structure

**Files:**
- Create: `~/Library/Mobile Documents/com~apple~CloudDocs/FORMATION_RESPONSES/`
- Create: `~/Library/Mobile Documents/com~apple~CloudDocs/FORMATION_RESPONSES/processed/`
- Create: `~/Documents/S6_COMMS_TECH/dashboard/formation_log.json`

- [ ] **Step 1: Create iCloud directories**

```bash
mkdir -p ~/Library/Mobile\ Documents/com~apple~CloudDocs/FORMATION_RESPONSES/processed
```

- [ ] **Step 2: Create empty formation_log.json**

```json
{
  "meta": {
    "purpose": "Append-only daily log of Morning Formation responses for learning",
    "created": "2026-03-25",
    "schema_version": 1
  },
  "entries": {}
}
```

Write to: `~/Documents/S6_COMMS_TECH/dashboard/formation_log.json`

- [ ] **Step 3: Verify directories exist and sync**

```bash
ls -la ~/Library/Mobile\ Documents/com~apple~CloudDocs/FORMATION_RESPONSES/
ls -la ~/Documents/S6_COMMS_TECH/dashboard/formation_log.json
```

- [ ] **Step 4: Commit**

```bash
cd ~/owens-lifeos
git add docs/superpowers/plans/2026-03-25-morning-formation-protocol.md
git commit -m "feat(formation): create directory structure and empty formation_log.json"
```

---

### Task 2: Build Formation Packet Generator

**Files:**
- Create: `~/Documents/S6_COMMS_TECH/scripts/formation_packet_generator.py`

This script reads existing JSON files (superagent_state.json, health_data.json, accountability_report.json, calendar_mirror_log.json, task_health.json) and assembles a structured formation packet. Pure JSON-to-JSON — no AI inference, <5 second runtime.

- [ ] **Step 1: Write formation_packet_generator.py**

```python
#!/usr/bin/env python3
"""
formation_packet_generator.py — Morning Formation Packet Assembler

Reads existing Life OS JSON data files and assembles a structured
formation_packet.json for the iPhone interactive session.

Pure JSON-to-JSON transform — no AI inference, <5 sec runtime.
Runs daily at 0545 via orchestrator, after Overwatch morning run (0530).

Usage:
  python3 formation_packet_generator.py            # Normal run
  python3 formation_packet_generator.py --dry-run  # Print to stdout, don't write
"""

import json
import os
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────
DASHBOARD = Path.home() / "Documents" / "S6_COMMS_TECH" / "dashboard"
ICLOUD = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
HEALTH_DIR = DASHBOARD / "health"

SUPERAGENT_STATE = DASHBOARD / "superagent_state.json"
ACCOUNTABILITY = DASHBOARD / "accountability_report.json"
TASK_HEALTH = DASHBOARD / "task_health.json"
CALENDAR_MIRROR = DASHBOARD / "calendar_mirror_log.json"
HEALTH_DATA = HEALTH_DIR / "health_data.json"
SUBSTANCE_TRACKER = DASHBOARD / "substance_tracker.json"
PENDING_ACTIONS = DASHBOARD / "pending_actions.json"

OUTPUT = ICLOUD / "FORMATION_PACKET.json"

PRIORITY_CAP = 7


def load_json(path: Path) -> dict | None:
    """Load a JSON file, return None if missing or corrupt."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        print(f"  WARN: Could not load {path.name}: {e}", file=sys.stderr)
        return None


def build_sitrep(health: dict | None, task_health: dict | None, calendar: dict | None) -> dict:
    """Build the SITREP section from existing data."""
    sitrep = {"health": {}, "calendar": [], "system": {}, "overnight": ""}

    # Health
    if health:
        recovery = health.get("recovery", {})
        sitrep["health"] = {
            "recovery_score": recovery.get("score", None),
            "recovery_zone": recovery.get("zone", "UNKNOWN"),
            "deep_sleep_hours": recovery.get("components", {}).get("sleep_quality", {}).get("deep_hours", None),
            "hrv": recovery.get("components", {}).get("hrv", {}).get("value", None),
            "flag": recovery.get("recommendation", "No data"),
        }

    # Calendar — extract today's events
    if calendar and isinstance(calendar, dict):
        events = calendar.get("events", calendar.get("today", []))
        if isinstance(events, list):
            sitrep["calendar"] = [
                {"time": e.get("time", ""), "event": e.get("title", e.get("summary", str(e)))}
                for e in events[:10]
            ]

    # System health
    if task_health and "tasks" in task_health:
        tasks = task_health["tasks"]
        green = sum(1 for t in tasks.values() if t.get("status") == "GREEN")
        red = sum(1 for t in tasks.values() if t.get("status") == "RED")
        total = len(tasks)
        alerts = [
            f"{name}: {t.get('last_error', 'failed')}"
            for name, t in tasks.items()
            if t.get("status") == "RED"
        ][:5]
        sitrep["system"] = {"green": green, "total": total, "red": red, "alerts": alerts}

    return sitrep


def build_priorities(state: dict | None, accountability: dict | None) -> tuple[list, int]:
    """Build priority list from superagent concerns + accountability recs.
    Returns (priorities, overflow_count)."""
    today = date.today().isoformat()
    items = []

    # From superagent_state active concerns
    if state:
        for concern in state.get("active_concerns", []):
            status = concern.get("status", "")
            if status in ("resolved", "dismissed"):
                continue
            items.append({
                "id": concern.get("id", "unknown"),
                "source": "overwatch_concern",
                "text": concern.get("summary", "")[:200],
                "category": concern.get("category", "general"),
                "age_days": concern.get("times_flagged", 0),
                "times_flagged": concern.get("times_flagged", 0),
                "deadline": concern.get("deadline", None),
                "alert_level": "RED" if concern.get("escalation_level", 0) >= 2 else "YELLOW",
                "required_response": "confirm | defer(date) | dismiss(reason) | done",
            })

    # From accountability pending recs
    if accountability:
        for rec in accountability.get("recommendations", []):
            rec_status = rec.get("status", "")
            if rec_status in ("ACTED", "RESOLVED"):
                continue
            # Avoid duplicating items already from superagent_state
            rec_id = rec.get("id", "unknown")
            if any(p["id"] == rec_id for p in items):
                continue
            items.append({
                "id": rec_id,
                "source": "accountability",
                "text": rec.get("summary", "")[:200],
                "category": "recommendation",
                "age_days": rec.get("days_since_given", 0),
                "times_flagged": rec.get("follow_up_count", 0),
                "deadline": rec.get("deadline", None),
                "alert_level": rec.get("alert_level", "ROUTINE"),
                "required_response": "confirm | defer(date) | dismiss(reason) | done",
            })

    # Filter out deferred items not yet due
    items = [
        i for i in items
        if not (i.get("defer_date") and i["defer_date"] >= today)
    ]

    # Triage: RED first, then deadline within 7 days, then YELLOW by times_flagged
    def sort_key(item):
        is_red = 0 if item["alert_level"] == "RED" else 1
        deadline = item.get("deadline") or "9999-12-31"
        has_soon_deadline = 0 if deadline <= (date.today() + timedelta(days=7)).isoformat() else 1
        return (is_red, has_soon_deadline, -item.get("times_flagged", 0), -item.get("age_days", 0))

    items.sort(key=sort_key)

    overflow = max(0, len(items) - PRIORITY_CAP)
    return items[:PRIORITY_CAP], overflow


def build_coaching_homework(state: dict | None) -> list:
    """Extract coaching homework from superagent state."""
    homework = []
    if not state:
        return homework
    for thread in state.get("coaching_threads", []):
        if thread.get("status") in ("completed", "dismissed"):
            continue
        assigned = thread.get("assigned", thread.get("first_raised", ""))
        days_pending = 0
        if assigned:
            try:
                assigned_date = datetime.fromisoformat(assigned).date()
                days_pending = (date.today() - assigned_date).days
            except (ValueError, TypeError):
                pass
        homework.append({
            "id": thread.get("id", "unknown"),
            "text": thread.get("summary", thread.get("topic", ""))[:200],
            "assigned": assigned,
            "days_pending": days_pending,
            "required_response": "confirm | defer(date) | done(note)",
        })
    return homework


def check_substance_prompt(tracker: dict | None) -> bool:
    """Check if substance logging is active."""
    return tracker is not None and len(tracker.get("entries", [])) > 0


def main():
    dry_run = "--dry-run" in sys.argv

    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Formation Packet Generator")

    # Load all sources
    state = load_json(SUPERAGENT_STATE)
    accountability = load_json(ACCOUNTABILITY)
    task_health = load_json(TASK_HEALTH)
    calendar = load_json(CALENDAR_MIRROR)
    health = load_json(HEALTH_DATA)
    substance = load_json(SUBSTANCE_TRACKER)

    # Build packet
    sitrep = build_sitrep(health, task_health, calendar)
    priorities, overflow = build_priorities(state, accountability)
    homework = build_coaching_homework(state)

    packet = {
        "schema_version": 1,
        "date": date.today().isoformat(),
        "generated": datetime.now().isoformat(),
        "priority_cap": PRIORITY_CAP,
        "overflow_count": overflow,
        "sitrep": sitrep,
        "priorities": priorities,
        "coaching_homework": homework,
        "substance_prompt": check_substance_prompt(substance),
        "input_schema": {
            "energy": "1-5 (1=drained, 5=peak)",
            "mood": "1-5 (1=low, 5=great)",
            "sleep_feel": "1-5 (1=terrible, 5=refreshed)",
            "substances_last_night": [
                "nicotine", "thc", "alcohol", "caffeine_late",
                "cold_plunge", "sauna", "sex", "none"
            ],
            "family_pulse": "free text",
            "anything_on_mind": "free text",
        },
    }

    output = json.dumps(packet, indent=2, default=str)

    if dry_run:
        print(output)
        print(f"\n  Priorities: {len(priorities)} (overflow: {overflow})")
        print(f"  Homework: {len(homework)}")
    else:
        OUTPUT.write_text(output, encoding="utf-8")
        print(f"  Wrote {len(output):,} chars to {OUTPUT}")
        print(f"  Priorities: {len(priorities)} (overflow: {overflow}), Homework: {len(homework)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run with --dry-run to verify output**

```bash
python3 ~/Documents/S6_COMMS_TECH/scripts/formation_packet_generator.py --dry-run
```

Expected: JSON output to stdout with priorities, sitrep, coaching_homework populated from live data.

- [ ] **Step 3: Run for real and verify iCloud output**

```bash
python3 ~/Documents/S6_COMMS_TECH/scripts/formation_packet_generator.py
cat ~/Library/Mobile\ Documents/com~apple~CloudDocs/FORMATION_PACKET.json | python3 -m json.tool | head -30
```

Expected: Valid JSON written to iCloud path.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat(formation): add formation_packet_generator.py"
```

---

### Task 3: Build Formation Ingest Script

**Files:**
- Create: `~/Documents/S6_COMMS_TECH/scripts/formation_ingest.py`

Watches iCloud `FORMATION_RESPONSES/` for new files. Parses response JSON. Updates downstream files. Moves processed files.

- [ ] **Step 1: Write formation_ingest.py**

```python
#!/usr/bin/env python3
"""
formation_ingest.py — Morning Formation Response Ingester

Watches ~/Library/Mobile Documents/com~apple~CloudDocs/FORMATION_RESPONSES/
for new formation response JSON files from the iPhone interactive session.

On finding a new file:
  1. Validates JSON structure (schema_version check)
  2. Updates superagent_state.json (priority confirm/defer/done/dismiss)
  3. Updates accountability_report.json (logs responses)
  4. Updates substance_tracker.json (logs substance data)
  5. Appends to formation_log.json (learning data)
  6. Moves processed file to processed/ subfolder

Error handling: processes what it can, skips unknown IDs with warning,
never hard-fails. Partial success still writes to formation_log.

Runs every 15 min via orchestrator.

Usage:
  python3 formation_ingest.py           # Normal run
  python3 formation_ingest.py --dry-run # Parse but don't write
"""

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────
ICLOUD = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
DASHBOARD = Path.home() / "Documents" / "S6_COMMS_TECH" / "dashboard"

RESPONSES_DIR = ICLOUD / "FORMATION_RESPONSES"
PROCESSED_DIR = RESPONSES_DIR / "processed"
FORMATION_LOG = DASHBOARD / "formation_log.json"
SUPERAGENT_STATE = DASHBOARD / "superagent_state.json"
ACCOUNTABILITY = DASHBOARD / "accountability_report.json"
SUBSTANCE_TRACKER = DASHBOARD / "substance_tracker.json"
ALERT_HISTORY = DASHBOARD / "alert_history.json"

LOG_DIR = Path.home() / "Documents" / "S6_COMMS_TECH" / "scripts" / "cleanup_logs"


def log(msg: str):
    """Log to formation_ingest.log."""
    log_file = LOG_DIR / "formation_ingest.log"
    try:
        with open(log_file, "a") as f:
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n")
    except OSError:
        pass
    print(f"  {msg}")


def load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        log(f"WARN: Could not load {path.name}: {e}")
        return None


def save_json(path: Path, data: dict):
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def find_new_responses() -> list[Path]:
    """Find unprocessed formation response files."""
    if not RESPONSES_DIR.exists():
        return []
    return sorted(
        p for p in RESPONSES_DIR.glob("formation_*.json")
        if p.is_file()
    )


def validate_response(data: dict) -> bool:
    """Basic schema validation."""
    if not isinstance(data, dict):
        return False
    if data.get("schema_version") != 1:
        log(f"WARN: Unknown schema_version: {data.get('schema_version')}")
        return False
    if "date" not in data:
        log("WARN: Missing 'date' field")
        return False
    return True


def update_superagent_state(responses: list[dict], dry_run: bool):
    """Update superagent_state.json with priority responses."""
    state = load_json(SUPERAGENT_STATE)
    if not state or dry_run:
        return

    concerns = state.get("active_concerns", [])
    concern_map = {c.get("id"): c for c in concerns}

    for resp in responses:
        rid = resp.get("id", "")
        action = resp.get("response", "")
        note = resp.get("note", "")

        # Match against concern IDs
        if rid in concern_map:
            concern = concern_map[rid]
            if action == "done":
                concern["status"] = "resolved"
                concern["resolution_note"] = f"Commander marked done in Formation: {note}"
            elif action == "dismiss":
                concern["status"] = "dismissed"
                concern["resolution_note"] = f"Commander dismissed in Formation: {note}"
            elif action == "defer":
                concern["defer_date"] = resp.get("defer_date")
                concern["note"] = f"Deferred in Formation: {note}"
            elif action == "confirm":
                concern["note"] = f"Confirmed in Formation: {note}"
            log(f"  Updated concern {rid}: {action}")
        else:
            log(f"  WARN: Unknown priority ID '{rid}' — skipping")

    save_json(SUPERAGENT_STATE, state)


def update_accountability(responses: list[dict], response_date: str, dry_run: bool):
    """Log responses to accountability_report.json."""
    acc = load_json(ACCOUNTABILITY)
    if not acc or dry_run:
        return

    for rec in acc.get("recommendations", []):
        rec_id = rec.get("id")
        match = next((r for r in responses if r.get("id") == rec_id), None)
        if match:
            action = match.get("response", "")
            if action == "done":
                rec["status"] = "ACTED"
            elif action == "confirm":
                rec["formation_confirmed"] = response_date
            elif action == "defer":
                rec["formation_deferred_to"] = match.get("defer_date")
            elif action == "dismiss":
                rec["status"] = "DISMISSED"
            rec["formation_note"] = match.get("note", "")
            rec["formation_date"] = response_date

    save_json(ACCOUNTABILITY, acc)


def update_substance_tracker(substances: list[str], response_date: str, dry_run: bool):
    """Add substance entries from Formation input."""
    if not substances or "none" in substances or dry_run:
        return

    tracker = load_json(SUBSTANCE_TRACKER)
    if not tracker:
        return

    entries = tracker.get("entries", [])
    # Add a formation-sourced entry
    entries.append({
        "date": response_date,
        "time": "evening",
        "source": "formation",
        "substances": substances,
    })
    tracker["entries"] = entries
    save_json(SUBSTANCE_TRACKER, tracker)
    log(f"  Logged substances: {substances}")


def append_formation_log(response_data: dict, dry_run: bool):
    """Append to formation_log.json."""
    if dry_run:
        return

    formation_log = load_json(FORMATION_LOG) or {
        "meta": {"purpose": "Formation responses", "schema_version": 1},
        "entries": {},
    }

    response_date = response_data.get("date", "unknown")
    commander = response_data.get("commander_input", {})
    priorities = response_data.get("priority_responses", [])

    entry = {
        "completed": response_data.get("completed"),
        "energy": commander.get("energy"),
        "mood": commander.get("mood"),
        "sleep_feel": commander.get("sleep_feel"),
        "substances": commander.get("substances", []),
        "family_pulse": commander.get("family_pulse"),
        "free_text": commander.get("free_text"),
        "priorities": {
            p["id"]: {
                "response": p.get("response"),
                "note": p.get("note"),
                "defer_date": p.get("defer_date"),
            }
            for p in priorities
        },
        "day_intent": response_data.get("day_intent", []),
    }

    # Overwrite if duplicate date (Commander re-did Formation)
    formation_log["entries"][response_date] = entry
    save_json(FORMATION_LOG, formation_log)
    log(f"  Appended formation_log entry for {response_date}")


def process_response(path: Path, dry_run: bool) -> bool:
    """Process a single formation response file. Returns True on success."""
    log(f"Processing: {path.name}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log(f"ERROR: Invalid JSON in {path.name}: {e}")
        return False

    if not validate_response(data):
        log(f"ERROR: Validation failed for {path.name}")
        return False

    response_date = data.get("date", "unknown")
    priority_responses = data.get("priority_responses", [])
    commander = data.get("commander_input", {})
    substances = commander.get("substances", [])

    # Update downstream files
    update_superagent_state(priority_responses, dry_run)
    update_accountability(priority_responses, response_date, dry_run)
    update_substance_tracker(substances, response_date, dry_run)
    append_formation_log(data, dry_run)

    # Move to processed
    if not dry_run:
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        dest = PROCESSED_DIR / path.name
        shutil.move(str(path), str(dest))
        log(f"  Moved to processed/")

    log(f"OK: {path.name} — {len(priority_responses)} priorities, substances={substances}")
    return True


def main():
    dry_run = "--dry-run" in sys.argv
    responses = find_new_responses()

    if not responses:
        # Silent exit — this runs every 15 min, no output when nothing to do
        return

    log(f"Found {len(responses)} new response(s)")

    for path in responses:
        process_response(path, dry_run)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create a test response file and run --dry-run**

Write a sample `formation_2026-03-25.json` to FORMATION_RESPONSES/:

```json
{
  "schema_version": 1,
  "date": "2026-03-25",
  "completed": "2026-03-25T06:45:00",
  "commander_input": {
    "energy": 3,
    "mood": 4,
    "sleep_feel": 2,
    "substances": ["nicotine"],
    "family_pulse": "Good evening with Lindsey",
    "free_text": null
  },
  "priority_responses": [
    {"id": "concern_002", "response": "confirm", "note": "doing tonight", "defer_date": null},
    {"id": "concern_005", "response": "confirm", "note": null, "defer_date": null}
  ],
  "day_intent": ["Director roundtable prep", "Estate packet", "Zone 2 only"]
}
```

```bash
python3 ~/Documents/S6_COMMS_TECH/scripts/formation_ingest.py --dry-run
```

Expected: Parses file, logs actions, does not modify any files.

- [ ] **Step 3: Run for real with test file**

```bash
python3 ~/Documents/S6_COMMS_TECH/scripts/formation_ingest.py
```

Verify:
- `formation_log.json` has entry for 2026-03-25
- Test file moved to `FORMATION_RESPONSES/processed/`
- `superagent_state.json` updated (concern_002 and concern_005 notes updated)

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat(formation): add formation_ingest.py with error handling"
```

---

### Task 4: Wire Into Orchestrator

**Files:**
- Modify: `~/Documents/S6_COMMS_TECH/scripts/lifeos_orchestrator.py`

Add two new tasks: `formation_packet` (daily 0545) and `formation_ingest` (every 15 min).

- [ ] **Step 1: Add formation_packet task**

Add after the `overwatch_morning` task block in the TASKS dict:

```python
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
    # Watches iCloud for Formation responses, updates downstream JSONs.
    # Every 15 min — matches orchestrator cycle. Silent when no new files.
    "formation_ingest": {
        "script": "formation_ingest.py",
        "schedule": {"interval_min": 15},
        "timeout": 30,
        "critical": True,
    },
```

- [ ] **Step 2: Verify orchestrator accepts new tasks**

```bash
python3 ~/Documents/S6_COMMS_TECH/scripts/lifeos_orchestrator.py --status 2>&1 | grep formation
```

Expected: Both `formation_packet` and `formation_ingest` appear in status output.

- [ ] **Step 3: Force-run both tasks to verify**

```bash
python3 ~/Documents/S6_COMMS_TECH/scripts/lifeos_orchestrator.py --run formation_packet
python3 ~/Documents/S6_COMMS_TECH/scripts/lifeos_orchestrator.py --run formation_ingest
```

Expected: Both complete successfully.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat(formation): wire packet generator and ingest into orchestrator"
```

---

### Task 5: Add MCP Tool for Formation Packet

**Files:**
- Modify: `~/Documents/S6_COMMS_TECH/scripts/lifeos_mcp_server.py`

Add a `get_formation_packet` tool so Claude Desktop can also access the packet.

- [ ] **Step 1: Add the tool**

Add after the existing `get_action_items` tool:

```python
@mcp.tool()
def get_formation_packet() -> str:
    """Get the current Morning Formation packet for the interactive session.
    Contains SITREP, priorities requiring response, coaching homework, and input schema."""
    packet_path = ICLOUD / "FORMATION_PACKET.json"
    return _read_file(packet_path)
```

- [ ] **Step 2: Commit**

```bash
git add -A && git commit -m "feat(formation): add get_formation_packet MCP tool"
```

---

### Task 6: Update Overwatch Agent

**Files:**
- Modify: `~/owens-lifeos/agents/overwatch-tdo.md`

Add instruction to read formation_log.json for ground truth on Commander responses.

- [ ] **Step 1: Add Formation awareness to Overwatch**

In the `## My Data Sources` or main instructions section, add:

```markdown
## Formation Intelligence

Read `~/Documents/S6_COMMS_TECH/dashboard/formation_log.json` at every run. This is ground truth — the Commander's explicit morning responses to every priority you've raised. When you see:
- **confirm** — he acknowledged it, track follow-through from this date
- **defer(date)** — he chose to delay, resurface on that date
- **done(note)** — he completed it, read his note for context you can't observe
- **dismiss(reason)** — he removed it, read his reason before re-raising

Also read `commander_input` fields: energy, mood, sleep_feel, family_pulse. These are subjective signals only the Commander can provide. Use them to calibrate your assessment — if he says sleep_feel=2 but objective deep sleep was 1.2h, the numbers and the man agree. If he says energy=4 but recovery_score is 45%, something is off.

If no Formation entry exists for today by your midday run (1200), send an iMessage nudge via s6_alert.py.
```

- [ ] **Step 2: Commit**

```bash
cd ~/owens-lifeos && git add agents/overwatch-tdo.md
git commit -m "feat(formation): add Formation intelligence reading to Overwatch"
```

---

### Task 7: Update Briefing Packet Generator

**Files:**
- Modify: `~/Documents/S6_COMMS_TECH/scripts/briefing_packet_generator.py`

Add a Formation Status section so cross-platform Claudes know whether today's Formation has been completed.

- [ ] **Step 1: Add Formation status to briefing packet**

In the section builder, add a new section that reads `formation_log.json` and reports today's status:

```python
def build_formation_section() -> str:
    """Build Formation status section for briefing packet."""
    from datetime import date
    formation_log_path = Path.home() / "Documents" / "S6_COMMS_TECH" / "dashboard" / "formation_log.json"
    today = date.today().isoformat()

    try:
        data = json.loads(formation_log_path.read_text(encoding="utf-8"))
        entries = data.get("entries", {})
        if today in entries:
            entry = entries[today]
            energy = entry.get("energy", "?")
            mood = entry.get("mood", "?")
            n_priorities = len(entry.get("priorities", {}))
            return f"""## Morning Formation
**Status:** COMPLETED ({today})
**Commander State:** Energy {energy}/5, Mood {mood}/5
**Priorities Addressed:** {n_priorities}
**Day Intent:** {', '.join(entry.get('day_intent', ['not set']))}
"""
        else:
            return f"""## Morning Formation
**Status:** NOT YET COMPLETED ({today})
_Commander has not completed Morning Formation today. Priorities and subjective state unknown._
"""
    except Exception:
        return "## Morning Formation\n**Status:** Data unavailable\n"
```

Add a call to `build_formation_section()` in the main packet assembly.

- [ ] **Step 2: Commit**

```bash
git add -A && git commit -m "feat(formation): add Formation status to briefing packet"
```

---

### Task 8: Write claude.ai Project System Prompt

**Files:**
- Create: `~/Library/Mobile Documents/com~apple~CloudDocs/FORMATION_PROMPT.md`

This is the system prompt addition for the claude.ai Project that powers the iPhone interactive session.

- [ ] **Step 1: Write the Formation prompt**

```markdown
# Morning Formation Protocol

You are Claude, running the Morning Formation for Tory Owens (Commander). This is a structured daily check-in that takes 5-7 minutes.

## When Triggered

When the Commander says "formation", "morning", "/formation", or "morning check-in", run this protocol.

## Step 0 — Load Packet

Read FORMATION_PACKET.json from this Project's files (or ask the Commander to share it). Check the `generated` timestamp. If the packet is more than 20 hours old, warn: "This packet is from yesterday — priorities may have changed. Proceed anyway?"

## Step 1 — SITREP (present, no input needed)

Present a clean summary from the packet:
- Recovery score + zone + flag (e.g., "Recovery: 62% YELLOW — rest day prescribed")
- Today's calendar events
- System health (GREEN/RED count, any alerts)
- Overnight activity summary

Keep it concise. 4-5 lines max.

## Step 2 — Commander's Input

Ask in one message:
> How are you feeling this morning?
> - Energy (1-5)?
> - Mood (1-5)?
> - How'd you sleep? (1-5)
> - Anything last night? (substances: nicotine, THC, alcohol, caffeine late, cold plunge, sauna, sex, or none)
> - Anything on your mind the system can't see? Family pulse?

Let him respond naturally in one message. Parse his response into structured fields. Don't be rigid — "energy 3, mood 4, slept like shit, had a gummy" is valid input.

## Step 3 — Priority Board

Present each priority from the packet ONE AT A TIME. For each:
- Show the text, age, times flagged, deadline if any
- Use emoji for alert level: RED = stop sign, YELLOW = warning, ROUTINE = clipboard
- Ask: "Confirm / Defer to ___ / Done / Dismiss?"

The Commander MUST respond to every item. Do not skip any. Do not batch them. If he tries to skip, gently insist: "Need a response on this one — confirm, defer, done, or dismiss?"

Then present coaching homework items the same way.

## Step 4 — Day's Intent

Ask: "What are your top 3 for today?"

## Step 5 — Formation Complete

Summarize everything:
- What was confirmed/deferred/done/dismissed
- Substances logged
- Day's intent
- Any coaching note (rest day holds, meeting prep, etc.)

Then generate the Formation Response as a JSON artifact with this exact structure:

```json
{
  "schema_version": 1,
  "date": "YYYY-MM-DD",
  "completed": "ISO timestamp",
  "commander_input": {
    "energy": N,
    "mood": N,
    "sleep_feel": N,
    "substances": ["..."],
    "family_pulse": "...",
    "free_text": "..."
  },
  "priority_responses": [
    {"id": "pri_XXX", "response": "confirm|defer|done|dismiss", "note": "...", "defer_date": null}
  ],
  "day_intent": ["...", "...", "..."]
}
```

Tell the Commander: "Save this artifact to Files → iCloud Drive → FORMATION_RESPONSES folder. One tap if you have the Shortcut set up."

## Rules

- Keep total time under 7 minutes. Be concise.
- Parse natural language — don't force rigid formatting on the Commander.
- Never skip a priority item. Every item requires a response.
- Use the Commander's voice — he's military, direct, doesn't need coddling.
- If no packet is available, tell him and offer to do a freeform check-in instead.
```

- [ ] **Step 2: Commit**

```bash
cd ~/owens-lifeos
git add -A && git commit -m "feat(formation): write claude.ai Formation protocol prompt"
```

---

### Task 9: Integration Test — Full Loop

- [ ] **Step 1: Run formation_packet_generator.py and verify packet**

```bash
python3 ~/Documents/S6_COMMS_TECH/scripts/formation_packet_generator.py
cat ~/Library/Mobile\ Documents/com~apple~CloudDocs/FORMATION_PACKET.json | python3 -m json.tool | head -40
```

Verify: valid JSON, priorities populated, sitrep has health data.

- [ ] **Step 2: Create a realistic test response and place in FORMATION_RESPONSES/**

Write a response file as if the Commander completed Formation.

- [ ] **Step 3: Run formation_ingest.py and verify downstream updates**

```bash
python3 ~/Documents/S6_COMMS_TECH/scripts/formation_ingest.py
```

Verify:
- `formation_log.json` has today's entry with all fields
- `superagent_state.json` updated for matched concern IDs
- Test file moved to `processed/`
- No errors in `cleanup_logs/formation_ingest.log`

- [ ] **Step 4: Run orchestrator --status to verify both tasks are GREEN**

```bash
python3 ~/Documents/S6_COMMS_TECH/scripts/lifeos_orchestrator.py --status 2>&1 | grep -E "formation|GREEN|RED"
```

- [ ] **Step 5: Verify FORMATION_PACKET.json is readable on iPhone**

Open Files app on iPhone → iCloud Drive → verify FORMATION_PACKET.json is visible.

- [ ] **Step 6: Final commit and push**

```bash
cd ~/owens-lifeos && git add -A
git commit -m "feat(formation): Morning Formation Protocol complete — packet generator, ingest, orchestrator, MCP, Overwatch, briefing packet, claude.ai prompt"
bash ~/owens-lifeos/sync.sh push
```

---

### Task 10: Build iOS Shortcut (manual — Commander action)

This task is a guide for the Commander to build on his iPhone. Cannot be automated.

- [ ] **Step 1: Open Shortcuts app on iPhone**

- [ ] **Step 2: Create new Shortcut named "Save Formation"**

Actions:
1. **Receive** input from Share Sheet (accept Text, Files)
2. **Save File** to: `iCloud Drive/FORMATION_RESPONSES/` with filename: `formation_[Current Date].json`

- [ ] **Step 3: Test the Shortcut**

In claude.ai, generate a test artifact. Tap Share → "Save Formation". Verify file appears in iCloud Drive/FORMATION_RESPONSES/.

- [ ] **Step 4: Verify ingest picks it up**

Wait for next orchestrator cycle (or force-run):
```bash
python3 ~/Documents/S6_COMMS_TECH/scripts/formation_ingest.py
```

Verify formation_log.json updated.
