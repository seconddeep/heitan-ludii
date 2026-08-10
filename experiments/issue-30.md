# Issue 30 Stronger UCT Balance and Strategy Report

This report records the experiments performed for GitHub Issue #30,
"Analyze Heitan balance and strategy with stronger AI."

## Environment

- Date: 2026-08-10
- Ludii Player: 1.3.14
- Ludii JAR SHA-256:
  `248a8bde801f347bc380a4957fdb48012b4bdf234a5591c9bf7479913d73068e`
- Java: OpenJDK 21.0.11
- Game definition: `games/Heitan.lud`
- Game definition SHA-256:
  `a833a7a0bb4edf3fe4f428876dfb07b6ff0cb143a68c105232800e5d7743644c`
- Experiment configuration: `experiments/issue-30/config.json`
- Source commit: `99d8a0d24429ac18889a3584ad6ce41781bd2acc`
- Evidence-file time span: 7,773 seconds (about 2 hours 10 minutes)

The complete machine-readable environment record is stored in
`experiments/issue-30/results/environment.json`. It also records hashes for the
configuration and experiment scripts.

## Method

The validated headless runner from Issue #11 loaded the repository's Heitan
definition through the Ludii API. UCT was limited by iterations rather than
elapsed time, avoiding machine-speed-dependent search budgets. Six workers ran
independent 10-game batches. Seeds and game indices remained globally unique
across the batches.

Three UCT self-play groups were run:

| Experiment | Black | White | Games |
| --- | ---: | ---: | ---: |
| UCT 100 | 100 iterations | 100 iterations | 100 |
| UCT 500 | 500 iterations | 500 iterations | 100 |
| UCT 1000 | 1000 iterations | 1000 iterations | 100 |

Black is always Player 1 and moves first under the Heitan rules. White is
always Player 2 and moves second. Alternating which colour moves first would
change the game rather than control an experimental variable. Because each
self-play game uses the same UCT budget in both seats, every strength receives
exactly 100 Black observations and 100 White observations.

Ludii does not expose all random streams used internally by UCT. Exact move
sequences are therefore not guaranteed to repeat from the numeric seed alone.
Every observed sequence is preserved in a replayable Ludii trial, while the
configuration, inputs, and statistical procedure remain reproducible.

## Completion and integrity

| Check | Result |
| --- | ---: |
| Completed natural endings | 300 / 300 |
| Games with 72 placements and 24 turns | 300 / 300 |
| Games with 36 Pieces per player | 300 / 300 |
| Scores independently verified | 300 / 300 |
| Winners independently verified | 300 / 300 |
| Final boards with all 41 points | 300 / 300 |
| Unique seeds | 300 / 300 |
| Unique experiment/game indices | 300 / 300 |
| Replayable trial files found | 300 / 300 |

No timeout, incomplete game, illegal Piece total, score mismatch, winner
mismatch, duplicate seed, duplicate game index, or missing trial remained in
the final dataset.

## Balance results

| UCT iterations | P1 wins | P2 wins | Draws | P1 win rate | P1 95% Wilson CI | P1-P2 margin |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 22 | 78 | 0 | 22% | 15.00%-31.07% | -56 points |
| 500 | 26 | 72 | 2 | 26% | 18.40%-35.37% | -46 points |
| 1000 | 39 | 53 | 8 | 39% | 30.02%-48.80% | -14 points |

The second player won substantially more often at all three budgets. The
imbalance was largest at 100 iterations and became smaller as search strength
increased. At 1000 iterations, P2 won 53 games, P1 won 39, and 8 were drawn.
This is evidence of a remaining P2 tendency in this sample, but it is also a
clear warning against estimating the size of the advantage from weak search:
the P1-P2 win margin narrowed from 56 to 14 percentage points.

The game length did not vary with strength. Every game lasted 72 placements and
24 turns because both players must place all 36 Pieces. Final-board measures,
rather than length, capture the gameplay changes.

## Final-board characteristics

Values below are averages per player, combining the two seats.

| UCT iterations | Secured Objectives | Advantage Objectives | Objective Pieces | Supply Pieces | Secured Supply Points |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 3.765 | 2.440 | 16.400 | 19.600 | 1.040 |
| 500 | 4.965 | 1.845 | 19.210 | 16.790 | 0.535 |
| 1000 | 5.330 | 1.620 | 19.585 | 16.415 | 0.630 |

Stronger UCT moved roughly three Pieces per player from Supply Points to
Objectives. At the same time, it secured more Objectives and fewer Supply
Points. This suggests a more efficient supply policy: stronger search often
uses temporary control of Supply Points to reach Objectives instead of spending
three Pieces to secure those Supply Points permanently.

The largest change occurred from 100 to 500 iterations:

- Secured Objectives increased by 1.20 per player.
- Objective Pieces increased by 2.81 per player.
- Advantage Objectives decreased as more contested Objectives became Secured.

The smaller 500-to-1000 changes, 0.365 additional Secured Objectives and 0.375
additional Objective Pieces per player, suggest that these aggregate measures
are beginning to stabilise.

## Positional patterns and convergence

For each point, the analysis formed a usage profile from its average final
Piece count. Adjacent strength profiles were compared using Pearson correlation
and mean absolute per-point change.

| Budgets compared | Objective correlation | Objective mean change | Supply correlation | Supply mean change |
| --- | ---: | ---: | ---: | ---: |
| 100 vs 500 | 0.2970 | 0.3513 Pieces | 0.8384 | 0.3256 Pieces |
| 500 vs 1000 | 0.7154 | 0.1481 Pieces | 0.9623 | 0.1964 Pieces |

Both point types were more similar between 500 and 1000 iterations than between
100 and 500. The higher correlation and smaller absolute changes provide
initial evidence that stronger UCT is converging on more consistent spatial
priorities.

At 1000 iterations, the four central Objectives were the four most occupied:

| Objective | Average total Pieces | P1 secured | P2 secured |
| --- | ---: | ---: | ---: |
| O11 | 2.84 | 47% | 35% |
| O22 | 2.82 | 42% | 36% |
| O12 | 2.77 | 37% | 36% |
| O21 | 2.69 | 37% | 40% |

This central concentration was less consistent at 100 iterations. Central
Objectives offer access through shared interior Supply Points, so their
emergence under deeper search is strategically plausible. This remains an
observed association rather than proof that every optimal strategy must be
centre-first.

Supply usage converged even more strongly than Objective usage. The 0.9623
correlation between 500 and 1000 iterations indicates that the stronger agents
were using a similar network of Supply Points, even though individual games
still varied.

## Deciding victory criteria

| UCT iterations | Secured Objectives | Advantage Objectives | Objective Pieces | Draw |
| ---: | ---: | ---: | ---: | ---: |
| 100 | 41% | 41% | 18% | 0% |
| 500 | 44% | 35% | 19% | 2% |
| 1000 | 52% | 29% | 11% | 8% |

Secured Objectives became the deciding criterion more often as search strength
increased. Advantage Objectives and Objective Pieces still decided 40% of the
1000-iteration games, so the lower tiebreak levels remain strategically
relevant. The higher draw rate at 1000 iterations is consistent with stronger,
more closely matched play producing more equal final evaluations.

## Reproduction and preserved evidence

With Java 21 and Ludii 1.3.14 available, run from the repository root:

```powershell
./experiments/issue-30/scripts/run-experiments.ps1 `
    -LudiiJar C:\path\to\Ludii-1.3.14.jar `
    -Parallelism 6

./experiments/issue-30/scripts/analyze-results.ps1
```

Generated evidence is stored under `experiments/issue-30/results/`:

- `raw/*.csv`: one record per game, including the complete final board
- `trials/**/*.trl`: 300 replayable Ludii trials
- `summary.csv`: balance and aggregate final-board measures
- `objectives.csv`: per-Objective state and Piece statistics
- `supply-points.csv`: per-Supply-Point state and Piece statistics
- `deciding-criteria.csv`: victory-criterion frequencies
- `strength-comparison.csv`: spatial convergence measures
- `analysis.json`: integrity-validation totals
- `environment.json`: versions, hashes, source commit, and evidence time span

## Limitations

- One hundred games per budget narrows uncertainty compared with Issue #11 but
  does not establish solved-game balance.
- UCT's internal random streams prevent bit-for-bit regeneration from seeds.
- The experiment compares three budgets for one Ludii UCT implementation; it
  does not compare different search algorithms or tuned UCT parameters.
- The apparent reduction in second-player advantage at 1000 iterations should
  be tested with larger samples and still higher budgets before being treated
  as convergence to the true game-theoretic balance.
- Spatial correlations describe aggregate final positions and do not prove a
  causal opening or move-order strategy.

## Conclusion

The Issue #30 acceptance criteria are satisfied:

- Three stronger UCT self-play experiments, totalling 300 games, were completed.
- First- and second-player outcomes were evaluated with confidence intervals.
- Complete raw data, final boards, trials, configuration, hashes, and analysis
  outputs were preserved.
- Search strength changed play measurably: stronger UCT allocated more Pieces
  to Objectives, secured more Objectives, and used fewer Supply Pieces.
- The 500- and 1000-iteration spatial profiles were substantially more similar
  than the 100- and 500-iteration profiles, providing initial evidence of
  strategic convergence.

This issue changed experiment tooling, generated evidence, and documentation
only. `games/Heitan.lud` and the rule specifications were not modified.
