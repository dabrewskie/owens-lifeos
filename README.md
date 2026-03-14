# Owens Life OS

Cross-platform skill and agent synchronization for Tory Owens' Claude-based Life Operating System.

## Architecture

This repo is the **single source of truth** for Life OS system configuration:
- `skills/` — Claude Code native skills (19 skills)
- `agents/` — Claude Code native agents (8 agents)

Local runtime locations (`~/.claude/skills/`, `~/.claude/agents/`) use **symlinks** pointing into this repo. Any edit via Claude Code writes directly to the repo. Remote edits (via claude.ai + GitHub MCP) are pulled automatically.

## Sync Flow

```
Claude Code (local edits) ──> repo files via symlinks ──> git push (eod-close)
                                                              │
claude.ai (GitHub MCP) ────> git push ──────────────────────> │
                                                              v
                                                         GitHub repo
                                                              │
                                                              v
                                                    git pull (SessionStart)
                                                              │
                                                              v
                                                    ~/.claude/skills/ (symlinks)
                                                    ~/.claude/agents/ (symlinks)
```

## Sync Cadence

- **Inbound (pull):** Every Claude Code SessionStart + morning-sweep
- **Outbound (push):** eod-close daily + manual as needed

## Private

This repo is private. It contains system configuration, not personal data.
Personal data (COP, profile, history, financial plan) remains in the iCloud git repo.
