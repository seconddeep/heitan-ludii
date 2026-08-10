# Issue 30 stronger-UCT experiment workflow

This directory contains the reproducible experiment workflow for GitHub Issue
#30, "Analyze Heitan balance and strategy with stronger AI."

The workflow reuses the validated headless Java runner from Issue #11. It does
not modify the Heitan game definition or either rule specification.

## Requirements

- Java Development Kit 21 (`java` on `PATH`)
- Ludii Player 1.3.14 JAR
- PowerShell 7 or Windows PowerShell 5.1

## Experiments

The checked-in configuration runs 100 UCT self-play games at each of 100, 500,
and 1000 iterations per placement. Black is Player 1 and always moves first in
Heitan; White is Player 2 and always moves second. Because both seats use the
same UCT configuration, every strength receives one Black and one White
observation per game. Alternating which colour moves first would change the
game rules and is therefore outside this issue.

UCT uses iteration limits rather than time limits. Ludii does not expose every
random stream used internally by UCT, so reruns are statistically reproducible
rather than guaranteed to produce identical moves. Every observed game is
preserved as a replayable `.trl` file.

## Run

From the repository root:

```powershell
./experiments/issue-30/scripts/run-experiments.ps1 `
    -LudiiJar C:\path\to\Ludii-1.3.14.jar `
    -Parallelism 6

./experiments/issue-30/scripts/analyze-results.ps1
```

For a small smoke test, copy `config.json`, reduce each `games` value, and pass
the copy using `-ConfigPath`. Generated data is always written under
`experiments/issue-30/results/`.

`-Parallelism` defaults to 1. Values above 1 divide each experiment into
10-game batches (configurable with `-BatchSize`) while preserving globally
unique seeds and game indices. Iteration-limited search makes these batches
independent of machine-speed differences.

## Outputs

- `results/raw/*.csv`: one row per game, including the complete final board
- `results/trials/**/*.trl`: replayable Ludii trials
- `results/timings.csv`: worker time for each experiment group after an uninterrupted run
- `results/summary.csv`: outcomes and aggregate final-board metrics
- `results/objectives.csv`: per-Objective state and Piece statistics
- `results/supply-points.csv`: per-Supply-Point state and Piece statistics
- `results/deciding-criteria.csv`: deciding victory criterion frequencies
- `results/strength-comparison.csv`: pairwise changes between UCT budgets
- `results/analysis.json`: integrity-validation totals
- `results/environment.json`: versions, hashes, configuration, and source commit
