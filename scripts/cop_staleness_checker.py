#!/usr/bin/env python3
"""COP staleness checker — reads COP.md, finds 'Last Updated: YYYY-MM-DD' lines,
and reports sections that are stale (>7d AMBER, >14d RED)."""

import os
import re
import sys
from datetime import datetime

def main():
    cop_path = os.path.expanduser(
        "~/Library/Mobile Documents/com~apple~CloudDocs/COP.md"
    )

    if not os.path.exists(cop_path):
        print("COP: File not found")
        return

    try:
        with open(cop_path, "r") as f:
            content = f.read()
    except IOError:
        print("COP: Unable to read file")
        return

    today = datetime.now()
    lines = content.split("\n")

    # Track current section heading and last-updated dates
    current_section = "Unknown"
    sections = []  # list of (section_name, days_stale)

    for line in lines:
        # Detect section headings (## or ### level)
        heading_match = re.match(r'^#{1,3}\s+(.+)', line)
        if heading_match:
            current_section = heading_match.group(1).strip()

        # Detect "Last Updated: YYYY-MM-DD" — handles markdown bold (**), colons, etc.
        date_match = re.search(r'\*{0,2}[Ll]ast\s+[Uu]pdated\*{0,2}[:\s*]+(\d{4}-\d{2}-\d{2})', line)
        if date_match:
            try:
                updated = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                days = (today - updated).days
                sections.append((current_section, days))
            except ValueError:
                pass

    if not sections:
        print("COP: No 'Last Updated' dates found")
        return

    red = [(name, days) for name, days in sections if days > 14]
    amber = [(name, days) for name, days in sections if 7 < days <= 14]

    parts = []
    if red:
        red_str = ", ".join(f"{name}: {days}d" for name, days in red)
        parts.append(f"{len(red)} section{'s' if len(red)>1 else ''} RED ({red_str})")
    if amber:
        amber_str = ", ".join(f"{name}: {days}d" for name, days in amber)
        parts.append(f"{len(amber)} section{'s' if len(amber)>1 else ''} AMBER ({amber_str})")

    if parts:
        print(f"COP: {' | '.join(parts)}")
    else:
        print("COP: All sections current")


if __name__ == "__main__":
    main()
