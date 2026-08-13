# Issue 58: deeper 6x6 spatial-scaling validation

This experiment follows Issue 56 by expanding the 6x6 UCT 500 sample from 20
to 50 validated games and adding a small 6x6 UCT 1000 sample. It compares both
levels against the existing validated 4x4 data from Issue 30.

## Frozen analysis definitions

The region mapping, per-turn allocation patterns, fixed four-turn windows,
progress checkpoints, normalized spatial measures, bootstrap procedure, and
interpretation hierarchy are copied from Issue 56. The metric-calculation
logic in `analyze-scale.mjs` is unchanged. Issue 58 changes only experiment
inputs, configuration, output locations, and wrapper orchestration.

The copied source hashes are:

| File | SHA-256 |
| --- | --- |
| `analyze-scale.mjs` | `08d7b7e18fe53684fe668489d65dcb04a6c6fa45c8ed31cbbe74f09a477c0355` |
| `HeitanScaleReplay.java` | `963755c9067b4827f97ab87a6e522ab850e3b036de3d603e897dba84f1cb7ded` |
| `Heitan6x6Experiment.java` | `3fbb1f7cdbfa68d2e7a141d3446b4cf9d0fd560804e0fb1c69ac574bdb8959cd` |

The hashes are checked against Issue 56 before running the experiment. No
region or metric is retuned after observing the new results. Subsampling stays
disabled.

## Samples and seeds

- Existing 6x6 UCT 500: 20 games, seeds `560150`--`560169`, from Issue 56.
- New 6x6 UCT 500: 30 games, seeds `560170`--`560199`, indices 21--50.
- New 6x6 UCT 1000: target 20 games, seeds `581000`--`581019`.
- Existing 4x4 UCT 500 and UCT 1000: 100 games each, from Issue 30.

If the UCT 1000 sample must be reduced after the timed smoke check, it uses a
prefix of the fixed `581000`--`581019` range and the reason is recorded here.

The timed one-game UCT 1000 smoke run completed naturally in 509.846 seconds
with 144 placements and 48 turns. This projects to about 2.8 hours when run
sequentially and is practical with the configured parallelism of six, so the
full 20-game target is retained. The smoke trial is stored under
`results-smoke` and is not included in the analyzed sample.

The full 30-game UCT 500 continuation and 20-game UCT 1000 run completed in
8722.490 seconds with parallelism six. All 50 new games ended naturally.

## Requirements

- Java 21
- Node.js 24 or later
- Ludii Player 1.3.14

## Run

First time one UCT 1000 game without mixing it into the analyzed results:

```powershell
./experiments/issue-58/scripts/run-experiments.ps1 `
  -LudiiJar C:\Users\verti\Ludii-1.3.14.jar `
  -ExperimentId 6x6-uct-1000 -GamesPerExperiment 1
```

Run the configured UCT 500 continuation and UCT 1000 samples:

```powershell
./experiments/issue-58/scripts/run-experiments.ps1 `
  -LudiiJar C:\Users\verti\Ludii-1.3.14.jar -Parallelism 6
```

Replay every new and comparison trial, run the frozen analysis, and record the
environment:

```powershell
./experiments/issue-58/scripts/run-analysis.ps1 `
  -LudiiJar C:\Users\verti\Ludii-1.3.14.jar
```

All analyzed trials must replay as legal Ludii moves. An invalid or incomplete
trial, a score or winner mismatch, an unexpected trial count, or a duplicate
game key stops the analysis.

## Outputs

- `results/trials/`: 30 new UCT 500 and 20 UCT 1000 replayable trials
- `results/raw/`: runner data plus replayed game, placement, and turn-state data
- `results/turn-allocation-summary.csv`: per-turn regional allocation results
- `results/turn-allocation-progress.csv`: allocation results by progress quarter
- `results/progress-summary.csv`: fixed-window checkpoint comparisons
- `results/supply-conversion-summary.csv`: later Objective use of Secured Supply
- `results/analysis.json`: validation totals and frozen interpretation hierarchy
- `results/environment-run.json` and `results/environment.json`: runtime,
  versions, and source hashes
- `experiments/issue-58.md`: findings and conclusion

## Interpretation

The primary evidence remains the per-turn `3`, `2+1`, and `1+1+1` allocation
distribution. Normalized entropy, largest-region share, HHI, and coverage in
fixed four-turn windows are secondary evidence. The conclusion focuses on
whether broader multi-turn spatial play on 6x6 is reproducible at UCT 500 and
persists at UCT 1000. Seat balance, exact Supply rankings, reversal rates, and
strategic convergence are not treated as settled by these samples.
