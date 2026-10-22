"""Board watcher: a token-free monitor of this project's long runs, from the claude-board plugin's skeleton.

A script, not Claude, checks every CHECK_SECONDS: it rewrites the status file (open it in an editor, or let the
helper session print it hourly) and appends an ALERT line to the alerts log when something needs Claude's
judgment: a watched run finishing, stopping or going silent, an untagged Todo on the board, or a check of the
project's own. Claude waits on `--wait-alert` as a background task, which costs no tokens until it exits.

Copied into the project by /claude-board:board-init. The parts marked FILL IN (SKELETON_UNFILLED, JOBS,
project_checks) are this project's to write; the rest is generic. Standard library only, Python 3.8+.

    python -u <this file>                 run the watcher in the foreground
    python -u <this file> --supervise     run it, restarting it whenever it stops; start this one detached:
                                          Windows (PowerShell): Start-Process python -WindowStyle Hidden
                                              -ArgumentList '-u','<this file>','--supervise'
                                          macOS / Linux: nohup python3 -u <this file> --supervise >/dev/null 2>&1 &
    python -u <this file> --restart       restart the supervised watcher, e.g. after editing JOBS
    python -u <this file> --wait-alert    Claude's background wait: exits on the next alert, or when the status
                                          file is stale (watcher down); --take moves the alerts to this session
    python -u <this file> --once          one check, then print the status (to try out the filled-in parts)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# FILL IN: set to False once JOBS and project_checks below are written for this project. While it is True, the
# plugin's session-start hook asks Claude to fill them in, and the status file says the watcher is a skeleton.
SKELETON_UNFILLED: bool = True

SETTINGS_NAME: str = ".claude/claude-board.json"
CHECK_SECONDS: int = 60
STALE_MINUTES: float = 5.0  # a status file this old means the watcher is down
ALERT_HOURS: float = 3.0  # alerts this recent are shown in the status file
RESTART_SECONDS: int = 10  # pause before restarting a watcher that ran a while
CRASH_PAUSE_SECONDS: int = 60  # pause after one that died within a minute, so a crash loop stays slow


@dataclass(frozen=True)
class Job:
    """A long run to watch.

    Attributes:
        name: Heading in the status file.
        log: Its log file, relative to the project root.
        process: Text found in its command line while it runs.
        done_marker: Log text meaning it finished; "" when the process ending is the finish.
        stall_minutes: Alert when the log hasn't changed for this long while it runs.
        board_key: Its board item (e.g. "Q3"), shown in its heading and alerts; "" for none.
    """

    name: str
    log: str
    process: str
    done_marker: str = ""
    stall_minutes: float = 30.0
    board_key: str = ""

    @property
    def heading(self) -> str:
        """The name, prefixed with its board key when it has one, e.g. "[Q3] NIGHTLY BUILD"."""
        return f"[{self.board_key}] {self.name}" if self.board_key else self.name


@dataclass(frozen=True)
class Proc:
    """A running process: id, parent id, program name (e.g. "python.exe") and full command line."""

    pid: int
    parent: int
    name: str
    command: str


# FILL IN: this project's long runs, e.g.
#   Job("NIGHTLY BUILD", "logs/build.log", "make all", done_marker="BUILD DONE", stall_minutes=20, board_key="Q2")
# Claude adds one when a long run starts and removes it once its alert is handled, then runs --restart.
JOBS: list[Job] = []


def project_checks(now: datetime, processes: list[Proc]) -> tuple[list[str], list[str]]:
    """FILL IN: this project's own checks beyond JOBS, e.g. low disk, a service that should be up, a daily file.

    Args:
        now: The check's time.
        processes: Every running process.

    Returns:
        (status lines, alert messages). A message raised at every check alerts once, until it stops being raised;
        keep its wording steady (numbers in it may change).
    """
    return [], []


def find_root(start: Path) -> Path:
    """The project root: the nearest folder at or above `start` with the board settings or the board."""
    folder: Path
    for folder in (start, *start.parents):
        if (folder / SETTINGS_NAME).is_file() or (folder / "claude_board.md").is_file():
            return folder
    return Path.cwd()


def load_settings(root: Path) -> dict[str, Any]:
    """The project's board settings; {} if missing or unreadable."""
    path: Path = root / SETTINGS_NAME
    try:
        loaded: Any = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


ROOT: Path = find_root(Path(__file__).resolve().parent)
SETTINGS: dict[str, Any] = load_settings(ROOT)
BOARD_PATH: Path = ROOT / str(SETTINGS.get("board", "claude_board.md"))
STATUS_PATH: Path = ROOT / str(SETTINGS.get("status_file", "log_files/watcher_status.txt"))
ALERTS_PATH: Path = STATUS_PATH.with_name("watcher_alerts.log")  # one line per alert, appended
LOG_PATH: Path = STATUS_PATH.with_name("watcher.log")  # the supervisor's and the watcher's output
PID_PATH: Path = STATUS_PATH.with_name("watcher.pid")
SUPERVISOR_PID_PATH: Path = STATUS_PATH.with_name("watcher_supervisor.pid")
RESTART_MARKER: Path = STATUS_PATH.with_name("watcher.restart")  # --restart's request, so it isn't a crash
SCRIPT_NAME: str = Path(__file__).name
TAGGED_TODO: re.Pattern[str] = re.compile(r"-\s*T\d+[a-z]?\s*\([^)]*\):")


def read(path: Path) -> str:
    """A text file's contents, or "" if it can't be read."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def parse_ps(text: str) -> list[Proc]:
    """Processes from `ps -axww -o pid=,ppid=,comm=,args=` output (macOS, Linux)."""
    found: list[Proc] = []
    line: str
    for line in text.splitlines():
        match: re.Match[str] | None = re.match(r"^\s*(\d+)\s+(\d+)\s+(\S+)\s*(.*)$", line)
        if match:
            found.append(Proc(int(match[1]), int(match[2]), Path(match[3]).name, match[4]))
    return found


def parse_cim(text: str) -> list[Proc]:
    """Processes from Windows' Win32_Process as JSON (ProcessId, ParentProcessId, Name, CommandLine)."""
    try:
        rows: Any = json.loads(text) if text.strip() else []
    except ValueError:
        return []
    rows = rows if isinstance(rows, list) else [rows]
    return [Proc(int(r["ProcessId"]), int(r["ParentProcessId"]), str(r.get("Name") or ""),
                 str(r.get("CommandLine") or "")) for r in rows
            if isinstance(r, dict) and isinstance(r.get("ProcessId"), int) and isinstance(r.get("ParentProcessId"), int)]


def list_processes() -> list[Proc]:
    """Every running process; empty if they can't be read."""
    command: list[str] = (
        ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_Process | Select-Object ProcessId, "
         "ParentProcessId, Name, CommandLine | ConvertTo-Json -Compress"]
        if sys.platform == "win32" else ["ps", "-axww", "-o", "pid=,ppid=,comm=,args="]
    )
    try:
        out: str = subprocess.run(command, capture_output=True, text=True, errors="replace").stdout
    except OSError:
        return []
    return parse_cim(out) if sys.platform == "win32" else parse_ps(out)


def stop_process(pid: int) -> None:
    """Force-stop a process; one that already ended is fine."""
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass  # already gone, or not ours to stop


def live_pid(path: Path, processes: list[Proc]) -> int | None:
    """The process id in a pid file, if that process still runs this script; None otherwise."""
    text: str = read(path).strip()
    if not text.isdigit():
        return None
    return int(text) if any(p.pid == int(text) and SCRIPT_NAME in p.command for p in processes) else None


def session_of(pid: int, processes: list[Proc]) -> int | None:
    """The Claude session a process belongs to: its nearest claude ancestor (each session runs its own claude).

    Returns:
        The session's claude process id, or None if no live claude process is among its ancestors.
    """
    by_pid: dict[int, Proc] = {p.pid: p for p in processes}
    seen: set[int] = set()
    current: Proc | None = by_pid.get(pid)
    while current is not None and current.pid not in seen:
        seen.add(current.pid)
        current = by_pid.get(current.parent)
        if current is not None and Path(current.name).stem.lower() == "claude":
            return current.pid
    return None


def other_waits(processes: list[Proc], own_pid: int) -> list[int]:
    """The `--wait-alert` runs of this script other than this one."""
    return [p.pid for p in processes
            if p.pid != own_pid and SCRIPT_NAME in p.command and "--wait-alert" in p.command]


def todo_items(board: str) -> dict[str, str]:
    """The Todo section's items by key ("T3"), from lines at column 0 that start with a dash or a number.

    Loose on purpose: a Todo typed quickly ("3 pull data", "- check the log") counts. A numbered item is keyed
    "T<n>", an unnumbered one by its text; indented sub-points don't count. Same as the plugin's hook.
    """
    items: dict[str, str] = {}
    section: str = ""
    line: str
    for line in board.splitlines():
        if line.startswith("## "):
            section = line[3:].strip().lower()
        elif section == "todo" and re.match(r"[-\d]", line):
            number: re.Match[str] | None = re.match(r"-?\s*T?(\d+)\b", line.strip(), re.IGNORECASE)
            items[f"T{number.group(1)}" if number else line.strip()] = line.strip()
    return items


def untagged_todos(board: str) -> list[str]:
    """Todos Claude hasn't taken up yet: those without a status tag after their key."""
    return [key for key, line in todo_items(board).items() if not TAGGED_TODO.match(line)]


def board_summary(board: str) -> str:
    """One line counting the board's open items, e.g. "BOARD (claude_board.md): 1 todo, 0 asks, 2 recommends, 3 queued"."""
    counts: dict[str, int] = {"todo": len(todo_items(board)), "asks": 0, "recommends": 0, "queue": 0}
    letters: dict[str, str] = {"asks": "A", "recommends": "R", "queue": "Q"}
    section: str = ""
    line: str
    for line in board.splitlines():
        if line.startswith("## "):
            section = line[3:].strip().lower()
        elif section in letters and re.match(rf"^- {letters[section]}\d+", line):
            counts[section] += 1
    words: list[str] = [f"{counts['todo']} todo{'' if counts['todo'] == 1 else 's'}",
                        f"{counts['asks']} ask{'' if counts['asks'] == 1 else 's'}",
                        f"{counts['recommends']} recommend{'' if counts['recommends'] == 1 else 's'}",
                        f"{counts['queue']} queued"]
    return f"BOARD ({BOARD_PATH.name}): " + ", ".join(words)


def job_report(job: Job, now: datetime, processes: list[Proc]) -> tuple[list[str], str | None]:
    """A job's status lines, and its alert message if it needs Claude (None otherwise)."""
    log: Path = ROOT / job.log
    text: str = read(log)
    running: bool = any(job.process in p.command for p in processes if SCRIPT_NAME not in p.command)
    minutes: float | None = (now.timestamp() - log.stat().st_mtime) / 60 if log.exists() else None
    last: str = next((line.strip() for line in reversed(text.splitlines()) if line.strip()), "(empty log)")
    alert: str | None = None
    if job.done_marker and job.done_marker in text:
        state: str = "finished"
        alert = f"{job.heading} finished"
    elif not running:
        state = "not running"
        alert = f"{job.heading} stopped without its done marker" if job.done_marker else f"{job.heading} ended"
    else:
        state = "running"
        if minutes is not None and minutes > job.stall_minutes:
            alert = f"{job.heading} log silent for {minutes:.0f} min"
    age: str = f"{minutes:.0f} min ago" if minutes is not None else "no log yet"
    return [job.heading, f"  {state}, log updated {age}", f"  last: {last[:110]}", ""], alert


def alert_key(message: str) -> str:
    """A message with its numbers blanked, so "silent for 31 min" and "silent for 32 min" are one alert."""
    return re.sub(r"\d+", "#", message)


def recent_alerts(now: datetime) -> list[str]:
    """The status file's ALERTS section: alert lines from the last ALERT_HOURS."""
    since: str = f"{now - timedelta(hours=ALERT_HOURS):%Y-%m-%d %H:%M}"
    lines: list[str] = [line for line in read(ALERTS_PATH).splitlines() if line[:16] >= since]
    return [f"ALERTS (last {ALERT_HOURS:.0f} h, from {ALERTS_PATH.name})", *(f"  {line}" for line in lines[-5:]),
            ""] if lines else []


def check(now: datetime, active: set[str], record: bool = True) -> tuple[list[str], list[str], set[str]]:
    """One round of checks.

    Args:
        now: The check's time.
        active: Alert keys raised last round (each alerts once, until it clears).
        record: Append new alerts to the alerts log; False for a trial (--once), which would otherwise wake Claude.

    Returns:
        (status file lines, new alert messages, alert keys raised this round).
    """
    processes: list[Proc] = list_processes()
    report: list[str] = [f"Status at {now:%a %H:%M} (updated every {CHECK_SECONDS} s)", ""]
    if SKELETON_UNFILLED:
        report += ["SKELETON: this watcher's FILL IN parts (JOBS, project_checks) aren't written yet", ""]
    raised: list[str] = []
    job: Job
    for job in JOBS:
        lines: list[str]
        alert: str | None
        lines, alert = job_report(job, now, processes)
        report += lines
        if alert:
            raised.append(alert + " (remove it from JOBS once handled)")
    if not JOBS:
        report += ["No runs watched (JOBS is empty).", ""]
    extra: list[str]
    alerts: list[str]
    extra, alerts = project_checks(now, processes)
    report += extra + ([""] if extra else [])
    raised += alerts
    board: str = read(BOARD_PATH)
    untagged: list[str] = untagged_todos(board)
    if untagged:
        raised.append("untagged Todo on the board: " + "; ".join(untagged))
    report += [board_summary(board), ""]
    keys: set[str] = {alert_key(m) for m in raised}
    new: list[str] = [m for m in raised if alert_key(m) not in active]
    if new and record:
        with open(ALERTS_PATH, "a", encoding="utf-8") as log:
            log.write("".join(f"{now:%Y-%m-%d %H:%M} ALERT {m}\n" for m in new))
    report += recent_alerts(now)
    return report, new, keys


def run() -> None:
    """Check every CHECK_SECONDS, rewriting the status file; never returns on its own."""
    other: int | None = live_pid(PID_PATH, list_processes())
    if other is not None and other != os.getpid():
        print(f"another watcher is running (pid {other}); not starting a second one", flush=True)
        return
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
    active: set[str] = set()
    while True:
        report: list[str]
        report, _, active = check(datetime.now(), active)
        STATUS_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")
        time.sleep(CHECK_SECONDS)


def supervise() -> None:
    """Run the watcher and restart it whenever it exits; runs until stopped. Start it detached (see the top)."""
    other: int | None = live_pid(SUPERVISOR_PID_PATH, list_processes())
    if other is not None and other != os.getpid():
        print(f"a supervisor is already running (pid {other})", flush=True)
        return
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUPERVISOR_PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
    with open(LOG_PATH, "a", encoding="utf-8") as log:
        while True:
            started: float = time.monotonic()
            code: int = subprocess.run([sys.executable, "-u", str(Path(__file__).resolve())], cwd=ROOT,
                                       stdout=log, stderr=subprocess.STDOUT).returncode
            minutes: float = (time.monotonic() - started) / 60
            requested: bool = RESTART_MARKER.exists()
            RESTART_MARKER.unlink(missing_ok=True)
            pause: int = RESTART_SECONDS if requested or minutes >= 1 else CRASH_PAUSE_SECONDS
            what: str = f"watcher exited (code {code}) after {minutes:.0f} min; restarting in {pause} s"
            stamp: str = f"{datetime.now():%Y-%m-%d %H:%M}"
            log.write(f"[supervisor] {stamp} {what}{' (on request)' if requested else ''}\n")
            log.flush()
            if not requested:
                with open(ALERTS_PATH, "a", encoding="utf-8") as alerts:
                    alerts.write(f"{stamp} ALERT {what}\n")
            time.sleep(pause)


def restart() -> None:
    """Restart the supervised watcher (e.g. after editing JOBS): stop it, and the supervisor starts a fresh one."""
    processes: list[Proc] = list_processes()
    if live_pid(SUPERVISOR_PID_PATH, processes) is None:
        print("no supervisor is running; start one detached with --supervise", flush=True)
        return
    watcher: int | None = live_pid(PID_PATH, processes)
    if watcher is None:
        print("no watcher is running; the supervisor starts one shortly", flush=True)
        return
    RESTART_MARKER.write_text("", encoding="utf-8")
    stop_process(watcher)
    print(f"stopped watcher {watcher}; the supervisor restarts it in {RESTART_SECONDS} s", flush=True)


def new_alert_lines(offset: int) -> tuple[list[str], int]:
    """Alert lines appended since a byte offset, and the log's size now (a log that shrank is read from the start)."""
    size: int = ALERTS_PATH.stat().st_size if ALERTS_PATH.exists() else 0
    if size == offset:
        return [], size
    with open(ALERTS_PATH, "rb") as alerts:
        alerts.seek(offset if size > offset else 0)
        text: str = alerts.read().decode("utf-8", errors="replace")
    return [line for line in text.splitlines() if line.strip()], size


def wait_alert(take: bool = False, poll_seconds: float = 5.0) -> None:
    """Claude's background wait: return on the next alert, or when the status file goes stale (watcher down).

    One live session holds the alerts. Stops this session's older waits (a /clear leaves one behind) and those
    whose session ended; when another live session already waits, returns at once and says so.

    Args:
        take: Also stop other live sessions' waits, moving the alerts to this session.
        poll_seconds: Seconds between checks.
    """
    processes: list[Proc] = list_processes()
    own: int | None = session_of(os.getpid(), processes)
    held: list[tuple[int, int]] = []  # (wait pid, its session's claude pid)
    pid: int
    for pid in other_waits(processes, os.getpid()):
        owner: int | None = session_of(pid, processes)
        if take or owner is None or owner == own:
            stop_process(pid)
            print(f"stopped an older --wait-alert (pid {pid})", flush=True)
        else:
            held.append((pid, owner))
    if held:
        print(f"another live session (claude pid {held[0][1]}) holds the alerts (--wait-alert pid {held[0][0]}); "
              "this session leaves them there: don't restart this wait (--take moves them here)", flush=True)
        return
    offset: int = ALERTS_PATH.stat().st_size if ALERTS_PATH.exists() else 0
    while True:
        lines: list[str]
        lines, offset = new_alert_lines(offset)
        if lines:
            print("\n".join(lines), flush=True)
            return
        age: float = (time.time() - STATUS_PATH.stat().st_mtime) / 60 if STATUS_PATH.exists() else STALE_MINUTES + 1
        if age > STALE_MINUTES:
            print(f"{datetime.now():%Y-%m-%d %H:%M} ALERT status file not updated for {age:.0f} min: watcher down "
                  "(start it detached with --supervise)", flush=True)
            return
        time.sleep(poll_seconds)


def main() -> int:
    """Parse the command line and run the chosen mode."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description="Token-free monitor of this project's long runs.")
    mode: argparse._MutuallyExclusiveGroup = parser.add_mutually_exclusive_group()
    mode.add_argument("--supervise", action="store_true", help="run the watcher, restarting it whenever it stops")
    mode.add_argument("--restart", action="store_true", help="restart the supervised watcher, e.g. after editing JOBS")
    mode.add_argument("--wait-alert", action="store_true", help="wait for the next alert or a stale status file")
    mode.add_argument("--once", action="store_true", help="one check, then print the status")
    parser.add_argument("--take", action="store_true", help="with --wait-alert: take the alerts from another session")
    args: argparse.Namespace = parser.parse_args()
    if args.supervise:
        supervise()
    elif args.restart:
        restart()
    elif args.wait_alert:
        wait_alert(take=args.take)
    elif args.once:
        STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        report: list[str]
        new: list[str]
        report, new, _ = check(datetime.now(), set(), record=False)
        print("\n".join(report + [f"would alert: {m}" for m in new]))
    else:
        run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
