---
name: board
description: Rules of the project's work board (claude_board.md - Todo, Asks, Recommends, Queue; keys like T1, A1, R1, Q1 and their status and category tags). Use before adding, editing, tagging or deleting board items, when working the board's Todos or Queue, and when a question for the user comes up (it goes to Asks, not the console).
---

Read `board_rules.md` in this skill's folder and follow it. The plugin's SessionStart hook already puts the same
rules, the board's item counts and the startup steps into context at the start of a session; this skill is for
looking them up later in a long session.

The project's settings are in `.claude/claude-board.json` (all optional; see the plugin README): `board`,
`template`, `status_file`, `wait_alert`, `helper`, `helper_cron` and `rules_copy` (the generated copy of these
rules in the project, default `notes/board_rules.md`).
