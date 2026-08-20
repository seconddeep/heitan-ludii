# Issue 47: Strategic convergence under deeper UCT search

## Final production sample

The UCT 100,000 production analysis is finalized at **97 validated games**. The locked plan targeted 100 games; the remaining three were not replaced and are not treated as completed. UCT 30,000 contains 100 validated games, and the existing UCT 10,000 baseline contains 100 games. The excluded pilot and all memory diagnostics are absent from these aggregates.

The uncompleted identities are game 61 (seed 571000060), game 78 (seed 571000077), game 93 (seed 571000092). They exhausted memory during 100k MCTS search. This creates a possible missing-not-at-random limitation because memory-intensive search trajectories may differ from completed games.

## Memory diagnosis and stopping decision

The excluded 10GB diagnostic failed after approximately 57 minutes. Full GC retained 10,234 MiB, showing that the live MCTS search tree, rather than reclaimable temporary objects, filled the heap. A 15.1 GiB heap dump was created. The project will not change tree retention, increase the production heap further, use a larger-memory host, or generate replacement seeds for this analysis.

## Balance

| Budget | Games | P1 wins | P2 wins | Draws | P1 win rate | 95% CI |
|---:|---:|---:|---:|---:|---:|---:|
| 10,000 | 100 | 49 | 41 | 10 | 49.0% | 39.4–58.7% |
| 30,000 | 100 | 56 | 38 | 6 | 56.0% | 46.2–65.3% |
| 100,000 | 97 | 58 | 35 | 4 | 59.8% | 49.8–69.0% |

## Supply behavior

| Budget | Games | Supply events/game | First securing turn | Immediate take | Eventual securing |
|---:|---:|---:|---:|---:|---:|
| 10,000 | 100 | 3.67 | 7.28 | 3.64% | 19.06% |
| 30,000 | 100 | 4.43 | 5.70 | 5.10% | 24.10% |
| 100,000 | 97 | 4.76 | 4.60 | 6.01% | 26.80% |

For 30k→100k, the Supply-site usage rank correlation is 0.916; the 100k top-five usage share is 58.6% and HHI is 0.1026.

The 100k full-lexicographic reversal rates are T8=48.2%, T12=38.3%, T16=35.4%, T20=36.4%.

## Frozen convergence classifications

| Metric | 10k | 30k | 100k (97 games) | Classification |
|---|---:|---:|---:|---|
| p1_win_rate | 0.4900 | 0.5600 | 0.5979 | directionally stabilizing |
| games_with_any_securing_rate | 1.0000 | 1.0000 | 1.0000 | stable / converged-looking |
| turn20_reversal_rate | 0.3956 | 0.3298 | 0.3636 | non-monotonic |

These labels apply the pre-locked mechanical rules without manual override. They describe empirical robustness across these samples; they do not establish game-theoretic convergence or solve Heitan. Numeric evidence is in `experiments/issue-47/results/final/analysis.json` and the by-depth CSV files.
