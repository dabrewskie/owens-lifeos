#!/usr/bin/env python3
"""
memory_expander.py — Life OS Memory Expansion System
Runs as a SessionStart hook. Reads all memory files, COP executive summary,
and latest battle rhythm outputs. Outputs a compressed briefing injected
into every Claude Code session context.

This effectively bypasses the 200-line MEMORY.md limit by loading full
memory content through the hook system.

Safety: Pure read-only. No file mutations. No network calls.
Graceful degradation: if any file is missing, skip it and continue.
"""

import os
import sys
import glob
import json
from datetime import datetime, timedelta
from pathlib import Path

# ─── Configuration ───────────────────────────────────────────────
MEMORY_DIR = os.path.expanduser("~/.claude/projects/-Users-toryowens/memory")
COP_PATH = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/COP.md")
ICLOUD_ROOT = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs")

# Latest battle rhythm output files
LATEST_FILES = {
    "morning-sweep": os.path.join(ICLOUD_ROOT, "morning-sweep-latest.md"),
    "eod-close": os.path.join(ICLOUD_ROOT, "eod-close-latest.md"),
    "cop-sync": os.path.join(ICLOUD_ROOT, "cop-sync-latest.md"),
    "evolution-intel": os.path.join(ICLOUD_ROOT, "evolution-intel-latest.md"),
    "sentinel-scan": os.path.join(ICLOUD_ROOT, "sentinel-scan-latest.md"),
}

# Maximum lines to extract from each source
MAX_COP_LINES = 150       # Executive summary from COP
MAX_MEMORY_FILE = 80      # Per memory file
MAX_LATEST_LINES = 40     # Per latest output file
MAX_TOTAL_OUTPUT = 800    # Total output cap (keep context reasonable)

# ─── Helpers ─────────────────────────────────────────────────────

def safe_read(path, max_lines=None):
    """Read a file safely. Return content or None."""
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            if max_lines:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line)
                return ''.join(lines)
            return f.read()
    except (FileNotFoundError, PermissionError, OSError):
        return None


def file_age_days(path):
    """Return file age in days, or -1 if inaccessible."""
    try:
        mtime = os.path.getmtime(path)
        age = (datetime.now() - datetime.fromtimestamp(mtime)).days
        return age
    except (FileNotFoundError, OSError):
        return -1


def extract_cop_summary(cop_content):
    """Extract the executive-level sections from COP.md."""
    if not cop_content:
        return "COP: unavailable"

    lines = cop_content.split('\n')
    summary_lines = []
    in_section = False
    section_count = 0

    # Extract: header, CCIR, Action Items, Cross-Domain Flags, Blind Spots
    priority_headers = [
        'CCIR', 'ACTION ITEMS', 'CROSS-DOMAIN', 'BLIND SPOTS', 'SWOT',
        '90-DAY HORIZON', 'S4', 'MEDICAL', 'S6'
    ]

    for line in lines:
        # Always include top-level headers
        if line.startswith('# ') or line.startswith('## '):
            header_text = line.upper()
            if any(h in header_text for h in priority_headers):
                in_section = True
                section_count = 0
                summary_lines.append(line)
                continue
            else:
                in_section = False
                continue

        if in_section and section_count < 30:
            summary_lines.append(line)
            section_count += 1

    return '\n'.join(summary_lines[:MAX_COP_LINES])


def load_memory_files():
    """Load all memory/*.md files except MEMORY.md itself."""
    memories = []
    pattern = os.path.join(MEMORY_DIR, "*.md")

    for filepath in sorted(glob.glob(pattern)):
        basename = os.path.basename(filepath)
        if basename == "MEMORY.md":
            continue

        content = safe_read(filepath, max_lines=MAX_MEMORY_FILE)
        if content:
            memories.append({
                'name': basename,
                'content': content.strip(),
                'age_days': file_age_days(filepath)
            })

    return memories


def load_latest_outputs():
    """Load recent battle rhythm outputs."""
    outputs = []
    for name, path in LATEST_FILES.items():
        age = file_age_days(path)
        if age < 0:
            outputs.append(f"  {name}: FILE NOT FOUND")
            continue
        if age > 7:
            outputs.append(f"  {name}: STALE ({age} days old)")
            continue

        content = safe_read(path, max_lines=MAX_LATEST_LINES)
        if content:
            # Take first meaningful lines as summary
            lines = [l for l in content.strip().split('\n') if l.strip()]
            summary = '\n'.join(lines[:15])
            outputs.append(f"  {name} ({age}d old):\n{summary}")
        else:
            outputs.append(f"  {name}: EMPTY")

    return outputs


# ─── Main Output ─────────────────────────────────────────────────

def main():
    output_lines = []
    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    output_lines.append(f"Memory Expansion: {today}")
    output_lines.append("")

    # ── Section 1: Full Memory Files ──
    memories = load_memory_files()
    if memories:
        output_lines.append("=== EXPANDED MEMORY ===")
        for mem in memories:
            output_lines.append(f"--- {mem['name']} ---")
            output_lines.append(mem['content'])
            output_lines.append("")

    # ── Section 2: COP Executive Summary ──
    cop_content = safe_read(COP_PATH)
    if cop_content:
        cop_summary = extract_cop_summary(cop_content)
        if cop_summary:
            output_lines.append("=== COP EXECUTIVE SUMMARY ===")
            output_lines.append(cop_summary)
            output_lines.append("")

    # ── Section 3: Latest Battle Rhythm Outputs ──
    latest = load_latest_outputs()
    if latest:
        output_lines.append("=== BATTLE RHYTHM STATUS ===")
        for item in latest:
            output_lines.append(item)
        output_lines.append("")

    # ── Section 4: Data Freshness Quick Check ──
    output_lines.append("=== DATA FRESHNESS ===")
    freshness_checks = {
        "COP.md": COP_PATH,
        "Financial Plan": os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/Family/Financial-Plan/Owens_Family_Financial_Plan.md"),
        "invest_intel_data.json": os.path.expanduser("~/Documents/S6_COMMS_TECH/dashboard/invest_intel_data.json"),
        "cop_data.json": os.path.expanduser("~/Documents/S6_COMMS_TECH/dashboard/cop_data.json"),
        "prediction_data.json": os.path.expanduser("~/Documents/S6_COMMS_TECH/dashboard/prediction_data.json"),
        "HISTORY.md": os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/TORY_OWENS_HISTORY.md"),
    }
    for name, path in freshness_checks.items():
        age = file_age_days(path)
        if age < 0:
            status = "MISSING"
        elif age == 0:
            status = "CURRENT"
        elif age <= 3:
            status = f"{age}d old"
        elif age <= 7:
            status = f"AMBER ({age}d)"
        else:
            status = f"RED ({age}d)"
        output_lines.append(f"  {name}: {status}")

    # ── Enforce total output cap ──
    full_output = '\n'.join(output_lines)
    lines = full_output.split('\n')
    if len(lines) > MAX_TOTAL_OUTPUT:
        lines = lines[:MAX_TOTAL_OUTPUT]
        lines.append(f"... (truncated at {MAX_TOTAL_OUTPUT} lines)")

    print('\n'.join(lines))


if __name__ == "__main__":
    main()
