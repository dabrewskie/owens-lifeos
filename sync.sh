#!/usr/bin/env bash
# sync.sh — Owens Life OS bidirectional sync
# Usage:
#   ./sync.sh pull    — pull remote changes (SessionStart, morning-sweep)
#   ./sync.sh push    — commit and push local changes (eod-close)
#   ./sync.sh status  — show sync state

set -euo pipefail

REPO_DIR="$HOME/owens-lifeos"
SKILLS_RUNTIME="$HOME/.claude/skills"
AGENTS_RUNTIME="$HOME/.claude/agents"

cd "$REPO_DIR"

case "${1:-status}" in
  pull)
    git pull --ff-only origin main 2>/dev/null && echo "SYNC: pulled latest" || echo "SYNC: already current"
    ;;
  push)
    if [ -n "$(git status --porcelain)" ]; then
      git add -A
      git commit -m "auto-sync: $(date '+%Y-%m-%d %H:%M') — skills/agents update"
      git push origin main
      echo "SYNC: pushed changes"
    else
      echo "SYNC: nothing to push"
    fi
    ;;
  status)
    echo "=== Life OS Sync Status ==="
    echo "Last commit: $(git log -1 --format='%ai — %s' 2>/dev/null || echo 'none')"
    echo "Pending changes: $(git status --porcelain | wc -l | tr -d ' ')"
    echo "Skills (repo): $(find skills -name 'SKILL.md' | wc -l | tr -d ' ')"
    echo "Agents (repo): $(find agents -name '*.md' | wc -l | tr -d ' ')"
    echo ""
    # Verify symlinks
    broken=0
    for link in "$SKILLS_RUNTIME"/*/SKILL.md; do
      [ -L "$link" ] || continue
      [ -e "$link" ] || { echo "BROKEN SYMLINK: $link"; broken=$((broken+1)); }
    done
    for link in "$AGENTS_RUNTIME"/*.md; do
      [ -L "$link" ] || continue
      [ -e "$link" ] || { echo "BROKEN SYMLINK: $link"; broken=$((broken+1)); }
    done
    [ "$broken" -eq 0 ] && echo "Symlinks: all healthy" || echo "Symlinks: $broken broken"
    ;;
  *)
    echo "Usage: sync.sh [pull|push|status]"
    exit 1
    ;;
esac
