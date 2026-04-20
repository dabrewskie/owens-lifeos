# BUILD SPEC: Cross-Platform Completion Queue (COP Sync Fix)

**Priority:** CRITICAL — URGENT
**Owner:** Claude Code
**Requester:** Commander (Tory Owens) + COS (Web)
**Date:** 2026-03-30

---

## PROBLEM STATEMENT

Web conversations (claude.ai) complete tasks with the Commander, but COP.md — the single source of truth — is only writable by Claude Code. This creates a **permanent data divergence**: completed items stay "overdue" in COP indefinitely. Every morning sweep, the web COS reads stale COP and reports false overdue flags to the Commander, eroding trust.

**Specific failures today (3/30/26):**
- Dragonslayer admin switch: COMPLETED ~3/27 in a web chat → COP still says "26 days overdue"
- ADB Fire TV disable: COMPLETED ~3/22 in a web chat → COP still says "6 days overdue"
- Gulf Shores lodging: CONFIRMED with Res #398702 shared in 3/29 web chat → COP says "VERIFY TODAY"

**Root cause:** No mechanism exists for web conversations to signal task completions back to COP.md. The two Claude instances (web + Code) operate on the same life but cannot close the loop with each other.

---

## SOLUTION: Completion Queue

A shared JSONL file that web conversations write to (via MCP tool) and Code's cop-sync reads from (to update COP.md). Think of it as a **message queue between Claude instances**.

### Architecture

```
Web (claude.ai) --[log_completion()]--> completion_queue.jsonl (iCloud)
                                              |
                                        cop-sync reads
                                              |
Code (Mac terminal) <--[updates COP.md]-- process_completions()
```

---

## DELIVERABLES (3 items)

### 1. New MCP Tool: `log_completion`

**File:** `~/owens-lifeos/scripts/lifeos_mcp_server.py`

Add this tool following the same pattern as `log_session`:

```python
@mcp.tool()
def log_completion(
    description: str,
    action_id: str = "",
    domain: str = "",
    notes: str = ""
) -> str:
    """Log a task/action completion from any Claude instance so cop-sync can update COP.md.
    
    This is the BRIDGE between web conversations and the COP. When a task is completed
    during a web chat, call this tool so Code's cop-sync picks it up.
    
    Args:
        description: What was completed (e.g., "Dragonslayer admin switch — Rylan moved to Standard User")
        action_id: COP action item number if known (e.g., "2" for Action Item #2). Optional.
        domain: Staff section affected (S1, S2, S3, S4, S6, Medical, CoS). Optional.
        notes: Any additional context. Optional.
    """
    QUEUE_PATH = ICLOUD / "completion_queue.jsonl"
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "description": description,
        "action_id": action_id,
        "domain": domain,
        "notes": notes,
        "source": "web",
        "processed": False
    }
    
    try:
        with open(QUEUE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return f"Completion logged: {description}\nQueued for next cop-sync to update COP.md."
    except Exception as e:
        return f"ERROR logging completion: {e}"


@mcp.tool()
def get_completion_queue() -> str:
    """Read pending (unprocessed) completions from the queue.
    
    Use this to check what completions are waiting to be synced to COP.
    Web COS uses this during morning sweeps to cross-reference before asserting overdue.
    """
    QUEUE_PATH = ICLOUD / "completion_queue.jsonl"
    
    if not QUEUE_PATH.exists():
        return "No completion queue file exists yet. No pending completions."
    
    try:
        entries = []
        for line in QUEUE_PATH.read_text(encoding="utf-8").strip().split("\n"):
            if line.strip():
                entry = json.loads(line)
                if not entry.get("processed", False):
                    entries.append(entry)
        
        if not entries:
            return "Completion queue is empty — all items have been processed by cop-sync."
        
        output = f"**{len(entries)} pending completions (not yet synced to COP):**\n\n"
        for e in entries:
            output += f"- [{e['timestamp'][:10]}] {e['description']}"
            if e.get('action_id'):
                output += f" (Action #{e['action_id']})"
            if e.get('domain'):
                output += f" [{e['domain']}]"
            output += "\n"
        
        return output
    except Exception as e:
        return f"ERROR reading completion queue: {e}"
```

Also add to the docstring at the top of the file:
```
  - log_completion: Log a task completion from web for cop-sync to process
  - get_completion_queue: Read pending completions not yet synced to COP
```

Also add the path constant near the other path definitions:
```python
COMPLETION_QUEUE_PATH = ICLOUD / "completion_queue.jsonl"
```

---

### 2. COP Sync Enhancement: Process Completions

The cop-sync skill (invoked via `battle_rhythm_runner.sh sync` → `claude -p "/sweep sync"`) needs a new STEP 0 before its normal work:

```
STEP 0 — Completion Queue Processing:
1. Read ~/Library/Mobile Documents/com~apple~CloudDocs/completion_queue.jsonl
2. Parse each line as JSON
3. For entries where "processed" is false:
   a. Find matching action item in COP.md by action_id or description
   b. Update COP.md: change status to "✅ COMPLETE [date] (synced from web)"
   c. If the completion resolves a cross-domain flag or running estimate item, update that too
   d. Mark the entry as processed (set "processed": true)
4. Rewrite completion_queue.jsonl with updated entries
5. Log: "Processed N completions from web queue"
```

Find the cop-sync skill prompt (wherever `/sweep sync` is defined — likely in a project's CLAUDE.md or a skill file) and add this step.

---

### 3. Backfill: Already Seeded

The completion queue has been pre-seeded at:
`~/Library/Mobile Documents/com~apple~CloudDocs/completion_queue.jsonl`

Contains 4 entries for items confirmed complete via web conversation history:
- Action #2: Dragonslayer admin switch (3/27)
- Action #8: ADB Fire TV disable (3/22)
- S1: Gulf Shores lodging confirmed — Beach Club BCB-0910 Res #398702 (3/29)
- Action #4: Estate attorney call completed (3/29)

These are ready for cop-sync to process on next run.

---

## TESTING

After building:

1. **Verify MCP tool:** Restart MCP server. From claude.ai, call `log_completion(description="TEST: Build spec verification", domain="S6")`. Then call `get_completion_queue()` to confirm it appears.

2. **Verify cop-sync processes queue:** Run `./battle_rhythm_runner.sh sync` manually. Check COP.md — action items #2, #4, #8 should now show COMPLETE. Check that completion_queue.jsonl entries show `"processed": true`.

3. **Verify no false positives:** After sync, run morning sweep. Dragonslayer, ADB, Gulf Shores should NOT appear as overdue.

---

## SUCCESS CRITERIA

- [ ] `log_completion` MCP tool exists and writes to completion_queue.jsonl
- [ ] `get_completion_queue` MCP tool exists and reads pending entries
- [ ] cop-sync processes the queue and updates COP.md action items
- [ ] Processed entries marked `"processed": true` (not deleted — audit trail)
- [ ] Backfill entries processed on first sync
- [ ] COP.md no longer shows Dragonslayer, ADB, or Gulf Shores as overdue

---

## STANDING ORDER (POST-DEPLOYMENT)

Once deployed, the cross-platform protocol is:

1. **Task completed in web conversation** → COS immediately calls `log_completion()` via MCP
2. **Morning sweeps (web)** → COS calls `get_completion_queue()` to check for pending completions before reporting any item as overdue
3. **cop-sync runs at noon** → processes the queue, updates COP.md

Two instances. One COP. One truth. The queue is the bridge.
