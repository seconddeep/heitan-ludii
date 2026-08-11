# Issue 32 deeper-UCT experiment workflow

This directory contains the reproducible experiment workflow for GitHub Issue
#32, "Analyze Heitan convergence with deeper UCT search."

It reuses the validated Java runner and the 100/500/1000-iteration baseline
from Issue #30. It does not modify the game definition or rule specifications.

## Requirements

- Java Development Kit 21 (`java` on `PATH`)
- Ludii Player 1.3.14 JAR
- Python 3.9 or newer

## Experiments

The checked-in configuration runs 100 UCT self-play games at 3000 iterations
and 100 at 10000 iterations per placement. Black is Player 1 and White is
Player 2. Search is iteration-limited, not time-limited.

## Run

From the repository root, first run a two-game-per-strength smoke test:

```sh
python3 experiments/issue-32/scripts/run_experiments.py \
  --ludii-jar /path/to/Ludii-1.3.14.jar \
  --games-override 2 --parallelism 2
```

The full run replaces the smoke-test evidence:

```sh
python3 experiments/issue-32/scripts/run_experiments.py \
  --ludii-jar /path/to/Ludii-1.3.14.jar \
  --parallelism 6 --batch-size 10

python3 experiments/issue-32/scripts/analyze_results.py
```

Each non-metadata run is a complete snapshot: existing Issue #32 raw CSV and
trial files are removed before new workers start. Issue #30 evidence is only
read as a comparison baseline.

## Outputs

- `results/raw/*.csv`: one record per game with the complete final board
- `results/trials/**/*.trl`: replayable Ludii trials
- `results/timings.csv`: worker time by experiment
- `results/summary.csv`: outcomes and aggregate final-board metrics
- `results/objectives.csv`: per-Objective metrics
- `results/supply-points.csv`: per-Supply-Point metrics
- `results/deciding-criteria.csv`: victory-criterion frequencies
- `results/score-differences.csv`: score-gap and close-ending metrics
- `results/strength-comparison.csv`: convergence across 100 through 10000
- `results/analysis.json`: integrity validation
- `results/environment.json`: versions, hashes, configuration, and commit
