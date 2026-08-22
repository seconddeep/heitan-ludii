# Issue 82: 3x3 deep-UCT first-player balance

This directory preregisters and implements the experiment requested by
GitHub Issue #82. It does not change the game definition, board topology,
piece count, scoring, or either rules document.

## Frozen experimental scope

The primary experiment is exactly 100 validated self-play games at each of
UCT 10,000, 30,000, and 100,000. These budgets live under `primary_budgets`
and `production.primary_tasks` in `config.json`.

UCT 300,000 is separate under `optional_budget`. It is not part of the primary
completion criteria and may enter production only after its excluded smoke
sample passes every preregistered operational criterion. The adoption decision
may inspect runtime, peak memory, completion/failure, artifact existence, and
replayability only. It must not inspect winners, scores, or balance estimates.

All production seed ranges are independent. A failed seed is never replaced.
Retries retain the same experiment version, budget, game index, and seed.

## Validated board invariants

Every analyzed game must use `Board/3x3` and contain exactly 25 sites:

- 16 Supply Points (`S00` through `S33`)
- 9 Objectives (`O00` through `O22`)

It must end naturally after 54 placements and 18 three-placement Heitan turns,
with 27 Pieces placed by each player. The independently reconstructed score is
`280 * Secured Objectives + 28 * Advantage Objectives + Objective Pieces`.

## Empirical stability rule

The mechanical 3 and 7 percentage-point thresholds in `config.json` are
reused unchanged from Issue #47; they were not selected from Issue #82 data.
The labels are descriptive sample-robustness labels only and do not establish
optimal play, solved balance, or game-theoretic convergence.

## Persistent production execution

The manifest is the primary state-management record for resume, with PID,
host identity, live-process state, and artifact existence/hash checked for
consistency. On restart, a stale transient task becomes `interrupted` and is
retried only with the same identity. A live task owned by another still-running
runner is not duplicated. A `completed` task whose artifacts still match is
always skipped and never regenerated.

Long production jobs must run in `tmux` under `caffeinate -i`. From the repo
root, set the Ludii path and run the tests and excluded pilot:

```sh
export LUDII_JAR=/Users/yasumasa/Ludii-1.3.14.jar
python3 -m unittest discover -s experiments/issue-82/scripts -p 'test_*.py'
python3 experiments/issue-82/scripts/run_experiments.py pilot --ludii-jar "$LUDII_JAR"
python3 experiments/issue-82/scripts/status.py --namespace pilot --operational-only
```

Freeze operational settings and explicitly include or exclude optional 300k:

```sh
python3 experiments/issue-82/scripts/freeze_protocol.py --ludii-jar "$LUDII_JAR" \
  --workers-10k 2 --workers-30k 2 --workers-100k 1 \
  --heap-10k 4g --heap-30k 4g --heap-100k 8g \
  --optional-300k exclude
```

Start each primary budget in its own persistent session:

```sh
tmux new-session -d -s heitan-82-10k \
  "cd '$PWD' && caffeinate -i env HEITAN82_CAFFEINATE=1 python3 experiments/issue-82/scripts/run_experiments.py production --budget 10000 --ludii-jar '$LUDII_JAR'"
tmux new-session -d -s heitan-82-30k \
  "cd '$PWD' && caffeinate -i env HEITAN82_CAFFEINATE=1 python3 experiments/issue-82/scripts/run_experiments.py production --budget 30000 --ludii-jar '$LUDII_JAR'"
tmux new-session -d -s heitan-82-100k \
  "cd '$PWD' && caffeinate -i env HEITAN82_CAFFEINATE=1 python3 experiments/issue-82/scripts/run_experiments.py production --budget 100000 --ludii-jar '$LUDII_JAR'"
```

Run these stages sequentially in the displayed order and revalidate each
completed stage before starting the next one. Do not launch the three sessions
at the same time; the separate names make each stage independently resumable,
not concurrent.

Use `tmux attach -t <session>` to inspect a session. If the runner, Java
subprocess, SSH connection, or host stops, restart the exact same command.
Resume processes only unfinished tasks. OOM, abnormal exit, timeout, and
validation failure are recorded per game and do not silently change the
sample.

After all possible retries are complete, finalize and analyze:

```sh
python3 experiments/issue-82/scripts/validate_trials.py --namespace production --budget 10000 --ludii-jar "$LUDII_JAR"
python3 experiments/issue-82/scripts/validate_trials.py --namespace production --budget 30000 --ludii-jar "$LUDII_JAR"
python3 experiments/issue-82/scripts/validate_trials.py --namespace production --budget 100000 --ludii-jar "$LUDII_JAR"
python3 experiments/issue-82/scripts/finalize_production.py
python3 experiments/issue-82/scripts/run_analysis.py --verify-deterministic
```

Requirements: Ludii Player 1.3.14, Java 21, Python 3.11 or later, `tmux`, and
macOS `caffeinate` for production execution.
