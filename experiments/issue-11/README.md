# Issue 11 experiment workflow

This directory contains the reproducible AI experiment workflow for GitHub
Issue #11.

## Requirements

- Java Development Kit 21 (`java` on `PATH`)
- Ludii Player 1.3.14 JAR
- PowerShell 7 or Windows PowerShell 5.1

## Run

From the repository root:

```powershell
./experiments/issue-11/scripts/run-experiments.ps1 `
    -LudiiJar C:\path\to\Ludii-1.3.14.jar

./experiments/issue-11/scripts/analyze-results.ps1
```

Use `-MetadataOnly` to refresh `results/environment.json` without rerunning
completed simulations.

The run script launches the Java runner in source-file mode, executes every entry in `config.json`,
saves one replayable Ludii trial per game, and records environment and SHA-256
metadata. The analysis script validates completion, piece totals, scores, and
winners before producing aggregate CSV files.

`SeededRandom` has the same policy as Ludii's Random agent (uniform selection
from legal moves) but uses an explicitly seeded random stream. Ludii's built-in
Random agent uses `ThreadLocalRandom`, which cannot be seeded by callers.

UCT uses a fixed iteration limit rather than a wall-clock limit. Its exact move
sequence is preserved in the generated `.trl` file; deterministic repetition of
UCT itself is not guaranteed by Ludii, because its internal random streams are
not exposed by the public runner API.
