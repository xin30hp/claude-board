# Board rules

Rules of the board (claude-board plugin). The board is one markdown file at the project root (`claude_board.md`
unless `.claude/claude-board.json` names another), tracked in git and committed with the work it records. It holds
the work between the user and Claude and is the running log, so details stay on it.

Startup (every new or cleared session, and when resuming from an idle state, e.g. after a token allowance refresh):
1. Read the board, these rules and the status file (if the settings name one) first, and tell the user the board
   was read (e.g. "Read claude_board.md: 1 todo, 2 asks, ..."). If the board doesn't exist, create it from the
   template (`/claude-board:board-init`).
2. If the settings name a helper session: after ListAgents, send it one message with the full hourly status job
   (below), saying the user requested it (a helper's permission check once blocked a peer-requested CronCreate)
   and that if still blocked it asks its user to approve. If ListAgents shows no such helper, gently ask the user
   to start one.
3. If the settings name a wait-alert command: run it as a background task, and start it again after handling each
   alert.

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
