# Issue 60: replicate 6x6 UCT 1000 spatial allocation

## Scope, execution, and validation

This follow-up expanded the 6x6 UCT 1000 sample from 20 to 50 games without
regenerating the Issue 58 games. The reused games have indices 1--20 and seeds
`581000`--`581019`; the 30 Issue 60 games have indices 21--50 and seeds
`581020`--`581049`. The existing 100-game 4x4 UCT 1000 sample from Issue 30
remains the comparison group.

The new games were generated with Ludii Player 1.3.14. Two command invocations
reached the one-hour execution limit, so the experiment used the provenance-
checked resume path and retained only completed games. The three segments took
9929.087 seconds in total. All 30 new games ended naturally with 144 placements
and 48 turns.

`results/trial-sources.csv` records source issue, index, seed, trial path, and
trial SHA-256 for every analyzed game. It contains 20 Issue 58 trials, 30
Issue 60 trials, and 100 Issue 30 trials. The reused and new 6x6 trials share
`experiment_id=6x6-uct-1000`, so they form one 50-game analysis group while
retaining per-trial provenance.

All 150 trials replayed as legal Ludii moves. Replayed winners and scores
matched the saved trials, every turn contained exactly three placements, and
there were no duplicate analysis keys or duplicate trial hashes. The final
analysis contains 14,400 placements and 4,800 turns.

## Frozen analysis

The Issue 60 analysis was not retuned. These analysis-side files are
byte-for-byte identical to Issue 56:

| File | SHA-256 |
| --- | --- |
| `analyze-scale.mjs` | `08d7b7e18fe53684fe668489d65dcb04a6c6fa45c8ed31cbbe74f09a477c0355` |
| `analyze-scale.test.mjs` | `fa2df107d616e70975fd7405e66e1e9ce4fdb65677a728baeb62710968f3d4e4` |
| `HeitanScaleReplay.java` | `963755c9067b4827f97ab87a6e522ab850e3b036de3d603e897dba84f1cb7ded` |

The experiment runner has SHA-256
`a0a0d6a58488e04e84cffd45526630e429eaad23f1b4e445a30b99dfc4f8b88f`.
Its only Java change from Issue 58 replaces repository-root `toRealPath()`
with lexical absolute-path normalization for recording relative trial paths.
Game generation, AI, seed, index, scoring, and validation logic are unchanged.

## Per-turn spatial allocation

| Board | Games | One region | Two regions (`2+1`) | Three regions (`1+1+1`) | Mean regions / turn |
| --- | ---: | ---: | ---: | ---: | ---: |
| 4x4 UCT 1000 | 100 | 2.75% | 40.42% | 56.83% | 2.541 |
| 6x6 UCT 1000 | 50 | 2.04% | 36.33% | 61.63% | 2.596 |

The expanded 6x6 three-region rate is 61.63%, with a frozen game-bootstrap
95% interval of 59.75--63.46%. The corresponding 4x4 rate is 56.83%
(54.88--58.96%). The 6x6 advantage is 4.79 percentage points, and the two
reported intervals do not overlap. The 50-game estimate is close to the
62.60% result from the original 20-game sample rather than collapsing toward
the 4x4 rate. Mean regions per turn is also higher by 0.055.

| Progress band | 4x4 three-region | 6x6 three-region | 6x6 minus 4x4 |
| --- | ---: | ---: | ---: |
| 0--25% | 64.50% | 69.17% | +4.67 pp |
| 25--50% | 57.00% | 64.00% | +7.00 pp |
| 50--75% | 49.83% | 62.00% | +12.17 pp |
| 75--100% | 56.00% | 51.33% | -4.67 pp |

The direction therefore replicates overall and in the first three progress
quarters. As in Issue 58, it reverses in the final quarter. The evidence does
not support a claim that every phase becomes more simultaneous.

## Fixed four-turn spatial windows

| Checkpoint | 4x4 entropy | 6x6 entropy | 4x4 largest share | 6x6 largest share | 4x4 HHI | 6x6 HHI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 25% | 0.764 | 0.808 | 0.306 | 0.282 | 0.213 | 0.192 |
| 50% | 0.730 | 0.789 | 0.335 | 0.292 | 0.234 | 0.199 |
| 75% | 0.730 | 0.761 | 0.337 | 0.310 | 0.233 | 0.212 |
| 90% | 0.726 | 0.753 | 0.338 | 0.332 | 0.234 | 0.223 |

The broader multi-turn effect is consistent at all four checkpoints: 6x6 has
higher normalized entropy, lower largest-region share, and lower HHI. The
largest-region difference again narrows late but does not reverse at 90%.

## Supply-to-Objective structure

| Board | Supply share | Objective share | Secured Supply / game | Secured Objectives / game | Later-use rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| 4x4 UCT 1000 | 45.60% | 54.40% | 1.26 | 10.66 | 72.22% |
| 6x6 UCT 1000 | 40.86% | 59.14% | 1.74 | 23.44 | 56.32% |

Secured Supply remains operational: 49 of 87 secured player-Supply events in
the 6x6 sample supplied at least one later Objective placement. These unequal
sample sizes do not establish a stable board-size difference in conversion.

## Conclusion

The larger sample supports interpretation 1: **at UCT 1000, 6x6 shows both
broader multi-turn spatial play and greater simultaneous multi-front
allocation within a turn**. The per-turn effect remains close to the original
20-game estimate after expansion to 50 games, while every frozen four-turn
measure continues to favor broader 6x6 play.

The conclusion is qualified by the late-game reversal in three-region
allocation. It is an overall and early-to-midgame result, not evidence of a
universal phase-by-phase effect. It also remains specific to UCT 1000 and the
available sample. Seat balance, exact Supply rankings, reversal rates, and
strategic convergence are not classified by this experiment.
