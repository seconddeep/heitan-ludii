# Issue 56: initial 6x6 scale analysis

## Scope and validation

The analysis used 100 seeded-Random, 50 UCT 100, and 20 UCT 500 games on
the validated 6x6 option. The comparison used the existing 100-game 4x4 data
set at each matching level. UCT 500 uses the Issue's lower sample-size bound
because a timed 6x6 smoke game took about 396 seconds.

All 470 games and 46,080 placements were replayed as legal Ludii moves. Every
game ended naturally, every turn contained exactly three placements, and the
replayed scores and winners matched. The results include no rejected or
partially completed game.

## Basic structure

| Board / agent | Games | Supply share | Objective share | Secured Supply / game | Secured Objectives / game |
| --- | ---: | ---: | ---: | ---: | ---: |
| 4x4 Random | 100 | 66.9% | 33.1% | 3.68 | 1.89 |
| 6x6 Random | 100 | 61.5% | 38.5% | 6.45 | 5.26 |
| 4x4 UCT 100 | 100 | 54.4% | 45.6% | 2.08 | 7.53 |
| 6x6 UCT 100 | 50 | 55.7% | 44.3% | 4.54 | 13.06 |
| 4x4 UCT 500 | 100 | 46.6% | 53.4% | 1.07 | 9.93 |
| 6x6 UCT 500 | 20 | 46.0% | 54.0% | 3.15 | 20.80 |

The Supply-to-Objective transition is preserved. At both board sizes, greater
search changes allocation away from Supply and toward Objectives. Secured
Supply Points also remain operational rather than merely terminal: 41.4% of
the UCT 100 and 55.6% of the UCT 500 6x6 player-Supply securing events later
supplied at least one Objective placement. The corresponding 4x4 values were
45.7% and 64.5%.

The final result continued to use all three score layers. In 6x6, the deciding
layer was Secured Objectives / Advantage Objectives / Objective Pieces in
80/16/4 Random games, 26/24/0 UCT 100 games, and 8/10/2 UCT 500 games.

## Primary spatial result: allocation within a turn

| Board / agent | One region | Two regions (2+1) | Three regions (1+1+1) | Mean regions / turn |
| --- | ---: | ---: | ---: | ---: |
| 4x4 Random | 1.25% | 26.92% | 71.83% | 2.706 |
| 6x6 Random | 1.38% | 29.83% | 68.79% | 2.674 |
| 4x4 UCT 100 | 1.75% | 33.29% | 64.96% | 2.632 |
| 6x6 UCT 100 | 1.00% | 28.17% | 70.83% | 2.698 |
| 4x4 UCT 500 | 2.13% | 34.50% | 63.38% | 2.613 |
| 6x6 UCT 500 | 1.56% | 35.94% | 62.50% | 2.609 |

UCT 100 provides positive evidence for cross-front allocation: its 6x6
three-region rate is 70.8% (game-bootstrap 95% interval 69.1--72.5%), versus
65.0% (62.9--67.0%) on 4x4. This difference also appears in every progress
quarter.

The effect is not stable across conditions. Random uses three regions slightly
less often on 6x6, and at UCT 500 the overall rates are practically the same:
62.5% (59.5--65.7%) on 6x6 and 63.4% (61.3--65.4%) on 4x4. Thus the initial
sample does not support a general claim that enlarging the board itself makes
the three placements split across more fronts.

## Secondary fixed-window result

Each fixed four-turn window contains 12 placements on either board, avoiding
the unequal cumulative placement count at equal game progress. At UCT 500,
6x6 had higher normalized entropy than 4x4 at every representative checkpoint:
0.812 vs 0.782 at 25%, 0.822 vs 0.780 at 50%, 0.817 vs 0.758 at 75%, and
0.807 vs 0.754 at 90%. Its largest-region share and HHI were correspondingly
lower at most checkpoints.

This indicates broader movement between regions across adjacent turns even
though the three placements within a single UCT 500 turn were not divided
across more regions. It is useful secondary evidence, but it does not override
the mixed primary result.

Leader reversibility was retained as a sample-limited secondary measure. Under
the full lexicographic comparison, the checkpoint leader eventually lost in
7/20 UCT 500 6x6 games at 50% progress and 4/20 at 90%, versus 41/96 and 39/95
non-tied 4x4 games. These denominators are too different and the 6x6 sample is
too small to treat this as a settled difference.

## Preliminary conclusion

The 6x6 option completes stably and clearly preserves Heitan's two-layer
Supply-to-Objective play. It also creates a broader spatial theatre over fixed
multi-turn windows. However, the central qualitative test--more allocation of
the three placements across simultaneous fronts--is positive at UCT 100 but
absent at UCT 500 and Random.

The conservative first-pass classification is therefore **promising broader
multi-turn spatial play, but not yet a demonstrated qualitatively new scale**.
At the tested shallow search strengths, it would be premature either to call
6x6 merely a stretched 4x4 or to claim that simultaneous cross-front resource
allocation has decisively emerged. A targeted follow-up should first increase
the UCT 500 sample or test somewhat stronger search; rarefaction/subsampling is
unnecessary unless the turn-level and fixed-window evidence remains ambiguous
afterward.

## Interpretation limits

- Absolute cumulative used/unused region counts and entropy are descriptive
  only because 6x6 has twice as many placements at the same progress fraction.
- The primary evidence is the per-turn `3`, `2+1`, and `1+1+1` distribution;
  normalized fixed-window metrics are secondary.
- Rarefaction/subsampling was not run.
- Seat results are recorded, but this initial sample does not establish first-
  player balance, convergence, reversal rates, or stable site rankings.
