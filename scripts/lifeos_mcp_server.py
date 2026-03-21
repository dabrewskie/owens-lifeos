#!/usr/bin/env python3
"""
Life OS MCP Server — Tory Owens
Exposes Life OS operations as MCP tools for Claude Desktop and Web.
Runs locally on Mac, accessible via stdio transport.

Tools exposed:
  - get_cop: Read the live Common Operating Picture
  - get_profile: Read identity profile
  - get_briefing_packet: Get the cross-platform briefing packet
  - get_health_data: Pull latest health metrics
  - get_financial_snapshot: Current financial state
  - get_action_items: Active action items from COP
  - log_session: Write a session entry to HISTORY.md
  - run_platform_sync: Regenerate briefing packet
  - search_history: Search HISTORY.md for past sessions
  - list_skills: List all Life OS skills
  - get_skill: Read a skill's SKILL.md content
  - create_skill: Create a new skill
  - update_skill: Update an existing skill
  - delete_skill: Delete a skill
  - list_agents: List all Life OS agents
  - get_agent: Read an agent definition
  - create_agent: Create a new agent
  - update_agent: Update an existing agent
  - delete_agent: Delete an agent
  - sync_repo: Pull/push the owens-lifeos GitHub repo
"""
from __future__ import annotations

import json
import subprocess
import re
from datetime import datetime, date
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# ── Paths ──────────────────────────────────────────────────────────────
ICLOUD = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs"
SCRIPTS = Path.home() / "Documents/S6_COMMS_TECH/scripts"
HEALTH_METRICS = (
    Path.home()
    / "Library/Mobile Documents/iCloud~com~ifunography~HealthExport/Documents/Health Metrics"
)

COP_PATH = ICLOUD / "COP.md"
PROFILE_PATH = ICLOUD / "TORY_OWENS_PROFILE.md"
HISTORY_PATH = ICLOUD / "TORY_OWENS_HISTORY.md"
BRIEFING_PATH = ICLOUD / "BRIEFING_PACKET.md"
FINANCIAL_PLAN_PATH = ICLOUD / "Family/Financial-Plan/Owens_Family_Financial_Plan.md"
HEALTH_READER = SCRIPTS / "health_auto_export_reader.py"
PACKET_GENERATOR = SCRIPTS / "briefing_packet_generator.py"
LIFEOS_REPO = Path.home() / "owens-lifeos"
SKILLS_DIR = LIFEOS_REPO / "skills"
AGENTS_DIR = LIFEOS_REPO / "agents"
SYNC_SCRIPT = LIFEOS_REPO / "sync.sh"

# ── Server ─────────────────────────────────────────────────────────────
mcp = FastMCP("Life OS")


def _read_file(path: Path, max_chars: int = 0) -> str:
    """Read a file, return contents or error message."""
    try:
        text = path.read_text(encoding="utf-8")
        if max_chars and len(text) > max_chars:
            return text[:max_chars] + f"\n\n... (truncated at {max_chars} chars, full file is {len(text)} chars)"
        return text
    except FileNotFoundError:
        return f"ERROR: File not found: {path}"
    except Exception as e:
        return f"ERROR reading {path}: {e}"


def _run_script(script_path: Path, args: list[str] | None = None, timeout: int = 30) -> str:
    """Run a Python script and return output."""
    cmd = ["python3", str(script_path)]
    if args:
        cmd.extend(args)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=str(Path.home())
        )
        output = result.stdout
        if result.stderr:
            output += f"\n\nSTDERR:\n{result.stderr}"
        return output if output.strip() else "Script completed with no output."
    except subprocess.TimeoutExpired:
        return f"ERROR: Script timed out after {timeout}s"
    except FileNotFoundError:
        return f"ERROR: Script not found: {script_path}"
    except Exception as e:
        return f"ERROR running script: {e}"


# ── Tools ──────────────────────────────────────────────────────────────


@mcp.tool()
def get_cop() -> str:
    """Get the full Common Operating Picture (COP) — operational state across all Life OS domains.
    Includes CCIR, staff running estimates, action items, 90-day horizon, and cross-domain signals."""
    content = _read_file(COP_PATH)
    # Staleness warning: if COP.md hasn't been modified in >48h, warn the reader
    if COP_PATH.exists():
        import time
        age_h = (time.time() - COP_PATH.stat().st_mtime) / 3600
        if age_h > 48:
            days = age_h / 24
            warning = (
                f"⚠️ STALENESS WARNING: COP.md was last updated {days:.0f} days ago. "
                f"Financial figures, action item statuses, and running estimates may be outdated. "
                f"Route to Claude Code and run 'sweep sync' to refresh before making decisions "
                f"based on these numbers.\n"
                f"{'=' * 60}\n\n"
            )
            content = warning + content
    return content


@mcp.tool()
def get_profile() -> str:
    """Get Tory Owens' identity profile — family, military service, career, health, personality, operating style.
    Load this before any personal interaction to understand who you're working with."""
    return _read_file(PROFILE_PATH)


@mcp.tool()
def get_briefing_packet() -> str:
    """Get the cross-platform briefing packet — condensed identity + COP + Standing Orders.
    This is the same document used as claude.ai Project instructions."""
    return _read_file(BRIEFING_PATH)


@mcp.tool()
def get_action_items() -> str:
    """Extract active action items from the COP. Returns the action items table with status, owner, and due dates."""
    cop = _read_file(COP_PATH)
    if cop.startswith("ERROR"):
        return cop
    # Extract the action items section
    match = re.search(
        r"## ACTION ITEMS \(Tracked\)\s*\n(.*?)(?=\n---|\n## )",
        cop,
        re.DOTALL,
    )
    if match:
        return f"# Action Items (from COP)\nExtracted: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{match.group(1).strip()}"
    return "Could not extract action items from COP. The COP may have been reformatted."


@mcp.tool()
def get_health_data(days: int = 7) -> str:
    """Pull latest health data from Health Auto Export. Returns macro compliance, body comp, sleep, vitals.

    Args:
        days: Number of days to analyze (default 7)
    """
    if HEALTH_READER.exists():
        return _run_script(HEALTH_READER, timeout=30)

    # Fallback: read most recent JSON files directly
    if not HEALTH_METRICS.exists():
        return "ERROR: Health Metrics directory not found. Health Auto Export may not be syncing."

    files = sorted(HEALTH_METRICS.glob("HealthAutoExport-*.json"), reverse=True)
    if not files:
        return "ERROR: No health data files found."

    latest = files[0]
    try:
        data = json.loads(latest.read_text())
        metrics = data.get("data", {}).get("metrics", [])
        summary_lines = [
            f"# Health Data — {latest.stem.replace('HealthAutoExport-', '')}",
            f"Source: {latest.name}",
            f"Metrics available: {len(metrics)}",
            "",
        ]
        # Extract key metrics
        targets = {"protein": 210, "carbohydrates": 130, "total_fat": 71, "dietary_energy": 2000}
        for m in metrics:
            name = m.get("name", "")
            data_points = m.get("data", [])
            if data_points:
                latest_val = data_points[-1]
                qty = latest_val.get("qty", latest_val.get("totalSleep", "N/A"))
                units = m.get("units", "")
                summary_lines.append(f"- **{name}**: {qty} {units}")

        return "\n".join(summary_lines)
    except Exception as e:
        return f"ERROR parsing health data: {e}"


@mcp.tool()
def get_financial_snapshot() -> str:
    """Get current financial state — net worth, FCF, RPED gap, emergency fund status, investment portfolio.
    Extracted from the COP S4 section and financial plan."""
    cop = _read_file(COP_PATH)
    if cop.startswith("ERROR"):
        return cop

    # Extract S4 section
    match = re.search(
        r"### S4 — Logistics/Finance.*?(?=\n### |\n---)",
        cop,
        re.DOTALL,
    )
    s4 = match.group(0) if match else "S4 section not found in COP."

    # Extract quick reference if available in briefing packet
    bp = _read_file(BRIEFING_PATH)
    qr_match = re.search(
        r"## SECTION 4: QUICK REFERENCE.*?(?=\n## SECTION |\n---\s*$)",
        bp,
        re.DOTALL,
    )
    quick_ref = qr_match.group(0) if qr_match else ""

    return f"# Financial Snapshot\nExtracted: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{s4}\n\n{quick_ref}"


@mcp.tool()
def log_session(summary: str, domains: str, decisions: str = "", action_items: str = "") -> str:
    """Log a session from any Claude instance to HISTORY.md so Claude Code can ingest it.

    Args:
        summary: 1-3 sentence summary of what happened in this session
        domains: Comma-separated domains touched (S1,S2,S3,S4,S5,S6,Medical,CoS)
        decisions: Any decisions made (optional)
        action_items: Any action items generated (optional)
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    date_str = datetime.now().strftime("%Y-%m-%d")

    entry_parts = [f"\n**[{date_str}]** — [Cross-Platform Session | {domains}] {summary}"]
    if decisions:
        entry_parts.append(f"  Decisions: {decisions}")
    if action_items:
        entry_parts.append(f"  Action Items: {action_items}")

    entry = "\n".join(entry_parts) + "\n"

    try:
        with open(HISTORY_PATH, "a", encoding="utf-8") as f:
            f.write(entry)
        return f"Session logged to HISTORY.md at {timestamp}.\nEntry: {entry.strip()}"
    except Exception as e:
        return f"ERROR logging session: {e}"


@mcp.tool()
def run_platform_sync() -> str:
    """Regenerate the briefing packet and trigger cross-platform sync.
    Updates BRIEFING_PACKET.md in iCloud with latest PROFILE + COP + Standing Orders."""
    if not PACKET_GENERATOR.exists():
        return f"ERROR: Briefing packet generator not found at {PACKET_GENERATOR}"
    return _run_script(PACKET_GENERATOR, timeout=30)


@mcp.tool()
def search_history(query: str, max_results: int = 10) -> str:
    """Search HISTORY.md for past sessions matching a query.

    Args:
        query: Search term (case-insensitive substring match)
        max_results: Maximum number of matching entries to return (default 10)
    """
    text = _read_file(HISTORY_PATH)
    if text.startswith("ERROR"):
        return text

    # Split into entries (each starts with **[date]**)
    entries = re.split(r"(?=\*\*\[)", text)
    matches = [e.strip() for e in entries if query.lower() in e.lower()]

    if not matches:
        return f"No history entries matching '{query}'."

    matches = matches[-max_results:]  # most recent matches
    return f"# History Search: '{query}'\nFound {len(matches)} matches (showing up to {max_results}):\n\n" + "\n\n---\n\n".join(matches)


@mcp.tool()
def get_ccir_status() -> str:
    """Get the current CCIR (Commander's Critical Information Requirements) status.
    These are the items that require immediate attention when triggered."""
    cop = _read_file(COP_PATH)
    if cop.startswith("ERROR"):
        return cop

    match = re.search(
        r"## COMMANDER'S CRITICAL INFORMATION REQUIREMENTS.*?(?=\n---)",
        cop,
        re.DOTALL,
    )
    if match:
        return f"# CCIR Status\nExtracted: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{match.group(0).strip()}"
    return "Could not extract CCIR from COP."


@mcp.tool()
def get_90day_horizon() -> str:
    """Get the 90-day horizon — upcoming events, deadlines, and milestones across all domains."""
    cop = _read_file(COP_PATH)
    if cop.startswith("ERROR"):
        return cop

    match = re.search(
        r"## 90-DAY HORIZON.*?(?=\n---)",
        cop,
        re.DOTALL,
    )
    if match:
        today = date.today().strftime("%Y-%m-%d")
        return f"# 90-Day Horizon\nToday: {today}\n\n{match.group(0).strip()}"
    return "Could not extract 90-day horizon from COP."


@mcp.tool()
def recommend_platform(task_description: str) -> str:
    """Given a task description, recommend the best Claude platform to accomplish it.
    Use this when the current platform may not be the best fit for what the user needs.

    Args:
        task_description: What the user is trying to accomplish
    """
    task = task_description.lower()

    # Keywords → platform mapping
    routing = {
        "code": {
            "keywords": ["build skill", "create agent", "modify hook", "edit file", "write code",
                         "create script", "build tool", "modify skill", "scheduled task",
                         "update claude.md", "git", "deploy", "install"],
            "platform": "Claude Code",
            "reason": "Skills, agents, hooks, and file modifications require Claude Code's engine."
        },
        "desktop_mcp": {
            "keywords": ["health check", "health data", "pull cop", "financial snapshot",
                         "log session", "search history", "ccir", "action items",
                         "platform sync", "90 day"],
            "platform": "Claude Desktop (with Life OS MCP)",
            "reason": "Desktop has the Life OS MCP server with live data access and session logging."
        },
        "ios": {
            "keywords": ["voice", "on the go", "quick question", "driving", "walking",
                         "mobile", "phone"],
            "platform": "Claude iOS (Owens Life OS Project)",
            "reason": "iOS is best for voice conversations and quick mobile interactions."
        },
        "research": {
            "keywords": ["research", "pubmed", "clinical trial", "literature", "deep dive",
                         "compare options", "evidence"],
            "platform": "Claude Code or Claude.ai Web",
            "reason": "Both have research MCP connectors (PubMed, bioRxiv, Clinical Trials, Consensus)."
        },
        "cowork": {
            "keywords": ["automate", "schedule", "recurring", "email triage", "gmail sweep",
                         "calendar management"],
            "platform": "CoWork",
            "reason": "CoWork handles scheduled automations, email triage, and calendar management."
        },
        "strategic": {
            "keywords": ["strategy", "long range", "retirement", "rped", "5 year plan",
                         "career", "financial plan", "deep analysis"],
            "platform": "Claude Code",
            "reason": "Strategic sessions benefit from Claude Code's full skill suite (S5, financial-intelligence, life-intelligence agent)."
        },
    }

    recommendations = []
    for key, config in routing.items():
        if any(kw in task for kw in config["keywords"]):
            recommendations.append(config)

    if not recommendations:
        return (
            f"Task: '{task_description}'\n\n"
            "No strong platform preference detected. General guidance:\n"
            "- Complex/multi-step → Claude Code\n"
            "- Live data queries → Claude Desktop (MCP)\n"
            "- Quick/mobile → iOS app\n"
            "- Automations → CoWork\n"
            "- Research → Code or Web"
        )

    lines = [f"Task: '{task_description}'\n"]
    for i, rec in enumerate(recommendations):
        prefix = "RECOMMENDED" if i == 0 else "ALSO"
        lines.append(f"**{prefix}: {rec['platform']}**")
        lines.append(f"  {rec['reason']}\n")

    return "\n".join(lines)


# ── Skill & Agent CRUD ─────────────────────────────────────────────────


def _git_commit_push(message: str) -> str:
    """Commit all changes in the Life OS repo and push to GitHub."""
    try:
        result = subprocess.run(
            ["bash", str(SYNC_SCRIPT), "push"],
            capture_output=True, text=True, timeout=30,
            cwd=str(LIFEOS_REPO),
        )
        return result.stdout.strip() + (f"\n{result.stderr}" if result.stderr else "")
    except Exception as e:
        return f"ERROR pushing: {e}"


@mcp.tool()
def list_skills() -> str:
    """List all Life OS skills with their names and descriptions."""
    if not SKILLS_DIR.exists():
        return "ERROR: Skills directory not found."
    skills = []
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists():
            text = skill_file.read_text(encoding="utf-8")
            # Extract name and description from frontmatter
            name_match = re.search(r"^name:\s*(.+)$", text, re.MULTILINE)
            desc_match = re.search(r"description:\s*[>|]?\s*\n?\s*(.+?)(?:\n\S|\n---)", text, re.DOTALL)
            name = name_match.group(1).strip() if name_match else skill_dir.name
            desc = desc_match.group(1).strip().split("\n")[0] if desc_match else "No description"
            skills.append(f"- **{name}**: {desc}")
    return f"# Life OS Skills ({len(skills)} total)\n\n" + "\n".join(skills)


@mcp.tool()
def get_skill(skill_name: str) -> str:
    """Read the full SKILL.md content for a specific skill.

    Args:
        skill_name: Skill directory name (e.g., 'morning-sweep', 'cop-sync')
    """
    skill_file = SKILLS_DIR / skill_name / "SKILL.md"
    return _read_file(skill_file)


@mcp.tool()
def create_skill(skill_name: str, content: str, auto_push: bool = True) -> str:
    """Create a new Life OS skill. The content should be a complete SKILL.md with YAML frontmatter.

    Args:
        skill_name: Skill directory name (lowercase, hyphenated, e.g., 'new-skill')
        content: Full SKILL.md content including --- frontmatter with name and description
        auto_push: Automatically commit and push to GitHub (default True)
    """
    skill_dir = SKILLS_DIR / skill_name
    if skill_dir.exists():
        return f"ERROR: Skill '{skill_name}' already exists. Use update_skill instead."

    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(content, encoding="utf-8")

    # Create symlink in Claude Code runtime
    runtime_link = Path.home() / ".claude/skills" / skill_name
    if not runtime_link.exists():
        runtime_link.symlink_to(skill_dir)

    result = f"Skill '{skill_name}' created at {skill_file}\nSymlink: {runtime_link} -> {skill_dir}"
    if auto_push:
        result += "\n" + _git_commit_push(f"add skill: {skill_name}")
    return result


@mcp.tool()
def update_skill(skill_name: str, content: str, auto_push: bool = True) -> str:
    """Update an existing Life OS skill with new content.

    Args:
        skill_name: Skill directory name (e.g., 'morning-sweep')
        content: Complete new SKILL.md content (replaces entire file)
        auto_push: Automatically commit and push to GitHub (default True)
    """
    skill_file = SKILLS_DIR / skill_name / "SKILL.md"
    if not skill_file.exists():
        return f"ERROR: Skill '{skill_name}' not found. Use create_skill instead."

    skill_file.write_text(content, encoding="utf-8")
    result = f"Skill '{skill_name}' updated."
    if auto_push:
        result += "\n" + _git_commit_push(f"update skill: {skill_name}")
    return result


@mcp.tool()
def delete_skill(skill_name: str, auto_push: bool = True) -> str:
    """Delete a Life OS skill. Removes the skill directory and its symlink.

    Args:
        skill_name: Skill directory name to delete
        auto_push: Automatically commit and push to GitHub (default True)
    """
    import shutil

    skill_dir = SKILLS_DIR / skill_name
    if not skill_dir.exists():
        return f"ERROR: Skill '{skill_name}' not found."

    # Remove runtime symlink first
    runtime_link = Path.home() / ".claude/skills" / skill_name
    if runtime_link.is_symlink():
        runtime_link.unlink()

    shutil.rmtree(skill_dir)
    result = f"Skill '{skill_name}' deleted."
    if auto_push:
        result += "\n" + _git_commit_push(f"delete skill: {skill_name}")
    return result


@mcp.tool()
def list_agents() -> str:
    """List all Life OS agents with their names and descriptions."""
    if not AGENTS_DIR.exists():
        return "ERROR: Agents directory not found."
    agents = []
    for agent_file in sorted(AGENTS_DIR.glob("*.md")):
        text = agent_file.read_text(encoding="utf-8")
        name_match = re.search(r"^name:\s*(.+)$", text, re.MULTILINE)
        desc_match = re.search(r"description:\s*[>|]?\s*\n?\s*(.+?)(?:\n\S|\n---)", text, re.DOTALL)
        name = name_match.group(1).strip() if name_match else agent_file.stem
        desc = desc_match.group(1).strip().split("\n")[0] if desc_match else "No description"
        agents.append(f"- **{name}**: {desc}")
    return f"# Life OS Agents ({len(agents)} total)\n\n" + "\n".join(agents)


@mcp.tool()
def get_agent(agent_name: str) -> str:
    """Read the full agent definition file.

    Args:
        agent_name: Agent filename without extension (e.g., 'financial-reviewer')
    """
    agent_file = AGENTS_DIR / f"{agent_name}.md"
    return _read_file(agent_file)


@mcp.tool()
def create_agent(agent_name: str, content: str, auto_push: bool = True) -> str:
    """Create a new Life OS agent. The content should be a complete agent .md file with YAML frontmatter.

    Args:
        agent_name: Agent filename without extension (lowercase, hyphenated)
        content: Full agent .md content including --- frontmatter with name, description, tools
        auto_push: Automatically commit and push to GitHub (default True)
    """
    agent_file = AGENTS_DIR / f"{agent_name}.md"
    if agent_file.exists():
        return f"ERROR: Agent '{agent_name}' already exists. Use update_agent instead."

    agent_file.write_text(content, encoding="utf-8")

    # Create symlink in Claude Code runtime
    runtime_link = Path.home() / ".claude/agents" / f"{agent_name}.md"
    if not runtime_link.exists():
        runtime_link.symlink_to(agent_file)

    result = f"Agent '{agent_name}' created at {agent_file}\nSymlink: {runtime_link} -> {agent_file}"
    if auto_push:
        result += "\n" + _git_commit_push(f"add agent: {agent_name}")
    return result


@mcp.tool()
def update_agent(agent_name: str, content: str, auto_push: bool = True) -> str:
    """Update an existing Life OS agent with new content.

    Args:
        agent_name: Agent filename without extension (e.g., 'financial-reviewer')
        content: Complete new agent .md content (replaces entire file)
        auto_push: Automatically commit and push to GitHub (default True)
    """
    agent_file = AGENTS_DIR / f"{agent_name}.md"
    if not agent_file.exists():
        return f"ERROR: Agent '{agent_name}' not found. Use create_agent instead."

    agent_file.write_text(content, encoding="utf-8")
    result = f"Agent '{agent_name}' updated."
    if auto_push:
        result += "\n" + _git_commit_push(f"update agent: {agent_name}")
    return result


@mcp.tool()
def delete_agent(agent_name: str, auto_push: bool = True) -> str:
    """Delete a Life OS agent. Removes the agent file and its symlink.

    Args:
        agent_name: Agent filename without extension to delete
        auto_push: Automatically commit and push to GitHub (default True)
    """
    agent_file = AGENTS_DIR / f"{agent_name}.md"
    if not agent_file.exists():
        return f"ERROR: Agent '{agent_name}' not found."

    # Remove runtime symlink first
    runtime_link = Path.home() / ".claude/agents" / f"{agent_name}.md"
    if runtime_link.is_symlink():
        runtime_link.unlink()

    agent_file.unlink()
    result = f"Agent '{agent_name}' deleted."
    if auto_push:
        result += "\n" + _git_commit_push(f"delete agent: {agent_name}")
    return result


@mcp.tool()
def sync_repo(direction: str = "pull") -> str:
    """Pull or push the owens-lifeos GitHub repo to sync skills and agents across platforms.

    Args:
        direction: 'pull' to get remote changes, 'push' to publish local changes, 'status' to check state
    """
    if direction not in ("pull", "push", "status"):
        return "ERROR: direction must be 'pull', 'push', or 'status'"
    try:
        result = subprocess.run(
            ["bash", str(SYNC_SCRIPT), direction],
            capture_output=True, text=True, timeout=30,
            cwd=str(LIFEOS_REPO),
        )
        return result.stdout.strip() + (f"\n{result.stderr}" if result.stderr else "")
    except Exception as e:
        return f"ERROR: {e}"


# ── Entry Point ────────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run(transport="stdio")
