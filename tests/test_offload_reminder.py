"""Tests of the offload reminder hook (scripts/offload_reminder.py)."""

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
SCRIPT: Path = ROOT / "scripts" / "offload_reminder.py"
sys.path.insert(0, str(ROOT / "scripts"))

from offload_reminder import offload_hint  # noqa: E402

SETTINGS: dict[str, Any] = {
    "helper": "HaikuWaeBur", "status_file": "logs/status.txt", "offload_paths": ["data/", "logs/", ".sqlite"],
}


class OffloadReminderTest(unittest.TestCase):
    def test_hint_on_bulky_reads_only(self) -> None:
        self.assertIn("HaikuWaeBur", offload_hint(SETTINGS, {"file_path": "C:\\repo\\data\\big.csv"}) or "")
        self.assertIsNotNone(offload_hint(SETTINGS, {"command": "sqlite3 cache.SQLITE 'select 1'"}))
        self.assertIsNone(offload_hint(SETTINGS, {"file_path": "src/main.py"}))
        # The status file is the main session's own read, and a job launch writing its log reads nothing
        self.assertIsNone(offload_hint(SETTINGS, {"file_path": "/repo/logs/status.txt"}))
        self.assertIsNone(offload_hint(SETTINGS, {"command": "python run.py > logs/run.log 2>&1"}))

    def test_off_without_helper_or_paths(self) -> None:
        self.assertIsNone(offload_hint({"offload_paths": ["data/"]}, {"file_path": "data/x"}))
        self.assertIsNone(offload_hint({"helper": "h"}, {"file_path": "data/x"}))

    def test_hook_resolves_auto_helper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project: Path = Path(tmp) / "waeves-burgers"
            (project / ".claude").mkdir(parents=True)
            (project / ".claude" / "claude-board.json").write_text(
                json.dumps({"helper": "auto", "offload_paths": ["data/"]}), encoding="utf-8")
            env: dict[str, str] = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
            event: dict[str, Any] = {"cwd": str(project), "tool_name": "Read", "tool_input": {"file_path": "data/a"}}
            done: subprocess.CompletedProcess[str] = subprocess.run(
                [sys.executable, str(SCRIPT)], input=json.dumps(event), capture_output=True, text=True, env=env,
                check=True)
            out: dict[str, Any] = json.loads(done.stdout)
            self.assertIn("HaikuWaeBur", out["hookSpecificOutput"]["additionalContext"])
            quiet: subprocess.CompletedProcess[str] = subprocess.run(
                [sys.executable, str(SCRIPT)], input=json.dumps({"cwd": tmp, "tool_input": {"file_path": "data/a"}}),
                capture_output=True, text=True, env=env, check=True)
            self.assertEqual(quiet.stdout, "")


if __name__ == "__main__":
    unittest.main()
