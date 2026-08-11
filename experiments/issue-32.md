# Issue 32 Deeper UCT Convergence Report

This report records the experiments performed for GitHub Issue #32,
"Analyze Heitan convergence with deeper UCT search."

## Environment

- Date: 2026-08-11
- Machine: Apple M4 Mac mini, 10 cores, 16 GB RAM
- OS: macOS 26.5.2 arm64
- Ludii Player: 1.3.14
- Ludii JAR SHA-256:
  `248a8bde801f347bc380a4957fdb48012b4bdf234a5591c9bf7479913d73068e`
- Java: OpenJDK 21.0.12
- Game definition SHA-256:
  `d81468535f9beb331040fd0bc736e93dfcb9bfe7da36042ce4aabf54f96b2f6c`
- Source commit: `5ca93416cdaa030b633303a8ac77b87d53befd52`
- Wall-clock span: 45,923 seconds (about 12 hours 45 minutes, including sleep)

The machine-readable environment and input hashes are preserved in
`experiments/issue-32/results/environment.json`.

## Method

The validated Issue #11 Java runner loaded the repository's Heitan definition
through Ludii 1.3.14. Both seats used the same UCT iteration limit. Six workers
ran independent 10-game batches with globally unique seeds and game indices.
Every observed game was saved as a replayable Ludii trial.

| Experiment | Black | White | Games |
| --- | ---: | ---: | ---: |
| UCT 3000 | 3000 iterations | 3000 iterations | 100 |
| UCT 10000 | 10000 iterations | 10000 iterations | 100 |

Black is Player 1 and always moves first under the Heitan rules. UCT's internal
random streams do not support bit-for-bit reproduction from the recorded game
seed alone, so the complete trials are the authoritative move-sequence record.

## Completion and integrity

| Check | Result |
| --- | ---: |
| Completed natural endings | 200 / 200 |
| Games with 72 placements and 24 turns | 200 / 200 |
| Games with 36 Pieces per player | 200 / 200 |
| Scores independently verified | 200 / 200 |
| Winners independently verified | 200 / 200 |
| Final boards with all 41 points | 200 / 200 |
| Unique seeds | 200 / 200 |
| Unique experiment/game indices | 200 / 200 |
| Replayable trial files found | 200 / 200 |

No timeout, incomplete ending, invariant failure, duplicate identifier, score
mismatch, winner mismatch, or missing trial remained in the dataset.

## Balance results

| UCT | P1 wins | P2 wins | Draws | P1 rate (95% CI) | P2 rate (95% CI) | Draw rate (95% CI) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 22 | 78 | 0 | 22% (15.00-31.07%) | 78% (68.93-85.00%) | 0% (0.00-3.70%) |
| 500 | 26 | 72 | 2 | 26% (18.40-35.37%) | 72% (62.51-79.86%) | 2% (0.55-7.00%) |
| 1000 | 39 | 53 | 8 | 39% (30.02-48.80%) | 53% (43.29-62.49%) | 8% (4.11-15.00%) |
| 3000 | 35 | 61 | 4 | 35% (26.36-44.75%) | 61% (51.20-69.98%) | 4% (1.57-9.84%) |
| 10000 | 49 | 41 | 10 | 49% (39.42-58.65%) | 41% (31.87-50.80%) | 10% (5.52-17.44%) |

The P2 tendency did not persist monotonically. It strengthened again at 3000
iterations, where P2 led by 26 percentage points, but reversed at 10000, where
P1 led by 8 points. At 10000, both players' win-rate confidence intervals
overlap 50%, and the 8-point observed difference is not strong evidence of a
seat advantage. The sequence therefore indicates strong search-depth effects,
not stable convergence of the balance estimate.

Draws rose from 0% at 100 iterations to 10% at 10000, their highest observed
rate. The non-monotonic 8%, 4%, 10% sequence from 1000 onward does not establish
that the draw rate itself has converged.

## Final-board characteristics

Values are averages per player, combining the two seats.

| UCT | Secured Objectives | Advantage Objectives | Objective Pieces | Supply Pieces | Secured Supply Points |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 3.765 | 2.440 | 16.400 | 19.600 | 1.040 |
| 500 | 4.965 | 1.845 | 19.210 | 16.790 | 0.535 |
| 1000 | 5.330 | 1.620 | 19.585 | 16.415 | 0.630 |
| 3000 | 5.160 | 1.675 | 18.950 | 17.050 | 1.225 |
| 10000 | 4.805 | 1.655 | 17.560 | 18.440 | 1.835 |

The trend reported by Issue #30 did not continue indefinitely. Objective
allocation and secured Objectives peaked around 1000 iterations, then declined
at 3000 and 10000. Conversely, permanent securing of Supply Points increased
substantially. Deeper UCT therefore reveals a different resource-allocation
policy rather than simply refining the 1000-iteration policy.

## Spatial patterns and convergence

| Budgets compared | Objective correlation | Objective mean change | Supply correlation | Supply mean change |
| --- | ---: | ---: | ---: | ---: |
| 100 vs 500 | 0.2970 | 0.3513 Pieces | 0.8384 | 0.3256 Pieces |
| 500 vs 1000 | 0.7154 | 0.1481 Pieces | 0.9623 | 0.1964 Pieces |
| 1000 vs 3000 | 0.9037 | 0.1969 Pieces | 0.9797 | 0.3156 Pieces |
| 3000 vs 10000 | 0.9483 | 0.2125 Pieces | 0.9798 | 0.3312 Pieces |

Spatial rankings are stabilising: correlations exceed 0.90 for Objectives and
0.97 for Supply Points in both new comparisons. However, the mean per-point
changes no longer shrink. The spatial profile is therefore converging in
relative priority but not yet in absolute Piece allocation.

At 10000 iterations the four central Objectives remain the four most occupied:
O22 (3.02 Pieces), O12 (2.96), O21 (2.94), and O11 (2.91). This strengthens the
Issue #30 observation that deep UCT consistently prioritises the centre.

## Victory criteria and close endings

| UCT | Secured Objectives | Advantage Objectives | Objective Pieces | Draw |
| ---: | ---: | ---: | ---: | ---: |
| 100 | 41% | 41% | 18% | 0% |
| 500 | 44% | 35% | 19% | 2% |
| 1000 | 52% | 29% | 11% | 8% |
| 3000 | 50% | 34% | 12% | 4% |
| 10000 | 52% | 31% | 7% | 10% |

Secured Objectives decided about half of the games from 1000 iterations onward.
At 10000, only 7% reached Objective Pieces as the deciding criterion and 10%
were exact draws. Secured Objectives were tied in 48% of 10000-iteration games;
the first two criteria were both tied in 17%. These values are close to the
1000- and 3000-iteration samples rather than showing a monotonic rise in close
endings.

## Reproduction and preserved evidence

Run from the repository root with Java 21, Ludii 1.3.14, and Python 3:

```sh
python3 experiments/issue-32/scripts/run_experiments.py \
  --ludii-jar /path/to/Ludii-1.3.14.jar \
  --parallelism 6 --batch-size 10

python3 experiments/issue-32/scripts/analyze_results.py
```

The repository preserves 20 raw batch files, 200 replayable trials, aggregate
CSVs, integrity results, timings, configuration, and environment hashes under
`experiments/issue-32/results/`.

## Limitations

- One hundred games per budget leaves broad confidence intervals and cannot
  establish game-theoretic balance.
- The experiment samples one Ludii UCT implementation and two new budgets.
- UCT's internal random streams prevent exact regeneration from numeric seeds.
- Correlation measures aggregate final positions, not opening sequences or
  causal strategy.
- The wall-clock span includes a period when the Mac was asleep; worker-time
  measurements are more useful than elapsed wall time for performance.

## Conclusion

The Issue #32 acceptance criteria are satisfied. Both deeper UCT experiments
completed with verified natural endings, independently checked scores and
winners, and preserved replayable evidence.

P2 advantage does not remain stable: it is pronounced at 3000 iterations but
reverses to a small, statistically inconclusive P1 tendency at 10000. Balance
has therefore not demonstrably converged. Spatial priorities show clearer
convergence, especially the persistent central-Objective emphasis, while the
absolute allocation shifts back toward Supply Points at the deepest search.
Stronger search thus reveals materially different strategic behaviour, and the
P2 tendency seen at lower budgets is at least partly a search-depth artifact.

This analysis changed experiment tooling, generated evidence, and documentation
only. `games/Heitan.lud` and both rule specifications were not modified.
