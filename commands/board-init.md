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
   - `helper`: the name of a helper Claude session (as ListAgents shows it) that runs the hourly status job;
     suggest `"auto"` (named from the repo, e.g. PolymarketHunter -> HaikuPolHun; the README's Settings)
   - `helper_cron`: that job's schedule (default `7 * * * *`)
   - `rules_copy`: where to keep the generated copy of the rules (default `notes/board_rules.md`; `""` for none)
   - `watcher`: a token-free monitor of long runs that wakes Claude with alerts (suggest `tools/board_watcher.py`,
     with `status_file` `log_files/watcher_status.txt`); worth it when the project has runs of 10+ minutes
   - `offload_paths`: path fragments of the project's bulky data (e.g. `["data/", "logs/", ".sqlite", ".csv"]`);
     with a `helper`, a hook reminds Claude to hand reads of them to the helper (needs `helper`)
   Ask the user which apply, in one question with these choices (several allowed), a line each:
   - Helper: a second Claude session on a small model that prints the board hourly and takes simple jobs.
   - Offload hooks (with a helper): a reminder before Claude reads bulky data (logs, data files) to hand the
     read to the helper, so the results don't fill the main session's context.
   - Watcher: a token-free script that checks long runs every minute and wakes Claude when one needs it.
   - Neither: just the board.
   With no answer, write `{}`. Offload hooks without a helper: set `"helper": "auto"` too, saying so.
   If they chose offload hooks: look at the project's folders for bulky data (data, logs, caches, exports) and
   propose `offload_paths` from them for the user to confirm; leave out the status file (the hook skips it
   anyway).
   If they chose a watcher: copy `${CLAUDE_PLUGIN_ROOT}/templates/board_watcher.py` to the `watcher` path, fill in
   its FILL IN parts for this project (the plugin README's "Filling it in"), set SKELETON_UNFILLED = False, try
   `--once`, and start it detached with `--supervise` (commands in its docstring).
4. Write the rules copy: from the project root, run `python "${CLAUDE_PLUGIN_ROOT}/scripts/session_start.py"
   --rules-copy` (`python3` on macOS and Linux). Suggest a line in the project's CLAUDE.md for machines without
   the plugin: "Without the claude-board plugin, follow notes/board_rules.md (its startup section)."
5. Tell the user the board is ready, and that they add Todos to it. If `helper` is set, tell them how to start
   it (the plugin README's "The helper session", or the rules' Helper session paragraph): a new Claude Code
   session on this folder (the Desktop app's Code tab, or `claude` in a terminal), `/model haiku`,
   `/rename <helper>`, then approve its first CronCreate; it reads and writes claude_board.md like any session
   here, and with Remote Control (`/remote-control`) the user can follow its hourly prints from claude.ai/code or
   the phone app. If `offload_paths` is set, tell them how the offload hooks work (the plugin README's
   "Offloading to the helper"): they start with the next session (or `/clear`); before Claude reads a listed
   path it gets a reminder to hand the read to the helper when that is live and the result doesn't decide its
   next step; nothing is ever blocked; to change what counts, edit `offload_paths` in .claude/claude-board.json;
   to turn it off, remove the key. Suggest they say in CLAUDE.md which other jobs go to the helper (status
   checks, searches, mechanical edits from an exact spec) and which stay in the main session (design,
   decisions, anything touching money or credentials).

$ARGUMENTS
