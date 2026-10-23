"""PreToolUse hook: remind Claude (never block) to hand bulky data reads to the helper session.

Off unless the project's settings name both a `helper` and `offload_paths` (path fragments such as
"data/", "logs/", ".sqlite"). A Read, Grep, Glob or Bash call whose input names one gets a one-line reminder
in context; the status file and output redirections (a job launch writing its log) don't count, since reading
the status file is the main session's own job and a launch reads nothing.
Standard library only, like session_start.py.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from session_start import load_settings


def offload_hint(settings: dict[str, Any], tool_input: dict[str, Any]) -> str | None:
    """Return the reminder for a tool call, or None when it names no bulky path (or offloading is off)."""
    helper: Any = settings.get("helper")
    paths: Any = settings.get("offload_paths")
    if not helper or not paths:
        return None
    text: str = " ".join(str(v) for v in tool_input.values()).replace("\\", "/").lower()
    status: Any = settings.get("status_file")
    if status:
        text = text.replace(str(status).replace("\\", "/").lower(), "")
    text = re.sub(r">>?\s*\S+", "", text)
    if not any(str(p).replace("\\", "/").lower() in text for p in paths):
        return None
    return (f"Bulky data read: if {helper} is live (ListAgents) and this result doesn't decide your next step "
            "right away, send it there; otherwise go ahead.")


def main() -> int:
    """Run the hook; always exits 0 (a reminder must never block a tool call)."""
    try:
        event: dict[str, Any] = json.loads(sys.stdin.read() or "{}")
        project: Path = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd())
        settings: dict[str, Any] | None = load_settings(project)
        hint: str | None = offload_hint(settings or {}, event.get("tool_input") or {})
    except (OSError, ValueError):
        return 0
    if hint:
        sys.stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": hint}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
