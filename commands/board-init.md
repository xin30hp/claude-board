---
description: Start a work board in this project (claude_board.md and its settings)
---

Set up the claude-board work board in the current project:

1. If `claude_board.md` (or the board `.claude/claude-board.json` names) already exists, say so and stop.
2. Copy the plugin's template, `${CLAUDE_PLUGIN_ROOT}/templates/claude_board.example.md`, to `claude_board.md` at
   the project root, with the example items removed (keep the headings, the Lanes lines only if the project
   uses lanes).
3. Create `.claude/claude-board.json` if missing. Its keys are all optional; include only those that apply:
   - `board`: the board's path (default `claude_board.md`)
   - `template`: a project-specific template for a new board
   - `status_file`: a status file read at startup and printed by the helper's hourly status job
   - `wait_alert`: a command Claude keeps running as a background task to be woken by alerts
   - `helper`: the name of a helper Claude session (as ListAgents shows it) that runs the hourly status job
   - `helper_cron`: that job's schedule (default `7 * * * *`)
   Ask the user which apply, in one question; with no answer, write `{}`.
4. Tell the user the board is ready, and that they add Todos to it.

$ARGUMENTS
