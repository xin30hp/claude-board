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
   - `rules_copy`: where to keep the generated copy of the rules (default `notes/board_rules.md`; `""` for none)
   Ask the user which apply, in one question; with no answer, write `{}`.
4. Write the rules copy: from the project root, run `python "${CLAUDE_PLUGIN_ROOT}/scripts/session_start.py"
   --rules-copy` (`python3` on macOS and Linux). Suggest a line in the project's CLAUDE.md for machines without
   the plugin: "Without the claude-board plugin, follow notes/board_rules.md (its startup section)."
5. Tell the user the board is ready, and that they add Todos to it. If `helper` is set, tell them how to start
   it (the plugin README's "The helper session", or the rules' Helper session paragraph): a new Claude Code
   session on this folder (the Desktop app's Code tab, or `claude` in a terminal), `/model haiku`,
   `/rename <helper>`, then approve its first CronCreate; it reads and writes claude_board.md like any session
   here, and with Remote Control (`/remote-control`) the user can follow its hourly prints from claude.ai/code or
   the phone app.

$ARGUMENTS
