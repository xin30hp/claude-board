"""SessionStart hook: put the board rules, the board's item counts and the startup steps into context.

Reads the hook's JSON from stdin (cwd, source) and prints a SessionStart hookSpecificOutput JSON. Silent in a
project without a board: one is used only when `.claude/claude-board.json` exists or the board file does.
Standard library only, so it runs wherever Python 3.8+ does.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

SETTINGS_PATH: str = ".claude/claude-board.json"
DEFAULT_BOARD: str = "claude_board.md"
DEFAULT_CRON: str = "7 * * * *"
PLUGIN_ROOT: Path = Path(__file__).resolve().parent.parent
RULES_PATH: Path = PLUGIN_ROOT / "skills" / "board" / "board_rules.md"
# Board sections in order, with the key letter of their items.
SECTIONS: dict[str, str] = {"Todo": "T", "Asks": "A", "Recommends": "R", "Queue": "Q"}
SINGULAR: dict[str, str] = {"Todo": "todo", "Asks": "ask", "Recommends": "recommend", "Queue": "queued"}


def load_settings(project: Path) -> dict[str, Any] | None:
    """Return the project's board settings, {} when only the default board exists, None without a board.

    Raises:
        ValueError: the settings file isn't a JSON object.
    """
    path: Path = project / SETTINGS_PATH
    if path.is_file():
        settings: Any = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(settings, dict):
            raise ValueError(f"{SETTINGS_PATH} must hold a JSON object")
        return settings
    if (project / DEFAULT_BOARD).is_file():
        return {}
    return None


def count_items(board_text: str) -> dict[str, int]:
    """Count the top-level items (lines "- T1...", "- A2..." at column 0) of each board section."""
    counts: dict[str, int] = {name: 0 for name in SECTIONS}
    section: str | None = None
    line: str
    for line in board_text.splitlines():
        heading: re.Match[str] | None = re.match(r"^##\s+(\w+)", line)
        if heading:
            section = heading.group(1) if heading.group(1) in SECTIONS else None
        elif section and re.match(rf"^- {SECTIONS[section]}\d+", line):
            counts[section] += 1
    return counts


def summary_line(board_name: str, counts: dict[str, int]) -> str:
    """Return e.g. "Read claude_board.md: 2 todos, 0 asks, 10 recommends, 11 queued"."""
    parts: list[str] = []
    name: str
    for name, n in counts.items():
        word: str = SINGULAR[name]
        parts.append(f"{n} {word}" if n == 1 or word == "queued" else f"{n} {word}s")
    return f"Read {board_name}: " + ", ".join(parts)


def status_job_message(project: Path, board: Path, status: Path | None, cron: str) -> str:
    """Return the message that hands the hourly status job to the helper session."""
    shown: str = f"prints {board}"
    if status is not None:
        shown += f", then {status},"
    return (
        f"Repo location: {project}\n"
        "Hourly status job, requested by the user (if your permission check blocks CronCreate, ask your user to "
        "approve it).\n"
        f'The job: cron "{cron}", prompt exactly "status update"; each run {shown} each verbatim inside its own '
        "plain code fence (three backticks, no language) so the app shows the raw text instead of rendering "
        "markdown, with no thinking, summary or comment.\n"
        "Run CronList; if no such job exists, create it with CronCreate and run the status update once right "
        "away. Reply in one line whether the job existed or was created."
    )


def build_context(project: Path, settings: dict[str, Any], source: str) -> str:
    """Return the additionalContext text for a session start of the given source (startup, clear, resume, compact)."""
    board: Path = project / str(settings.get("board", DEFAULT_BOARD))
    status_name: str | None = settings.get("status_file")
    status: Path | None = project / status_name if status_name else None
    helper: str | None = settings.get("helper")
    wait_alert: str | None = settings.get("wait_alert")
    rules: str = RULES_PATH.read_text(encoding="utf-8")
    lines: list[str] = [
        f"claude-board plugin (session start: {source}). The board rules follow; they apply to this project.",
        "",
    ]
    fresh: bool = source in ("startup", "clear")
    steps: list[str] = []
    if board.is_file():
        counts: dict[str, int] = count_items(board.read_text(encoding="utf-8"))
        steps.append(
            f"Read the board ({board}) and these rules"
            + (f", then the status file ({status})" if status is not None else "")
            + f'; then tell the user, e.g. "{summary_line(board.name, counts)}" (counted by the hook).'
        )
    else:
        template: str = str(settings.get("template", PLUGIN_ROOT / "templates" / "claude_board.example.md"))
        steps.append(f"The board {board} doesn't exist: create it from the template ({template}).")
    if fresh and helper:
        message: str = status_job_message(
            project, board, status, str(settings.get("helper_cron", DEFAULT_CRON))
        )
        steps.append(
            f"Helper session: {helper}. After ListAgents, if it is live, send it this message (SendMessage); if "
            f"not, gently ask the user to start one:\n{message}"
        )
    if fresh and wait_alert:
        steps.append(
            f"Start the wait-alert as a background task (it stops any older one): {wait_alert} "
            "(run from the project root). Start it again after handling each alert."
        )
    lines.append("Startup steps now:")
    i: int
    step: str
    for i, step in enumerate(steps, 1):
        lines.append(f"{i}. {step}")
    lines += ["", rules]
    return "\n".join(lines)


def main() -> int:
    """Run the hook; returns the exit code (0 also on a bad settings file, reported in context instead)."""
    raw: str = sys.stdin.read() if not sys.stdin.isatty() else ""
    event: dict[str, Any] = json.loads(raw) if raw.strip() else {}
    project: Path = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd())
    source: str = str(event.get("source", "startup"))
    try:
        settings: dict[str, Any] | None = load_settings(project)
        if settings is None:
            return 0
        context: str = build_context(project, settings, source)
    except (OSError, ValueError) as error:
        context = f"claude-board plugin: couldn't read the board settings ({error}); fix {SETTINGS_PATH}."
    output: dict[str, Any] = {
        "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}
    }
    # ASCII-only JSON, so a Windows console code page can't garble it.
    sys.stdout.write(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
