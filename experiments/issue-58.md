# Issue 58: deeper 6x6 spatial-scaling validation

## Scope and validation

This follow-up retained the frozen Issue 56 region definitions, four-turn
window, checkpoints, metrics, bootstrap procedure, and interpretation
hierarchy. The copied `analyze-scale.mjs` has SHA-256
`08d7b7e18fe53684fe668489d65dcb04a6c6fa45c8ed31cbbe74f09a477c0355`,
identical to Issue 56. No metric-calculation logic was changed or retuned after
seeing the new games, and subsampling remained disabled.

The 6x6 UCT 500 sample combines the existing 20 Issue 56 games (seeds
`560150`--`560169`) with 30 new games (seeds `560170`--`560199`). A timed UCT
1000 smoke game took 509.846 seconds, so the practical target of 20 new games
was retained using seeds `581000`--`581019`. The full new run took 8722.490
seconds with parallelism six and Ludii Player 1.3.14.

The final comparison contains 50 6x6 and 100 4x4 UCT 500 games, plus 20 6x6
and 100 4x4 UCT 1000 games: 270 games, 24,480 placements, and 8,160 turns in
total. All 270 trials replayed as legal Ludii moves. Every game ended
naturally, every turn contained exactly three placements, and replayed scores
and winners matched the saved trials. No trial was rejected or partially
included.

## Supply-to-Objective structure

| Board / search | Games | Supply share | Objective share | Secured Supply / game | Secured Objectives / game |
| --- | ---: | ---: | ---: | ---: | ---: |
| 4x4 UCT 500 | 100 | 46.64% | 53.36% | 1.07 | 9.93 |
| 6x6 UCT 500 | 50 | 45.61% | 54.39% | 2.54 | 20.82 |
| 4x4 UCT 1000 | 100 | 45.60% | 54.40% | 1.26 | 10.66 |
| 6x6 UCT 1000 | 20 | 41.25% | 58.75% | 1.90 | 23.30 |

The two-layer structure remains clear at both search levels. Supply placement
dominates earlier play and Objective placement becomes the majority overall.
Secured Supply is operational rather than merely terminal: 71/127 (55.9%) of
6x6 UCT 500 player-Supply securing events and 22/38 (57.9%) of 6x6 UCT 1000
events supplied at least one later Objective placement. The corresponding 4x4
rates were 69/107 (64.5%) and 91/126 (72.2%). These rates describe continued
later use; the unequal sample sizes do not establish a stable board-size
difference.

## Per-turn spatial allocation

| Board / search | One region | Two regions (`2+1`) | Three regions (`1+1+1`) | Mean regions / turn |
| --- | ---: | ---: | ---: | ---: |
| 4x4 UCT 500 | 2.13% | 34.50% | 63.38% | 2.613 |
| 6x6 UCT 500 | 1.96% | 35.17% | 62.88% | 2.609 |
| 4x4 UCT 1000 | 2.75% | 40.42% | 56.83% | 2.541 |
| 6x6 UCT 1000 | 2.40% | 35.00% | 62.60% | 2.602 |

Expanding 6x6 UCT 500 from 20 to 50 games leaves the Issue 56 result
essentially unchanged. Its three-region rate is 62.88% (game-bootstrap 95%
interval 60.75--65.04%), versus 63.38% (61.25--65.42%) on 4x4. Thus 6x6 does
not produce more simultaneous three-region allocation at UCT 500.

At UCT 1000, the 6x6 three-region rate is higher: 62.60% (59.69--65.83%),
versus 56.83% (54.88--58.96%) on 4x4. The direction holds in the first three
progress quarters (70.83% vs 64.50%, 64.58% vs 57.00%, and 60.83% vs 49.83%)
but reverses slightly in the last quarter (54.17% vs 56.00%). This is positive
stronger-search evidence, but the 20-game 6x6 sample and the late-game reversal
do not justify a general claim that every phase becomes more simultaneous.

## Fixed four-turn spatial windows

Each window contains 12 placements on either board. This avoids comparing
different numbers of placements at equal progress fractions.

| Search | Board | 25% entropy | 50% entropy | 75% entropy | 90% entropy |
| --- | --- | ---: | ---: | ---: | ---: |
| UCT 500 | 4x4 | 0.782 | 0.780 | 0.758 | 0.754 |
| UCT 500 | 6x6 | 0.795 | 0.802 | 0.803 | 0.786 |
| UCT 1000 | 4x4 | 0.764 | 0.730 | 0.730 | 0.726 |
| UCT 1000 | 6x6 | 0.814 | 0.789 | 0.762 | 0.744 |

The expanded UCT 500 sample preserves the Issue 56 finding: 6x6 normalized
entropy is higher at all four representative checkpoints. Its largest-region
share and HHI are also lower at every checkpoint.

The same pattern persists at UCT 1000. The 6x6 entropy advantage is largest
at 25% and 50%, remains positive at 75%, and narrows by 90%. Largest-region
share and HHI are lower on 6x6 at all four checkpoints, although the
largest-region shares are nearly equal at 90% (0.3375 versus 0.3383). This is
consistent evidence that adjacent turns move across a broader spatial theatre
on 6x6, with the difference weakening late in the game.

## Conclusion

The targeted follow-up supports a **reproducible qualitative scaling effect in
broader multi-turn spatial play**. The effect survives expansion from 20 to 50
UCT 500 games and remains present in the stronger UCT 1000 sample under the
frozen four-turn measures.

The distinction from Issue 56 also remains important. At UCT 500, the three
placements within one turn are not distributed across more regions on 6x6,
even though adjacent turns collectively range more broadly. UCT 1000 provides
positive evidence for greater per-turn breadth as well, but that evidence is
based on only 20 6x6 games and is not present in the final progress quarter.
The supported classification is therefore specifically a stable broader
multi-turn spatial effect, not a settled claim of universally greater
simultaneous multi-front allocation or strategic convergence.

Seat balance, exact Supply rankings, reversal rates, and convergence are not
classified by this experiment. The 6x6 UCT 1000 sample is small, and its
results should be replicated before making narrower phase-specific or balance
claims.
