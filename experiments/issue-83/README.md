# Issue 83: 3x3 vs 4x4 deep-UCT first-player balance

This directory compares the validated, existing 3x3 and 4x4 self-play
samples requested by GitHub Issue #83. It does not generate self-play or
change the game, board definitions, rules, piece counts, or source trials.

## Frozen analysis

The primary measure is unconditional P1 win rate, with draws in the
denominator. The cross-board contrast is always `4x4 - 3x3`. UCT iteration
counts are matched nominal budgets, not evidence of equal effective search
depth.

The practical-equivalence margin is exactly 5 percentage points. For a
cross-board contrast `d`:

- `d > 0.05` is a material positive contrast;
- `d < -0.05` is a material negative contrast;
- `|d| <= 0.05` is descriptively similar.

The internal classification precedence is `unresolved-invalid`,
`non-monotonic`, `consistent`, `search-dependent`, then defensive
`unresolved`. The two unresolved codes share the same report label but retain
different machine-readable reasons. Full rules are frozen in `config.json`.

Bootstrap replicates resample games independently within every board-budget
condition. The difference-in-differences interval is obtained directly: all
four endpoint samples are independently resampled and the complete DiD is
recomputed in every replicate.

## Source samples

- 3x3: Issue #82 production, 100 games at each of 10k, 30k, and 100k.
- 4x4 10k: the Issue #32 baseline reused by Issue #47, 100 games.
- 4x4 30k: Issue #47 production, 100 games.
- 4x4 100k: Issue #47 finalized production, 97 games.

Issue #47 games 61, 78, and 93 at 100k remain excluded. Their possible
missing-not-at-random limitation is retained. No failed identity is replaced.

## Reproduce

Run from the repository root with Python 3.9 or later:

```sh
python3 experiments/issue-83/scripts/freeze_inputs.py
python3 -m unittest discover -s experiments/issue-83/scripts -p 'test_*.py'
python3 experiments/issue-83/scripts/run_analysis.py --verify-deterministic
```

`freeze_inputs.py` refuses to overwrite an existing lock. Delete neither lock
for an ordinary rerun: once frozen, rerun the tests and analysis only. The
analysis verifies every pinned source before reading outcomes.

## Progress-based turn comparisons

Secondary turn metrics use the state at the end of
`ceil(total_turns * progress)`:

| Progress | 3x3 (18 turns) | 4x4 (24 turns) |
|---|---:|---:|
| 75% | 14 | 18 |
| 90% | 17 | 22 |

A late reversal is eligible only when the checkpoint leader is non-tied and
the final result is non-draw. It occurs when that leader differs from the
final winner.
