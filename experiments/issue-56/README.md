# Issue 56: initial 6x6 scale analysis

This experiment evaluates whether the validated experimental 6x6 board
preserves Heitan's Supply-to-Objective structure while producing meaningful
cross-front allocation of the three placements in a turn. It is not a balance
or convergence study.

## Primary spatial measure

Every Point is mapped into one of nine normalized 3x3 regions. On each axis,
its board coordinate is divided by the board width and assigned to the nearest
of `1/6`, `1/2`, and `5/6`; an exact tie is assigned to the centre. Each turn is
then classified as `3` (one region), `2+1` (two regions), or `1+1+1` (three
regions).

The turn-level distribution and mean regions used per turn are the primary
evidence for multi-front allocation. Cumulative used-region counts, unused
regions, and entropy are sample-size sensitive because 6x6 contains twice as
many placements at the same progress percentage. They are descriptive only.
Normalized entropy, largest-region share, HHI, and fixed four-turn windows are
secondary evidence. Rarefaction/subsampling is deliberately disabled for the
initial analysis and is only a sensitivity analysis if these measures remain
ambiguous.

## Run

Requirements: Java 21, Python 3.9+, and Ludii Player 1.3.14.

```powershell
./experiments/issue-56/scripts/run-experiments.ps1 `
  -LudiiJar C:\Users\verti\Ludii-1.3.14.jar -Parallelism 6

./experiments/issue-56/scripts/run-analysis.ps1 `
  -LudiiJar C:\Users\verti\Ludii-1.3.14.jar
```

Use `-GamesPerExperiment 2` on the first command for a smoke run. A reduced
run is stored separately under `results-smoke` and never mixed with the full
results.

The analysis replays every 6x6 trial and the existing validated 4x4 Random,
UCT 100, and UCT 500 trials as legal Ludii moves. Invalid or incomplete trials
stop the workflow rather than entering the analysis.

The configured 6x6 sample sizes are Random 100, UCT 100 at 50 games, and UCT
500 at 20 games. A timed UCT 500 smoke game took about 396 seconds on the run
machine, so the lower end of the Issue's 20--50 range is used for that level.
This runtime-driven choice is recorded and no convergence claim is made.

## Outputs

- `results/trials/`: replayable 6x6 trials
- `results/raw/games.csv`: validated game-level data
- `results/raw/placements.csv`: every placement and its normalized region
- `results/raw/turn-states.csv`: layer and secured-state snapshots
- `results/turn-allocation-summary.csv`: primary 3/2+1/1+1+1 comparison
- `results/turn-allocation-progress.csv`: primary allocation by progress band
- `results/progress-comparison.csv`: progress-normalized structural measures
- `results/fixed-window-spatial.csv`: secondary fixed-window measures
- `results/supply-conversion-summary.csv`: Secured Supply to later Objective use
- `results/leader-reversibility-summary.csv`: checkpoint leader outcomes with denominators
- `results/analysis.json`, `results/environment.json`, and `experiments/issue-56.md`

All rates retain their denominators. Bootstrap intervals resample whole games.
No result is presented as proof of final balance or strategic convergence.
