"""Tests of the SessionStart hook (scripts/session_start.py), run as the hook runs it."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT: Path = Path(__file__).resolve().parent.parent
SCRIPT: Path = ROOT / "scripts" / "session_start.py"
sys.path.insert(0, str(ROOT / "scripts"))

import session_start  # noqa: E402

BOARD: str = """# Claude board

## Todo

- T1: one
  - T1a: a sub-item, not counted

## Asks

(none)

## Recommends

- R1: one
- R2: two

## Queue

Lanes:
- Machine: Q1.

In order:
- Q1 (Ready): one
"""


def run_hook(project: Path, source: str = "startup") -> dict[str, Any] | None:
    """Run the hook in a subprocess; returns its JSON output, or None when it printed nothing."""
    env: dict[str, str] = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    done: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps({"cwd": str(project), "source": source, "hook_event_name": "SessionStart"}),
        capture_output=True, text=True, env=env, check=True,
    )
    return json.loads(done.stdout) if done.stdout.strip() else None


class SessionStartTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.project: Path = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_settings(self, settings: dict[str, Any]) -> None:
        (self.project / ".claude").mkdir(exist_ok=True)
        (self.project / ".claude" / "claude-board.json").write_text(json.dumps(settings), encoding="utf-8")

    def test_silent_without_board(self) -> None:
        self.assertIsNone(run_hook(self.project))

    def test_counts_and_rules(self) -> None:
        (self.project / "claude_board.md").write_text(BOARD, encoding="utf-8")
        out: dict[str, Any] | None = run_hook(self.project)
        assert out is not None
        context: str = out["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("Read claude_board.md: 1 todo, 0 asks, 2 recommends, 1 queued", context)
        self.assertIn("Questions for the user go to Asks", context)
        self.assertNotIn("Helper session", context)

    def test_helper_and_wait_alert_on_fresh_sessions_only(self) -> None:
        (self.project / "board.md").write_text(BOARD, encoding="utf-8")
        self.write_settings({
            "board": "board.md", "status_file": "status.txt", "helper": "myHelper",
            "helper_cron": "5 * * * *", "wait_alert": "python watcher.py --wait-alert",
        })
        out: dict[str, Any] | None = run_hook(self.project, "clear")
        assert out is not None
        context: str = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Helper session: myHelper", context)
        self.assertIn('cron "5 * * * *"', context)
        self.assertIn(str(self.project / "status.txt"), context)
        self.assertIn("python watcher.py --wait-alert", context)
        compact: dict[str, Any] | None = run_hook(self.project, "compact")
        assert compact is not None
        context = compact["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn("Helper session", context)
        self.assertNotIn("--wait-alert", context)
        self.assertIn("Read board.md:", context)

    def test_missing_board_with_settings(self) -> None:
        self.write_settings({})
        out: dict[str, Any] | None = run_hook(self.project)
        assert out is not None
        self.assertIn("doesn't exist", out["hookSpecificOutput"]["additionalContext"])

    def test_bad_settings_reported(self) -> None:
        (self.project / ".claude").mkdir()
        (self.project / ".claude" / "claude-board.json").write_text("[1]", encoding="utf-8")
        out: dict[str, Any] | None = run_hook(self.project)
        assert out is not None
        self.assertIn("couldn't read the board settings", out["hookSpecificOutput"]["additionalContext"])

    def test_count_items_ignores_other_sections(self) -> None:
        counts: dict[str, int] = session_start.count_items("## Rules\n- T9: not an item\n## Todo\n- T1: x\n")
        self.assertEqual(counts["Todo"], 1)


if __name__ == "__main__":
    unittest.main()
