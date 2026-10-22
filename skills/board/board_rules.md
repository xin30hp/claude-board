# Board rules

Rules of the board (claude-board plugin). The board is one markdown file at the project root (`claude_board.md`
unless `.claude/claude-board.json` names another), tracked in git and committed with the work it records. It holds
the work between the user and Claude and is the running log, so details stay on it.

Startup (every new, cleared or resumed session, and when resuming from an idle state, e.g. after a token allowance
refresh; after a compaction, steps 1 and 3 only):
1. Read the board, these rules and the status file (if the settings name one) first, and tell the user the board
   was read (e.g. "Read claude_board.md: 1 todo, 2 asks, ..."), naming any untagged Todo (one not taken up yet).
   If the board doesn't exist, create it from the template (`/claude-board:board-init`).
2. If the settings name a helper session: after ListAgents, send it one message with the full hourly status job
   (below), saying the user requested it (a helper's permission check once blocked a peer-requested CronCreate)
   and that if still blocked it asks its user to approve. If ListAgents shows no such helper, gently ask the user
   to start one, and tell them how (Helper session, below).
3. If the settings name a wait-alert command: run it as a background task, and start it again after handling each
   alert. One live session holds the alerts: a new wait replaces only its own session's older one (or one whose
   session has ended), so if it reports that another live session holds them, leave them there and don't restart
   it.

Helper session: a second Claude Code session on the same project folder, on a small model (e.g. Haiku), that
takes the hourly status job and simple jobs the main session hands it. To start one: open the project folder in
a new session (the Claude Desktop app's Code tab, or `claude` in a terminal), switch to a small model
(`/model haiku`), and name it as the settings' `helper` says (`/rename <name>`), so ListAgents finds it; approve
its first CronCreate. It reads and writes the board like any session in that folder. A Desktop app session can
also be followed from claude.ai/code or the Claude phone app with Remote Control (`/remote-control`, or Settings >
Claude Code > Connect new sessions to Remote Control; Pro, Max, Team or Enterprise plans), so its hourly prints
show the board away from the computer.

Watcher (optional): a script, not Claude, that checks the project's long runs every minute at no token cost,
keeps the status file current and appends an ALERT line when something needs Claude; the wait-alert (step 3)
wakes Claude on one. A project gets one by copying the plugin's skeleton (`templates/board_watcher.py`, named by
the settings' `watcher`). While the copy still says SKELETON_UNFILLED = True, Claude fills in its FILL IN parts for
the project (JOBS: the long runs to watch; project_checks: anything else that should alert), posts an Ask for
anything needing the user, sets it False, tries it with --once and starts it detached with --supervise. Claude
adds a Job when a long run starts and removes it once its alert is handled (then --restart). Without a watcher,
Claude checks long runs itself; if the Queue's work needs a watcher or alerts it doesn't have, Claude posts an Ask
[planning] with a recommendation instead of deciding, and keeps working the rest.

The hourly status job (for the helper): on the settings' cron (default "7 * * * *", hourly at :07), prompt exactly
"status update"; each run prints the board, then the status file (absolute paths), each verbatim inside its own
plain code fence (three backticks, no language) so the app shows the raw text instead of rendering markdown, with
no thinking, summary or comment. It runs CronList; if no such job exists it creates one with CronCreate and runs
the status update once right away; it replies whether the job existed or was created. Without a status file, each
run prints the board only.

Working the board:
- Todo items are the user's requests: execute them, and turn anything needing the user into an Ask for the next
  live session.
- Questions for the user go to Asks, never to the console or AskUserQuestion pop-ups, even when the user is live
  and the question blocks a Todo. In the console, only name its key (A1, A2, ...); block only the affected item
  ("Blocked by A1") and keep working the rest of the Queue.
- Lasting decisions go to memory, not the board.

Sections:
- Todo (T): the user's requests, treated as user input. Claude executes them and deletes each one when resolved.
  Taking one up, Claude gives it a status tag like a Queue item's ("- T2 (Running: Q5c): ..."), so an untagged
  Todo is one Claude hasn't seen yet (a project's watcher, if it has one, may alert on it). The user writes Todos
  without tags.
- Asks (A): decisions Claude needs from the user, never asked in the console. They may sit; Claude never acts on a
  default. Deleted once answered.
- Recommends (R): work Claude suggests. Deleted when done, or when the user declines.
- Queue (Q): work Claude has committed to, in order, in the lanes the project's CLAUDE.md defines, if any (e.g.
  machine: one heavy job at a time, in Queue order; code: alongside). Deleted, like a Todo, once done and its
  results recorded (findings, README, the commit); a top-level item never carries a Done tag. A Done sub-item
  stays only while its parent is open, as the record its siblings build on, and goes with it.

Format (for what Claude writes; the user's text may be loose):
- One item per line, keyed T1, A1, R1, Q1; items refer to each other by key. Split a long item into sub-bullets
  keyed Q2a, Q2b, ...
- Claude may rewrite a loosely keyed Todo (e.g. "2 do X", "#2", none at all) to the strict form ("- T2: do X",
  sub-items T2a, T2b, ...) so keys stay unambiguous; the user's wording is kept as is.
- Each Queue item starts with a status tag after its key: (Running: <what>), (Waiting on Q2b) or (Waiting on
  <process>), (Blocked by A1), (Ready), and (Done: <commit>) on sub-items only, then its lane. A parent takes its
  most urgent child's tag.
- Each Ask starts with a category tag after its key: [money] (stakes, live trading, tuned settings, accounts),
  [claude.md] (edits to CLAUDE.md), [planning] (Queue order, lanes, time vs accuracy), [code] (structure, naming),
  [misc]. List Asks in that order, so the ones that matter most come first.
- With lanes, the Queue opens with a Lanes summary, one short line per lane: the running item (with its finish
  time if known), then the next ones in order. Status only; the details are in the ordered list.
- Mark an item Running only once it has really started, and update the tags and the Lanes summary whenever an
  item starts, finishes or gets blocked.
- After a large Queue job, hand off before going on (the project's CLAUDE.md, if it says how).
