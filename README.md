# claude-board

A Claude Code plugin for a work board shared between you and Claude: one markdown file per project
(`claude_board.md`) with four sections.

- Todo (T1, T2, ...): your requests. Write them loosely; Claude tags each one when it takes it up.
- Asks (A1, ...): decisions Claude needs from you. Claude puts its questions here instead of in the console, and
  keeps working on everything they don't block.
- Recommends (R1, ...): work Claude suggests.
- Queue (Q1, ...): work Claude has committed to, in order, with status tags (Running, Waiting on, Blocked by,
  Ready, Done).

The full rules are in `skills/board/board_rules.md`.

## What the plugin adds

- A session-start hook: in a project with a board, it puts the rules, the board's item counts and the startup
  steps into Claude's context (read the board and status file, tell you what's on it, hand the hourly status job
  to a helper session, start a wait-alert). Projects without a board get nothing.
- The `board` skill: the same rules, for Claude to look up mid-session.
- `/claude-board:board-init`: starts a board (and its settings) in the current project.

## Install

In Claude Code:

```
/plugin marketplace add xin30hp/claude-board
/plugin install claude-board@claude-board
```

For a local clone, use its path instead: `/plugin marketplace add E:/path/to/claude-board`.
The hook needs Python 3.8 or later (`python3`, or `python` on Windows).

## Settings

`.claude/claude-board.json` in the project, all keys optional (a project with just `claude_board.md` and no
settings file uses the defaults):

```
{
  "board": "claude_board.md",
  "template": "notes/my_board_template.md",
  "status_file": "log_files/watcher_status.txt",
  "wait_alert": "python -u -m mypackage.watcher --wait-alert",
  "helper": "myHelper",
  "helper_cron": "7 * * * *"
}
```

- `status_file`: a file some watcher of yours keeps current; read at startup and printed by the hourly status job.
- `wait_alert`: a command that exits when something needs Claude; Claude runs it in the background and restarts
  it after each alert.
- `helper`: another Claude session (e.g. a cheaper model) that prints the board and status file every hour, via
  a cron job Claude asks it to create; `helper_cron` sets the schedule.

A watcher is up to each project; the plugin only reads its status file and runs its wait command.

## Tests

`python -m unittest discover tests`
