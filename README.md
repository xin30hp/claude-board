# claude-board

A Claude Code plugin for a work board shared between you and Claude: one markdown file per project
(`claude_board.md`) with four sections.

- Todo (T1, T2, ...): your requests. Write them loosely; Claude tags each one when it takes it up.
- Asks (A1, ...): decisions Claude needs from you. Claude puts its questions here instead of in the console, and
  keeps working on everything they don't block.
- Recommends (R1, ...): work Claude suggests.
- Queue (Q1, ...): work Claude has committed to, in order, with status tags (Running, Waiting on, Blocked by,
  Ready, Done).

The full rules are in `skills/board/board_rules.md`. Each project also gets a copy, `notes/board_rules.md`
(generated, see Settings), so a session on a machine without the plugin can still follow them.

## What the plugin adds

- A session-start hook: in a project with a board, it puts the rules, the board's item counts (untagged Todos
  named) and the startup steps into Claude's context (read the board and status file, tell you what's on it,
  hand the hourly status job to a helper session, start a wait-alert). It runs on every session start: new,
  cleared, resumed, and after a compaction (then only the board read and the wait-alert, since the helper's job
  is unaffected). It also keeps the project's rules copy current. Projects without a board get nothing.
- The `board` skill: the same rules, for Claude to look up mid-session.
- `/claude-board:board-init`: starts a board (and its settings) in the current project.
- An optional watcher skeleton (`templates/board_watcher.py`): a token-free monitor of long runs that wakes
  Claude with alerts; each project copies it and Claude fills in what to watch (see The watcher).

## Install

The hook needs Python 3.8 or later (`python3`, or `python` on Windows).

From a terminal (any shell), with the `claude` command line:

```
claude plugin marketplace add xin30hp/claude-board
claude plugin install claude-board@claude-board
claude plugin list
```

The first command registers this repo as a plugin source, the second installs the plugin for your user (all
projects), and `claude plugin list` should then show `claude-board@claude-board` as enabled. If `claude` isn't on
your PATH, call it by its full path, e.g. on Windows `%USERPROFILE%\.local\bin\claude.exe plugin install ...`.

Or inside a Claude Code session:

```
/plugin marketplace add xin30hp/claude-board
/plugin install claude-board@claude-board
```

Then start a new session (or `/clear`): the plugin's hook runs at session start. To check it works, open a project
that has a `claude_board.md` and ask Claude what the session-start context says; it should begin with
"claude-board plugin (session start: ...)".

To install from a local clone instead, give its path: `claude plugin marketplace add E:/path/to/claude-board`.
To get a newer version later: `claude plugin marketplace update claude-board`, then
`claude plugin update claude-board@claude-board`, then restart Claude Code.

Claude can't install the plugin for you: it changes what every future session loads, so Claude Code asks you to
run the install yourself (or to add a permission rule for `claude plugin` commands).

## Settings

`.claude/claude-board.json` in the project, all keys optional (a project with just `claude_board.md` and no
settings file uses the defaults). A minimal file is in `templates/claude-board.example.json`; the keys below
are all the settings there are:

```
{
  "board": "claude_board.md",
  "template": "notes/my_board_template.md",
  "status_file": "log_files/watcher_status.txt",
  "wait_alert": "python -u -m mypackage.watcher --wait-alert",
  "helper": "myHelper",
  "helper_cron": "7 * * * *",
  "rules_copy": "notes/board_rules.md",
  "watcher": "tools/board_watcher.py"
}
```

- `status_file`: a file the watcher keeps current; read at startup and printed by the hourly status job.
- `watcher`: the project's copy of the plugin's watcher skeleton (see The watcher below). With it set,
  `wait_alert` defaults to `python -u <watcher> --wait-alert`.
- `wait_alert`: a command that exits when something needs Claude; Claude runs it in the background and restarts
  it after each alert. Set it only for a watcher of your own instead of the skeleton. With several sessions open
  on one project, only one should hold the alerts: the command should replace only its own session's older wait
  (or one whose session ended), and when another live session holds them, exit at once saying so; Claude then
  leaves it. The skeleton does this.
- `helper`: another Claude session (e.g. a cheaper model) that prints the board and status file every hour, via
  a cron job Claude asks it to create; `helper_cron` sets the schedule. See The helper session below.
- `rules_copy`: where the hook keeps a copy of the rules, with this project's startup steps filled in (paths under
  `<repo>`, so it is the same on every machine); default `notes/board_rules.md`, `""` turns it off. Commit it,
  and point a fallback at it in CLAUDE.md for machines without the plugin. The hook rewrites it whenever the
  plugin's rules or the settings change; a file there without the "Generated by the claude-board plugin" line is
  yours and is left alone.

Everything beyond the board is optional: with no settings, the board works with Todo, Asks, Recommends and Queue
alone, and Claude checks on long runs itself.

## The watcher (optional)

What it is for: Claude often starts runs that take hours (builds, data pulls, test sweeps). Checking on them by
asking Claude costs tokens each time. The watcher is a small Python script, not Claude, that checks every minute
and costs no tokens: it rewrites a status file you can open in any editor, and appends an ALERT line when
something needs Claude (a watched run finished, stopped or went silent, a new Todo on the board, or a check of
the project's own). Claude keeps one `--wait-alert` running as a background task, which wakes it only on an
alert. With a helper session, the status file also shows on your phone every hour (see The helper session).

### Setting it up (for you, installing)

1. Run `/claude-board:board-init` and say yes to a watcher; or by hand: copy the plugin's
   `templates/board_watcher.py` into the project (e.g. `tools/board_watcher.py`) and add to
   `.claude/claude-board.json`: `"watcher": "tools/board_watcher.py"` and
   `"status_file": "log_files/watcher_status.txt"`.
2. Start a new session (or `/clear`). The session-start hook sees the copy is still the skeleton and asks Claude
   to fill it in for this project; Claude asks you on the board (Asks) about anything it can't decide.
3. Start the watcher's supervisor once, detached, so it outlives Claude sessions (Claude can run this for you):
   Windows (PowerShell): `Start-Process python -WindowStyle Hidden -ArgumentList '-u','tools/board_watcher.py','--supervise'`;
   macOS / Linux: `nohup python3 -u tools/board_watcher.py --supervise >/dev/null 2>&1 &`.
   Nothing restarts the supervisor after a reboot: start it again then.

It needs Python 3.8+ and nothing else. Its files go next to the status file: `watcher_alerts.log` (every alert),
`watcher.log` (its own output) and pid files.

### Filling it in (for Claude, in the project)

The skeleton's generic parts work as they are; three places are marked FILL IN:

- `JOBS`: the long runs to watch, one `Job(name, log, process, done_marker, stall_minutes, board_key)` each. Add
  one when a run starts (its log file, text from its command line, the log text that means done, the board
  item), run `--restart`, and remove it once its alert is handled.
- `project_checks(now, processes)`: anything else that should alert, returning (status lines, alert messages);
  e.g. low disk, a service that should be up, an API key that starts working. Keep each message's wording
  steady: it alerts once, until it stops being raised.
- `SKELETON_UNFILLED`: set it to False once the two above suit the project; until then the hook keeps asking.

Try it with `--once` (one check, printed; nothing written to the alerts log), then `--restart` the supervised
watcher. Alerts go to one live session: a new `--wait-alert` replaces only its own session's older wait (or one
whose session ended) and exits at once, saying so, when another live session holds them; don't restart it then.
`--take` moves the alerts to the current session. If the Queue's work needs more than the watcher gives (or the
project has no watcher and a long run is coming), post an Ask with a recommendation rather than deciding.

## The helper session

A second Claude Code session on the same project folder, on a small model, that takes the hourly status job (and
any simple jobs the main session hands it). Start it by hand:

1. Open the project folder in a new session: the Claude Desktop app's Code tab, or `claude` in a terminal.
2. Switch it to a small model: `/model haiku`.
3. Name it as `helper` says: `/rename myHelper`, so the main session finds it with ListAgents.
4. Approve its first CronCreate when the main session sends it the status job.

It reads and writes `claude_board.md` like any session in the folder. A Desktop app session can be followed from
claude.ai/code or the Claude phone app with Remote Control (`/remote-control` in the session, or Settings > Claude
Code > Connect new sessions to Remote Control; Pro, Max, Team or Enterprise plans), so its hourly prints show the
board away from the computer.

## Developing

`python -m unittest discover tests` and `python -m mypy --strict scripts templates tests`.

Every commit raises the patch version in `.claude-plugin/plugin.json` (0.1.0, 0.1.1, ... 0.1.100), so
`claude plugin update` picks the change up. Enable the hook once per clone: `git config core.hooksPath githooks`.
`CLAUDE_BOARD_NO_BUMP=1 git commit ...` skips it for one commit (e.g. an amend).
