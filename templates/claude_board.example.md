# Claude board

Work between the user and Claude. The user adds Todos (no tags needed); Claude keeps the rest.
Rules: the claude-board plugin's board skill (keys, status and category tags, lanes).

## Todo

- T1: Example: re-run the benchmark on the new data and report the mean.

## Asks

- A1 [planning]: Example: run the slow full benchmark now, or the quick sample first?

## Recommends

- R1: Example: cache the downloaded data, so reruns don't fetch it again.

## Queue

Lanes:

- Machine: Q1b (~14:00); next Q1c, Q2.
- Code: idle.

In order (approved YYYY-MM-DD):

- Q1 (Running: refresh.log; machine lane): Refresh the data, then verify it.
  - Q1a (Done: abc1234): Progress lines for the refresh.
  - Q1b (Running: refresh.log): The refresh itself, finish around 14:00.
  - Q1c (Waiting on Q1b): Verify it against the old data.
- Q2 (Waiting on Q1; machine lane): Re-run the benchmark on the refreshed data.
- Q3 (Blocked by A1): Publish the results.
