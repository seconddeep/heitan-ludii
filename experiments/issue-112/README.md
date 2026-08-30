# Issue 112: corrected-rule 4x4 deep UCT

This directory preregisters and implements GitHub Issue #112. It regenerates
independent fixed 4x4 samples at UCT 10,000, 30,000, and 100,000 under the
corrected Objective-piece tiebreak. It does not modify the game, rules, board,
or prior experiment evidence.

The repository-wide [safety and experiment integrity principles](../../docs/repository-principles.md)
apply. Historical original-rule trajectories, Issue #105 terminal rescoring,
and regenerated corrected-rule trajectories remain separate samples.

## Frozen scientific scope

Each budget has 100 task identities and seeds fixed before production. Failed
tasks are not replaced. The primary measure is unconditional P1 win rate, with
draws in the denominator. Corrected 100k minus corrected 30k is the primary
depth contrast. Point estimates and 95% game-bootstrap intervals are primary;
descriptive classifications are auxiliary and cannot be manually overridden.

Cross-board comparisons use Issue #108 corrected 3x3 evidence. Matched nominal
UCT iterations are not treated as equal effective search depth across boards.

## Source and scoring gates

Before production, the protocol locks every used #47/#83, #105, and #108
artifact and per-game evidence by repository-relative path, size, and SHA-256.
Every production start and resume verifies the complete source lock.

The same freeze step isolates `Board/4x4` in the source-locked
`games/Heitan.lud` and requires its positional values to be exactly:

- 36 Pieces per player;
- 72 total placements;
- Advantage weight 37;
- Secured weight 629.

The config and source-derived values must agree. Production cannot start if the
board option cannot be isolated, any value differs, or the game hash changes.
The corrected score is therefore `629 * Secured Objectives + 37 * Advantage
Objectives + own Pieces on own-Advantage Objectives`.

## Outcome-blind production boundary

Production runs in budget order: 10k, then 30k, then 100k. After each budget,
`validate_trials.py` creates a validation-only gate that checks only:

- legal replay and Objective Supply-source legality;
- natural 72-placement / 24-turn completion;
- exactly three placements per turn and 36 Pieces per player;
- retained artifact hashes and manifest identity;
- explicit failure state and unchanged retry identity;
- resume integrity.

These gates do not aggregate or report P1/P2/draw, score, balance, or structural
results. The next budget cannot start without the preceding outcome-blind gate.
Score/winner reconstruction and all aggregates are forbidden until all 300
production identities have reached terminal states. The post-production
`--full-scoring` validation must pass before finalization and analysis.

## Resilience and evidence

One atomic task directory is used per game. Completed tasks are never
regenerated; retries retain the same game ID and seed. Interrupted work becomes
resumable, while OOM, abnormal exit, validation failure, and missing output stay
visible. Production requires `tmux`, `caffeinate -i`, a clean locked HEAD, the
locked Ludii JAR, and a non-identifying `HEITAN112_RUNNER_ID`.

Raw trials are immutable generation evidence. A portable UTF-8/LF trial with
the repository-relative `game=games/Heitan.lud` field is retained and hashed.
Revalidation uses temporary outputs and does not rewrite retained evidence.

## Execution order

Run from the repository root, with `LUDII_JAR` set to Ludii 1.3.14:

```sh
python3 -m unittest discover -s experiments/issue-112/scripts -p 'test_*.py'
python3 experiments/issue-112/scripts/run_experiments.py pilot
python3 experiments/issue-112/scripts/validate_trials.py --namespace pilot
python3 experiments/issue-112/scripts/freeze_protocol.py
```

Commit the locked implementation before production. For every budget, run the
resumable production command in `tmux` under `caffeinate -i`, then run its
outcome-blind validation gate. After 100k:

```sh
python3 experiments/issue-112/scripts/validate_trials.py \
  --namespace production --full-scoring
python3 experiments/issue-112/scripts/finalize_production.py
python3 experiments/issue-112/scripts/run_analysis.py --verify-deterministic
python3 experiments/issue-112/scripts/public_safety_audit.py
```

The concrete heap, worker, retry, and rerun commands are recorded in
`protocol-lock.json` after the excluded pilot. Pilot outcomes are excluded and
must not be inspected when choosing operational parameters.
