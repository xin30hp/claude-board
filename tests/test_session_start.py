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
        self.assertIn("Read claude_board.md: 1 todo (untagged: T1), 0 asks, 2 recommends, 1 queued", context)
        self.assertIn("Questions for the user go to Asks", context)
        self.assertNotIn("Helper session: myHelper", context)
        self.assertNotIn("Start the wait-alert", context)

    def test_helper_and_wait_alert_by_source(self) -> None:
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
        self.assertIn("/rename myHelper", context)
        resume: dict[str, Any] | None = run_hook(self.project, "resume")
        assert resume is not None
        context = resume["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Helper session: myHelper", context)
        self.assertIn("python watcher.py --wait-alert", context)
        # A compaction keeps the helper's cron job but may lose track of the wait
        compact: dict[str, Any] | None = run_hook(self.project, "compact")
        assert compact is not None
        context = compact["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn("Helper session: myHelper", context)
        self.assertIn("python watcher.py --wait-alert", context)
        self.assertIn("Read board.md:", context)

    def test_derive_helper_name(self) -> None:
        cases: dict[str, str] = {
            "PolymarketHunter": "HaikuPolHun", "polymarket-hunter": "HaikuPolHun",
            "polymarket_hunter": "HaikuPolHun", "PolymarketHunter-reorg": "HaikuPolHun",
            "scraper": "HaikuScrape", "ai-bot": "HaikuAiBot", "XMLParser": "HaikuXmlPar",
            "claude-board": "HaikuClaBoa", "---": "HaikuHelper", "Waeve's_Burgers": "HaikuWaeBur",
        }
        repo: str
        for repo, name in cases.items():
            self.assertEqual(session_start.derive_helper_name(repo), name, repo)
        worktree: Path = Path("x") / "PolymarketHunter" / ".claude" / "worktrees" / "fix-1"
        self.assertEqual(session_start.repo_name(worktree), "PolymarketHunter")

    def test_helper_auto(self) -> None:
        project: Path = self.project / "polymarket-hunter"
        (project / ".claude").mkdir(parents=True)
        (project / ".claude" / "claude-board.json").write_text('{"helper": "auto"}', encoding="utf-8")
        (project / "claude_board.md").write_text(BOARD, encoding="utf-8")
        out: dict[str, Any] | None = run_hook(project)
        assert out is not None
        self.assertIn("/rename HaikuPolHun", out["hookSpecificOutput"]["additionalContext"])

    def test_loose_todos_counted_and_untagged_named(self) -> None:
        board: str = "## Todo\n\n- T1 (Running: Q2): taken up\n3 pull bookies\n- check the log\n  - a sub-point\n"
        self.assertEqual(session_start.count_items(board)["Todo"], 3)
        self.assertEqual(session_start.untagged_todos(board), ["T3", "- check the log"])
        (self.project / "claude_board.md").write_text(board, encoding="utf-8")
        out: dict[str, Any] | None = run_hook(self.project)
        assert out is not None
        self.assertIn("3 todos (untagged: T3, - check the log)", out["hookSpecificOutput"]["additionalContext"])

    def test_rules_copy_written_refreshed_and_hand_written_kept(self) -> None:
        (self.project / "claude_board.md").write_text(BOARD, encoding="utf-8")
        self.write_settings({"helper": "myHelper", "status_file": "log/status.txt", "wait_alert": "w --wait"})
        copy: Path = self.project / "notes" / "board_rules.md"
        out: dict[str, Any] | None = run_hook(self.project)
        assert out is not None
        self.assertIn("Wrote the rules copy", out["hookSpecificOutput"]["additionalContext"])
        text: str = copy.read_text(encoding="utf-8")
        self.assertIn(session_start.GENERATED_MARK, text)
        self.assertIn("Questions for the user go to Asks", text)
        self.assertIn("<repo>/log/status.txt", text)
        self.assertNotIn(str(self.project), text)
        again: dict[str, Any] | None = run_hook(self.project)
        assert again is not None
        self.assertNotIn("rules copy", again["hookSpecificOutput"]["additionalContext"])
        copy.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))  # as git checks it out on Windows
        crlf: dict[str, Any] | None = run_hook(self.project)
        assert crlf is not None
        self.assertNotIn("rules copy", crlf["hookSpecificOutput"]["additionalContext"])
        copy.write_text(text.replace("Asks", "Questions"), encoding="utf-8")
        run_hook(self.project)
        self.assertEqual(copy.read_text(encoding="utf-8"), text)
        copy.write_text("# My own rules\n", encoding="utf-8")
        kept: dict[str, Any] | None = run_hook(self.project)
        assert kept is not None
        self.assertIn("hand-written", kept["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(copy.read_text(encoding="utf-8"), "# My own rules\n")

    def test_rules_copy_turned_off(self) -> None:
        (self.project / "claude_board.md").write_text(BOARD, encoding="utf-8")
        self.write_settings({"rules_copy": ""})
        run_hook(self.project)
        self.assertFalse((self.project / "notes").exists())

    def test_bump_version(self) -> None:
        import bump_version
        text: str = '{\n  "name": "x",\n  "version": "0.1.99",\n  "license": "MIT"\n}\n'
        bumped: str
        version: str
        bumped, version = bump_version.bump(text)
        self.assertEqual(version, "0.1.100")
        self.assertEqual(bumped, text.replace("0.1.99", "0.1.100"))
        with self.assertRaises(ValueError):
            bump_version.bump('{"name": "x"}')

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
