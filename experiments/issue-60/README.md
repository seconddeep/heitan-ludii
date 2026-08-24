# Issue 60: replicate 6x6 UCT 1000 spatial allocation

This experiment expands the validated 6x6 UCT 1000 sample from Issue 58
from 20 to 50 games. It tests whether the stronger-search per-turn spatial
allocation difference replicates while rechecking the broader four-turn
spatial effect.

## Frozen analysis

`analyze-scale.mjs`, `analyze-scale.test.mjs`, and `HeitanScaleReplay.java`
are byte-for-byte copies of Issue 56. Both wrappers stop if any copied file's
SHA-256 differs from its Issue 56 source. The region mapping, four-turn window,
progress checkpoints, metrics, bootstrap procedure, and interpretation
hierarchy are therefore unchanged.

The experiment runner is outside that frozen set. Issue 60 supplies the new
index and seed ranges through `config.json` and its wrapper. Its only Java
change replaces `toRealPath()` on the repository root with lexical absolute
path normalization; the root is used solely to record relative trial paths.
This avoids an execution-environment permission failure and does not alter
game generation, AI, seed, index, scoring, or validation logic.

## Samples and provenance

- Reused 6x6 UCT 1000: Issue 58, indices 1--20, seeds `581000`--`581019`.
- New 6x6 UCT 1000: Issue 60, indices 21--50, seeds `581020`--`581049`.
- Comparison 4x4 UCT 1000: Issue 30, indices 1--100, seeds
  `300200`--`300299`.

The two 6x6 sources share `experiment_id=6x6-uct-1000`, so the frozen
analysis aggregates them as one 50-game group. Their source issues remain
recorded per trial in `results/trial-sources.csv`, together with index, seed,
path, and trial SHA-256. Manifest generation validates configured ranges,
runner rows, unique analysis keys, and unique trial contents before replay.

## Requirements

- Java 21
- Node.js 24 or later
- Ludii Player 1.3.14

## Run

Generate the 30 new games:

```powershell
$env:LUDII_JAR = '<path-to-Ludii-1.3.14.jar>'
./experiments/issue-60/scripts/run-experiments.ps1 `
  -LudiiJar $env:LUDII_JAR -Parallelism 6
```

If execution is interrupted, preserve completed trials and continue missing
indices with individually addressed runner tasks:

```powershell
./experiments/issue-60/scripts/run-experiments.ps1 `
  -LudiiJar $env:LUDII_JAR -Parallelism 12 -Resume
```

Replay all 150 games, validate provenance, and run the frozen analysis:

```powershell
./experiments/issue-60/scripts/run-analysis.ps1 `
  -LudiiJar $env:LUDII_JAR
```

## Interpretation

The primary evidence is per-turn `3`, `2+1`, and `1+1+1` allocation, mean
regions per turn, and progress-quarter consistency. Fixed four-turn entropy,
largest-region share, and HHI are the secondary consistency measures. Supply
versus Objective allocation and later Objective use of Secured Supply are
reported without retuning metrics.

The final report will choose explicitly between a replicated simultaneous
multi-front effect plus broader multi-turn play, and a scaling effect that
remains primarily broader multi-turn play. Seat balance, exact Supply
rankings, reversal rates, and convergence remain out of scope unless evidence
is unexpectedly strong.

## Completed result

The 30 new games completed across three resumable execution segments totaling
9929.087 seconds. All 150 comparison trials replayed successfully. The
expanded 6x6 three-region rate is 61.63% (frozen game-bootstrap 95% interval
59.75--63.46%), compared with 56.83% (54.88--58.96%) on 4x4. The advantage
persists in the first three progress quarters and reverses in the final
quarter. All four fixed-window checkpoints retain higher 6x6 entropy and
lower largest-region share and HHI.

The supported interpretation is that UCT 1000 6x6 play has both greater
overall simultaneous multi-front allocation within a turn and broader
multi-turn spatial play, with the per-turn conclusion qualified as not
universal across phases. See `experiments/issue-60.md` for the full report.
