"""Tests of the watcher skeleton (templates/board_watcher.py) and of the hook's steps for it."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT: Path = Path(__file__).resolve().parent.parent
SKELETON: Path = ROOT / "templates" / "board_watcher.py"
sys.path.insert(0, str(ROOT / "templates"))
sys.path.insert(0, str(ROOT / "scripts"))

import board_watcher  # noqa: E402
import session_start  # noqa: E402
from board_watcher import Job, Proc  # noqa: E402


class SkeletonTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.project: Path = Path(self.tmp.name)
        self.saved_root: Path = board_watcher.ROOT
        board_watcher.ROOT = self.project

    def tearDown(self) -> None:
        board_watcher.ROOT = self.saved_root
        self.tmp.cleanup()

    def test_session_of_nearest_claude_ancestor(self) -> None:
        processes: list[Proc] = [
            Proc(1, 0, "claude.exe", "app"), Proc(2, 1, "claude.exe", "session"), Proc(3, 2, "bash.exe", "bash"),
            Proc(4, 3, "python.exe", "python w.py --wait-alert"), Proc(7, 8, "python.exe", "orphan"),
        ]
        self.assertEqual(board_watcher.session_of(4, processes), 2)
        self.assertIsNone(board_watcher.session_of(7, processes))

    def test_other_waits_only_this_scripts_waits(self) -> None:
        name: str = board_watcher.SCRIPT_NAME
        processes: list[Proc] = [
            Proc(10, 1, "python", f"python -u {name} --wait-alert"), Proc(11, 1, "python", f"python {name} --wait-alert"),
            Proc(12, 1, "python", f"python {name} --supervise"), Proc(13, 1, "python", "python other.py --wait-alert"),
        ]
        self.assertEqual(board_watcher.other_waits(processes, 11), [10])

    def test_parsers(self) -> None:
        ps: list[Proc] = board_watcher.parse_ps("  12     1 /usr/bin/python3 python3 -u w.py --once\n")
        self.assertEqual(ps, [Proc(12, 1, "python3", "python3 -u w.py --once")])
        cim: list[Proc] = board_watcher.parse_cim(json.dumps(
            [{"ProcessId": 5, "ParentProcessId": 4, "Name": "claude.exe", "CommandLine": None}]))
        self.assertEqual(cim, [Proc(5, 4, "claude.exe", "")])
        self.assertEqual(board_watcher.parse_cim("not json"), [])

    def test_todo_parsing_matches_the_hook(self) -> None:
        board: str = "## Todo\n\n- T1 (Running: Q2): taken\n3 pull data\n- check the log\n## Asks\n- A1 [misc]: x\n"
        self.assertEqual(board_watcher.todo_items(board), session_start.todo_items(board))
        self.assertEqual(board_watcher.untagged_todos(board), session_start.untagged_todos(board))
        self.assertIn("3 todos, 1 ask, 0 recommends, 0 queued", board_watcher.board_summary(board))

    def test_job_report_states(self) -> None:
        log: Path = self.project / "run.log"
        log.write_text("step 1\nALL DONE\n", encoding="utf-8")
        job: Job = Job("BUILD", "run.log", "make all", done_marker="ALL DONE", stall_minutes=5, board_key="Q2")
        running: list[Proc] = [Proc(9, 1, "make", "make all -j4")]
        alert: str | None
        _, alert = board_watcher.job_report(job, datetime.now(), running)
        self.assertEqual(alert, "[Q2] BUILD finished")
        log.write_text("step 1\n", encoding="utf-8")
        _, alert = board_watcher.job_report(job, datetime.now(), [])
        self.assertEqual(alert, "[Q2] BUILD stopped without its done marker")
        _, alert = board_watcher.job_report(job, datetime.now(), running)
        self.assertIsNone(alert)
        old: float = time.time() - 600
        os.utime(log, (old, old))
        _, alert = board_watcher.job_report(job, datetime.now(), running)
        self.assertEqual(alert, "[Q2] BUILD log silent for 10 min")
        assert alert is not None
        self.assertEqual(board_watcher.alert_key(alert), board_watcher.alert_key("[Q2] BUILD log silent for 11 min"))

    def test_once_in_a_project_copy(self) -> None:
        tools: Path = self.project / "tools"
        tools.mkdir()
        shutil.copy(SKELETON, tools / "board_watcher.py")
        (self.project / ".claude").mkdir()
        (self.project / ".claude" / "claude-board.json").write_text(
            json.dumps({"watcher": "tools/board_watcher.py", "status_file": "logs/status.txt"}), encoding="utf-8")
        (self.project / "claude_board.md").write_text("## Todo\n\n- fix the build\n", encoding="utf-8")
        done: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, str(tools / "board_watcher.py"), "--once"], capture_output=True, text=True,
            cwd=tempfile.gettempdir(), check=True)
        self.assertIn("SKELETON", done.stdout)
        self.assertIn("No runs watched", done.stdout)
        self.assertIn("would alert: untagged Todo on the board: - fix the build", done.stdout)
        self.assertFalse((self.project / "logs" / "watcher_alerts.log").exists())


class HookWatcherTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.project: Path = Path(self.tmp.name)
        (self.project / "claude_board.md").write_text("## Todo\n", encoding="utf-8")
        self.settings: dict[str, Any] = {"watcher": "tools/board_watcher.py", "rules_copy": ""}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def context(self) -> str:
        return session_start.build_context(self.project, self.settings, "startup")

    def test_missing_unfilled_ready(self) -> None:
        context: str = self.context()
        self.assertIn("doesn't exist yet: copy the plugin's skeleton", context)
        self.assertNotIn("Start the wait-alert", context)
        copy: Path = self.project / "tools" / "board_watcher.py"
        copy.parent.mkdir()
        shutil.copy(SKELETON, copy)
        context = self.context()
        self.assertIn("is still the plugin's skeleton", context)
        self.assertIn("python -u tools/board_watcher.py --wait-alert", context)
        copy.write_text(copy.read_text(encoding="utf-8").replace(
            "SKELETON_UNFILLED: bool = True", "SKELETON_UNFILLED: bool = False"), encoding="utf-8")
        context = self.context()
        self.assertNotIn("skeleton (SKELETON_UNFILLED = True)", context)
        self.assertIn("Start the wait-alert as a background task: python -u tools/board_watcher.py", context)

    def test_wait_alert_setting_wins(self) -> None:
        self.settings["wait_alert"] = "python mine.py --wait"
        self.assertEqual(session_start.wait_alert_command(self.settings), "python mine.py --wait")
        self.assertIsNone(session_start.wait_alert_command({}))


if __name__ == "__main__":
    unittest.main()
