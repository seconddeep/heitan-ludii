# Issue 120: corrected-rule 7x7 UCT 30k follow-up

This directory preregisters and implements 30 independent Board/7x7 UCT
30,000 self-play tasks under the corrected Objective-piece tiebreak. The
primary comparison is against the frozen 30-game UCT 10,000 sample from Issue
118. Corrected 3x3 and 4x4 UCT 30,000 samples are secondary descriptive
context. No game rule, topology, board parameter, or historical evidence is
modified.

The repository-wide [safety and experiment integrity principles](../../docs/repository-principles.md)
apply. Issue 116 benchmark games are operational evidence only and are never
analysis samples.

## Frozen measures and accounting

The primary measures are unconditional P1 wins and draws divided by validated
completed games. Single-rate 95% intervals use Wilson score intervals. The
primary `30k - 10k` P1 and draw differences use independent game-level
nonparametric bootstrap intervals. The bootstrap seed, replicate count, task
identities, seeds, comparison inputs, and statistical procedures are locked
before production outcomes are inspected.

Every final report satisfies `planned = validated + failed`. The internal
`corrupt` state is retained for diagnosis but is included in `failed` for final
accounting. Failed seeds are never replaced; their state and detailed reason
remain in the manifest and `failures.csv`.

## Source and comparison gates

Production is allowed only if source-locked `games/Heitan.lud` exposes exactly
one Board/7x7 option with 64 Supply points, 49 Objectives, 72 Pieces per player,
144 placements, 48 Heitan turns, Advantage weight 73, and Secured weight 3650.
The corrected third layer counts only a player's own Pieces on Objectives where
that player has Advantage.

Issue 118 aggregate artifacts and all 30 validated per-game trial, result, and
validation artifacts are hash-locked. The Issue 118 sample is not regenerated.
The 3x3 and 4x4 UCT 30k contextual inputs are locked in the same way.

## Outcome-blind production boundary

The 30 task IDs and seeds are fixed before production. One worker runs under
`tmux` and `caffeinate -i`. Each task is saved atomically, completed tasks are
never regenerated, and retry/resume retains its task ID and seed. Status and
pre-final validation expose task states and failures but no outcome aggregate.

Aggregate analysis is forbidden until all tasks are terminal, every included
game passes full independent replay and scoring validation, and finalization
succeeds.

## Execution order

Run from the repository root with `LUDII_JAR` set to Ludii 1.3.14:

```sh
python3 -m unittest discover -s experiments/issue-120/scripts -p 'test_*.py'
python3 experiments/issue-120/scripts/run_experiments.py pilot
python3 experiments/issue-120/scripts/validate_trials.py --namespace pilot
python3 experiments/issue-120/scripts/freeze_protocol.py
```

Commit the experiment implementation and generated protocol/source locks. The
freeze records only information that exists at freeze time; it does not guess
the future production commit. Verify the committed tree is clean, then lock
that existing commit explicitly:

```sh
python3 experiments/issue-120/scripts/lock_production_head.py
```

Only then start production:

```sh
tmux new-session -d -s heitan-120-30k \
  "cd '$REPO_ROOT' && caffeinate -i env HEITAN120_CAFFEINATE=1 \
  HEITAN120_RUNNER_ID='$HEITAN120_RUNNER_ID' LUDII_JAR='$LUDII_JAR' \
  python3 experiments/issue-120/scripts/run_experiments.py production"
```

After all tasks are terminal, run outcome-blind operational validation, full
independent scoring validation, finalization, deterministic analysis, and the
public-safety audit:

```sh
python3 experiments/issue-120/scripts/validate_trials.py --namespace production --budget 30000
python3 experiments/issue-120/scripts/validate_trials.py --namespace production --full-scoring
python3 experiments/issue-120/scripts/finalize_production.py
python3 experiments/issue-120/scripts/run_analysis.py --verify-deterministic
python3 experiments/issue-120/scripts/public_safety_audit.py
```

If a full-scoring revalidation changes a task to `corrupt`, rerun the unchanged
production command only when the task still has a permitted attempt. A
score/winner reconstruction mismatch creates a global production block and
requires a reviewed corrective change before any resume.
