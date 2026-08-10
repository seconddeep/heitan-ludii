# Issue 11 Initial AI Experiment Report

This report records the experiments performed for GitHub Issue #11,
"Run initial AI experiments."

## Environment

- Date: 2026-08-10
- Ludii Player: 1.3.14
- Ludii JAR SHA-256:
  `248a8bde801f347bc380a4957fdb48012b4bdf234a5591c9bf7479913d73068e`
- Java: OpenJDK 21.0.11
- Game definition: `games/Heitan.lud`
- Game definition SHA-256:
  `a833a7a0bb4edf3fe4f428876dfb07b6ff0cb143a68c105232800e5d7743644c`
- Experiment configuration: `experiments/issue-11/config.json`
- Source commit: `7240180ffdbee077667bfca3087e468654eef3f2`

The complete machine-readable environment record is stored in
`experiments/issue-11/results/environment.json`.

## Method

The headless Java runner loads the repository's `games/Heitan.lud` file through
the Ludii API. It saves one Ludii trial and one raw CSV row for every game. The
analysis script independently verifies the final board, score, and winner
before generating aggregate data.

Four experiment groups were run:

| Experiment | Black | White | Games | Search limit |
| --- | --- | --- | ---: | ---: |
| Seeded Random self-play | Seeded Random | Seeded Random | 100 | Not applicable |
| UCT self-play | UCT | UCT | 20 | 50 iterations per placement |
| UCT Black vs Random White | UCT | Seeded Random | 10 | 50 UCT iterations per placement |
| Random Black vs UCT White | Seeded Random | UCT | 10 | 50 UCT iterations per placement |

`SeededRandom` selects uniformly from the legal moves, like Ludii's Random AI,
but uses a recorded seed. This replacement is necessary because Ludii 1.3.14's
Random AI uses `ThreadLocalRandom`, whose seed cannot be set by callers.

UCT was limited by iterations instead of elapsed time to remove machine-speed
variation. Ludii does not expose every random stream used inside UCT, so UCT
runs are statistically reproducible rather than guaranteed to repeat bit for
bit. Every observed move sequence is preserved in a replayable `.trl` file.

## Completion and integrity

| Check | Result |
| --- | ---: |
| Completed games | 140 / 140 |
| Natural endings | 140 / 140 |
| Games with 72 placements | 140 / 140 |
| Games with 36 Pieces per player | 140 / 140 |
| Scores independently verified | 140 / 140 |
| Winners independently verified | 140 / 140 |

No timeout, incomplete game, illegal final Piece total, score mismatch, or
winner mismatch was observed. All games lasted 24 turns and 72 placements, as
expected from the rules.

## Results

### Outcomes

| Experiment | P1 wins | P2 wins | Draws | P1 win rate | P1 95% Wilson CI |
| --- | ---: | ---: | ---: | ---: | ---: |
| Seeded Random self-play | 60 | 39 | 1 | 60% | 50.20%-69.06% |
| UCT self-play | 4 | 16 | 0 | 20% | 8.07%-41.60% |
| UCT Black vs Random White | 9 | 1 | 0 | 90% | 59.58%-98.21% |
| Random Black vs UCT White | 0 | 10 | 0 | 0% | 0.00%-27.75% |

The cross-agent experiments gave UCT 19 wins in 20 games. This confirms that
even the small 50-iteration search budget produces substantially different and
stronger play than uniform random placement in this sample.

The self-play results do not establish a stable first- or second-player
advantage. Random self-play leaned toward P1, while the smaller UCT sample
leaned strongly toward P2. The direction changing with the policy, together
with only 20 UCT self-play games, means that a balance conclusion would be
premature. More UCT games at several iteration budgets are needed.

### Final board statistics

| Experiment | Avg secured Objectives P1/P2 | Avg Advantage Objectives P1/P2 | Avg Objective Pieces P1/P2 | Avg Supply Pieces P1/P2 |
| --- | ---: | ---: | ---: | ---: |
| Seeded Random self-play | 1.10 / 0.79 | 4.24 / 4.61 | 12.04 / 11.79 | 23.96 / 24.21 |
| UCT self-play | 2.75 / 2.90 | 3.70 / 3.40 | 14.95 / 14.90 | 21.05 / 21.10 |
| UCT Black vs Random White | 2.00 / 1.10 | 3.60 / 3.60 | 14.60 / 12.00 | 21.40 / 24.00 |
| Random Black vs UCT White | 0.80 / 2.00 | 5.00 / 3.50 | 12.30 / 13.20 | 23.70 / 22.80 |

Compared with random self-play, UCT self-play moved about three additional
Pieces per player from Supply Points to Objectives and secured roughly three
times as many Objectives. The cross-agent results show the same tendency more
weakly: UCT averaged 2.00 secured Objectives versus 0.95 for Random, and 13.90
Objective Pieces versus 12.15 for Random across the two colour assignments.

These results suggest that search can recognise the long-term value of building
supply access and converting it into concentrated Objective pressure. They also
show that the apparent game character changes with agent strength; random-only
statistics understate how often Objectives can be secured.

Per-Objective final-state rates and Piece counts are recorded in
`experiments/issue-11/results/objectives.csv`. The complete state of all 25
Supply Points and 16 Objectives is also present in every raw result row.

### Deciding criteria

| Experiment | Secured Objectives | Advantage Objectives | Objective Pieces | Draw |
| --- | ---: | ---: | ---: | ---: |
| Seeded Random self-play | 70% | 24% | 5% | 1% |
| UCT self-play | 45% | 40% | 15% | 0% |
| UCT Black vs Random White | 50% | 50% | 0% | 0% |
| Random Black vs UCT White | 70% | 30% | 0% | 0% |

All three comparison levels affected at least one self-play result. In UCT
self-play, 55% of games reached a lower tiebreak after equal secured-Objective
counts. This is initial evidence that the lexicographic scoring layers remain
strategically relevant under search, rather than only under random play.

## Reproduction

With Java 21 and the Ludii 1.3.14 JAR available, run from the repository root:

```powershell
./experiments/issue-11/scripts/run-experiments.ps1 `
    -LudiiJar C:\path\to\Ludii-1.3.14.jar

./experiments/issue-11/scripts/analyze-results.ps1
```

On a Windows system that restricts local PowerShell scripts, invoke the files
with `powershell -NoProfile -ExecutionPolicy Bypass -File` instead.

Generated evidence is stored under `experiments/issue-11/results/`:

- `raw/*.csv`: one record per game, including the complete final board
- `trials/**/*.trl`: replayable Ludii trials
- `summary.csv`: outcome and average final-board statistics
- `objectives.csv`: per-Objective state and Piece statistics
- `deciding-criteria.csv`: winning-criterion frequencies
- `analysis.json`: validation counts
- `environment.json`: versions, hashes, and source commit

## Limitations and next steps

- The 20-game UCT self-play sample is too small for a firm balance conclusion.
- The 50-iteration UCT budget is intentionally small and does not represent
  expert play.
- UCT's internal random streams prevent bit-for-bit reruns, although recorded
  trials preserve the exact experiment outcomes.
- Positional rates are exploratory and should not be interpreted as stable
  Objective values at these sample sizes.

A follow-up study should run at least 100 UCT self-play games at multiple
iteration budgets, retain colour-balanced cross-agent controls, and compare
whether the observed P2 UCT tendency persists as search strength increases.

## Conclusion

The Issue #11 acceptance criteria are satisfied:

- 140 AI-vs-AI simulations were collected and documented.
- Win rate, game length, score components, and complete final boards were
  recorded.
- Initial balance and gameplay observations were derived from both random and
  search-based play.
- Configuration, scripts, hashes, raw CSV files, and Ludii trials are available
  for reproduction and further analysis.

This work adds experiment tooling, data, and documentation only. The Heitan game
definition and rule specifications were not changed.
