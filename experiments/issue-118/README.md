# Issue 118: corrected-rule 7x7 UCT 10k screen

This directory preregisters and implements the focused Board/7x7 screening
experiment. It generates 30 independent UCT 10,000 self-play games under the
current corrected Objective-piece tiebreak. It does not modify the game, rules,
board, scoring, or historical evidence.

The repository-wide [safety and experiment integrity principles](../../docs/repository-principles.md)
apply. Issue 116 benchmark games are operational evidence only and are excluded
from this sample.

## Frozen measures and denominator

The primary balance measure is unconditional P1 wins divided by validated
completed games. The draw measure is draws divided by validated completed
games. Every report states `planned=30`, the actual validated denominator, and
the failed count. Failed, missing, or incomplete tasks are not silently replaced
and are not included in either rate denominator.

Single-rate 95% intervals use Wilson score intervals. Board-size differences
use an independent game-level nonparametric bootstrap with replacement. The
bootstrap seed, replicate count, task identities, seeds, and historical inputs
are locked before production outcomes are inspected.

## Corrected scoring gate

Production is allowed only if source-locked `games/Heitan.lud` exposes exactly
one Board/7x7 option with 64 Supply points, 49 Objectives, 72 Pieces per player,
144 placements, 48 Heitan turns, Advantage weight 73, and Secured weight 3650.
The source must implement the corrected third layer exactly: P1 counts only P1
Pieces on Objectives where P1 has Advantage, and P2 counts only P2 Pieces on
Objectives where P2 has Advantage. Pieces on opposing-Advantage, Secured, or
neutral Objectives do not enter that layer.

Independent replay validation reconstructs the same lexicographic score:
Secured Objectives, then Advantage Objectives, then corrected Objective Pieces.

## Outcome-blind production boundary

The 30 production task IDs and seeds are fixed before production. Production
runs with one worker under `tmux` and `caffeinate -i`. Each task is persisted
atomically, completed tasks are never regenerated, and retries retain the same
task ID and seed. Status and pre-final validation expose no aggregate outcomes.

Aggregate analysis is forbidden until all tasks are terminal, every included
game passes full independent validation, and `finalize_production.py` succeeds.

## Execution order

Run from the repository root with `LUDII_JAR` set to Ludii 1.3.14:

```sh
python3 -m unittest discover -s experiments/issue-118/scripts -p 'test_*.py'
python3 experiments/issue-118/scripts/run_experiments.py pilot
python3 experiments/issue-118/scripts/validate_trials.py --namespace pilot
python3 experiments/issue-118/scripts/freeze_protocol.py
```

Commit the frozen protocol at a clean HEAD, then start production:

```sh
tmux new-session -d -s heitan-118-10k \
  "cd '$REPO_ROOT' && caffeinate -i env HEITAN118_CAFFEINATE=1 \
  HEITAN118_RUNNER_ID='$HEITAN118_RUNNER_ID' LUDII_JAR='$LUDII_JAR' \
  python3 experiments/issue-118/scripts/run_experiments.py production"
```

After all tasks are terminal:

```sh
python3 experiments/issue-118/scripts/validate_trials.py --namespace production --full-scoring
python3 experiments/issue-118/scripts/finalize_production.py
python3 experiments/issue-118/scripts/run_analysis.py --verify-deterministic
python3 experiments/issue-118/scripts/public_safety_audit.py
```

