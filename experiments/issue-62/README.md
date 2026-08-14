# Issue 62: 3x3 Heitan scale baseline

This directory preregisters and records the 3x3 baseline comparison requested
by Issue 62. The definitions below are frozen before production results are
examined.

## Production samples and runtime rule

The planned 3x3 samples are 100 games each of Seeded Random, UCT 100, UCT 500,
and UCT 1000, with the non-overlapping seed ranges in `config.json`. A sample
may be reduced only when runtime requires it, and only for the affected
condition (expected primarily to be UCT 1000). The condition, reason, frozen
sample size, and seed/index range must be recorded here before any production
outcomes or analysis outputs are examined. Other conditions are not reduced
automatically.

Runtime freeze decision (made before examining production outcomes): **retain
100 games for every condition.** A two-game-per-condition smoke run measured
mean generation times of 0.237 seconds for Seeded Random, 13.675 seconds for
UCT 100, 34.157 seconds for UCT 500, and 42.880 seconds for UCT 1000. These
times make the planned samples practical with parallel execution, so no
condition-specific reduction is justified. The smoke trials are validation
data only and are excluded from production analysis.

## Frozen spatial definitions

Coordinates are normalized independently for each board. Each axis is assigned
to the nearest of `1/6`, `1/2`, and `5/6`, producing the established nine
`LL`--`HH` regions. On 3x3, Objectives cover all nine regions while Supply
Points occupy only corner-side bands; this is retained as a property of the
geometry and will not be retuned after outcomes are seen.

The fixed window is four Heitan turns, hence exactly 12 placements on every
board. On 3x3 it spans 4 of only 18 turns and is proportionally longer than on
4x4 or 6x6. It is therefore a **fixed-placement comparison, not a
fixed-progress-width comparison**. Checkpoints are separately fixed at 25%,
50%, 75%, and 90% using `ceil(fraction * total turns)`.

Primary spatial evidence is per-turn `3`, `2+1`, and `1+1+1` allocation and
mean regions used. Four-turn normalized entropy, largest-region share, HHI,
and coverage are secondary evidence. Bootstrap intervals resample games 2,000
times with seed 560056.

Supply-site concentration is the per-game HHI of placements whose target is a
Supply Point, averaged within each condition. Site ranks use pooled placement
counts within a board and condition. Rank stability is the fraction of the
2,000 game-bootstrap replicates in which a site is tied for the highest pooled
count. Exact site ranks are exploratory and are not compared directly across
different board sizes.

## Frozen leader and reversal definitions

At a checkpoint, the primary leader is determined lexicographically from the
state at the end of the checkpoint turn:

1. number of Secured Objectives;
2. if tied, number of Advantage Objectives;
3. if still tied, Pieces on Objectives.

For diagnostic output, `secured` and `secured_advantage` leaders are also
reported, but `full_lexicographic` is primary. A game tied at the selected
layer has no checkpoint leader and is reported separately; it is excluded
from the reversal-rate denominator. A natural-end draw is also reported
separately and excluded from that denominator.

A **leader reversal** means that a non-tied checkpoint leader is different
from the natural-end winner. This measures checkpoint-to-final persistence,
not every intermediate lead change. The reversal denominator is therefore
games having both a non-tied checkpoint leader and a non-draw final winner.

## Validation stop conditions

Every analyzed trial must replay as legal Ludii moves and end naturally with
the board-specific placement and turn totals. Every turn must contain three
placements. Replayed winner and independently reconstructed score must match
the saved trial. Game keys, seeds, and trial hashes must be unique. Analysis
stops on any failure.

## Intended commands

```powershell
./experiments/issue-62/scripts/run-experiments.ps1 -Smoke -Parallelism 4
./experiments/issue-62/scripts/run-experiments.ps1 -Parallelism 6
./experiments/issue-62/scripts/run-analysis.ps1
```

Requirements: Ludii Player 1.3.14, Java 21, and Node.js 24 or later.

## Completed result

All four preregistered 3x3 conditions completed at 100 games, for 400 new
games total. Generation took 2358.773 wall-clock seconds at parallelism 12.
All 1,050 new and reused comparison trials passed provenance and legal replay
validation, covering 86,400 placements and 28,800 three-placement turns. See
`experiments/issue-62.md` for the complete result and qualified scaling
interpretation.

The complete generated `results/raw/turn-states.csv` is stored as
`turn-states.csv.zip` because its uncompressed form exceeds GitHub's 100 MB
per-file limit. `run-analysis.ps1` regenerates the ignored CSV directly.
