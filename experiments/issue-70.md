# Issue 70: front selection and late-game concentration on 6x6

## Summary

The preregistered analysis does **not** support the proposed strong pattern in
which broad 6x6 multi-front play contracts into a substantially smaller set of
maintained fronts late in the game.

At UCT 1000, active, dormant, and unattended fronts all remain broad or grow
through the final progress band. Placement does become mildly more
concentrated from the third to the fourth band on 6x6, but the change is small,
is not stronger than early-game opportunity-adjusted concentration, and is not
stable across search levels. There is evidence of selective abandonment of
some individual fronts, but 94.5% of earlier-active regions still receive
investment in the final band.

Late Objective play is also not well described as uniformly mechanical.
About one third of 6x6 late Objective placements occur in a region whose local
outcome is already conservatively fixed, but 89% change the target state, 42%
contribute to securing, 17% change the current global comparison, and the
global outcome remains mutable under the conservative bound before more than
99% of those placements.

## Validation

All configured Issue 65 trials and inputs passed the frozen provenance and
replay checks.

| Item | Validated total |
| --- | ---: |
| Games | 1,050 |
| Primary UCT 1000 games | 250 |
| Placements | 86,400 |
| Turns | 28,800 |
| Objective placements | 39,371 |
| Final-band Objective placements | 11,895 |

Every trial hash matched, every recorded move replayed legally, each turn
contained exactly three placements, every game ended naturally at its
board-specific length, and replayed winners and independently reconstructed
scores matched Ludii.

Remaining pieces were calculated without using Ludii stock state:

```
R[p] = board_piece_count_per_player - placements_by_player_so_far
```

`R[p]` stayed non-negative at every snapshot and reached zero for both players
at natural game end.

## Primary UCT 1000 results

All intervals are preregistered 95% game-bootstrap intervals.

### 1. Maintained fronts do not contract late

| Board | Band | Active fronts | Dormant fronts | Unresolved backlog | Decline from game peak |
| --- | ---: | ---: | ---: | ---: | ---: |
| 3x3 | 0--25% | 1.378 [1.273, 1.483] | 0.083 [0.058, 0.108] | 0.375 [0.323, 0.425] | 3.243 [3.008, 3.453] |
| 3x3 | 75--100% | 3.384 [3.196, 3.566] | 0.760 [0.670, 0.850] | 1.590 [1.454, 1.726] | 1.236 [1.084, 1.390] |
| 4x4 | 0--25% | 1.715 [1.600, 1.832] | 0.292 [0.243, 0.338] | 0.762 [0.693, 0.830] | 4.035 [3.865, 4.212] |
| 4x4 | 75--100% | 4.315 [4.152, 4.488] | 1.177 [1.093, 1.267] | 2.327 [2.202, 2.453] | 1.435 [1.292, 1.583] |
| 6x6 | 0--25% | 2.743 [2.547, 2.938] | 0.625 [0.550, 0.698] | 1.395 [1.270, 1.520] | 4.777 [4.522, 5.047] |
| 6x6 | 75--100% | 5.685 [5.465, 5.888] | 1.757 [1.655, 1.850] | 3.342 [3.172, 3.502] | 1.835 [1.665, 2.010] |

The primary 6x6 mean active count is 5.652 in the third band and 5.685 in the
fourth, rather than declining. Raw-turn reporting agrees: the final eight
turns remain near 5.6--5.9 active fronts, ending at 5.80. The decreasing
distance from each game's peak also shows that late play is closer to peak
front breadth, not farther from it.

### 2. Individual abandonment exists without broad contraction

The cohort is every region active at least once through 75% progress. Rates
below average games equally and use the primary four-complete-turn censoring
rule.

| Measure | 3x3 | 4x4 | 6x6 |
| --- | ---: | ---: | ---: |
| Receives final-band investment | 70.32% [66.73, 74.08] | 76.81% [73.70, 79.69] | 94.54% [92.22, 96.55] |
| Mechanically closed | 11.92% [9.67, 14.13] | 1.00% [0.27, 1.94] | 0.00% [0.00, 0.00] |
| Resolved or settled | 80.80% [77.78, 83.69] | 81.32% [78.09, 84.50] | 76.60% [72.47, 80.79] |
| End-censored | 5.56% [3.56, 7.54] | 8.81% [6.70, 10.93] | 11.77% [8.87, 14.88] |
| Selectively abandoned | 1.72% [0.75, 2.79] | 8.87% [6.73, 10.91] | 11.63% [8.79, 14.53] |

The exclusive ordering was
`mechanically_closed -> resolved_or_settled -> end_censored -> selectively_abandoned`.
Thus the 6x6 result contains genuine selective abandonment, but it coexists
with very high final-band survival and an increasing maintained-front count.
It supports selection among some regions, not overall contraction to a narrow
late-game theatre.

### 3. Opportunity-adjusted concentration is only mildly late-peaked

| Board | Band | Entropy gap | HHI gap | Regions receiving placements |
| --- | ---: | ---: | ---: | ---: |
| 3x3 | 0--25% | -0.260 [-0.279, -0.239] | 0.118 [0.105, 0.132] | 5.52 [5.31, 5.73] |
| 3x3 | 75--100% | -0.164 [-0.183, -0.146] | 0.072 [0.062, 0.083] | 6.42 [6.21, 6.63] |
| 4x4 | 0--25% | -0.155 [-0.167, -0.142] | 0.065 [0.059, 0.071] | 7.24 [7.05, 7.43] |
| 4x4 | 75--100% | -0.155 [-0.170, -0.141] | 0.067 [0.060, 0.075] | 7.13 [6.93, 7.32] |
| 6x6 | 0--25% | -0.087 [-0.101, -0.074] | 0.038 [0.033, 0.045] | 8.44 [8.22, 8.64] |
| 6x6 | 50--75% | -0.068 [-0.076, -0.060] | 0.030 [0.026, 0.033] | 8.68 [8.54, 8.80] |
| 6x6 | 75--100% | -0.082 [-0.094, -0.069] | 0.036 [0.030, 0.041] | 8.46 [8.26, 8.64] |

The gaps are actual placement concentration minus turn-start legal-opportunity
concentration. Negative entropy and positive HHI gaps show non-uniform choice
beyond opportunity alone. On 6x6, placement narrows slightly from the third
to fourth band, but the fourth-band gaps remain comparable to or smaller than
the first-band gaps. This is not a general late concentration effect.

### 4. Late Objective placements remain mostly consequential

| Measure | 3x3 | 4x4 | 6x6 |
| --- | ---: | ---: | ---: |
| Objective placements / game | 6.54 [6.10, 7.01] | 9.64 [9.10, 10.16] | 24.98 [23.86, 26.06] |
| Changes target state | 82.07% [78.79, 85.04] | 84.63% [81.50, 87.46] | 88.94% [87.41, 90.44] |
| Changes local lead | 33.43% [30.01, 36.97] | 17.68% [15.35, 20.19] | 8.64% [6.70, 10.70] |
| Contributes to securing | 41.54% [37.68, 45.42] | 38.08% [35.18, 40.86] | 42.41% [39.52, 45.07] |
| Changes global comparison | 12.71% [9.44, 16.28] | 15.39% [12.82, 18.02] | 17.47% [14.94, 19.80] |
| Global result still mutable before move | 95.78% [93.93, 97.46] | 98.23% [96.83, 99.43] | 99.64% [99.28, 99.92] |
| Region already fixed before move | 4.46% [2.81, 6.28] | 28.06% [24.29, 31.83] | 33.02% [28.58, 37.39] |

The fixed-outcome test gives the challenger every remaining Piece on any
unsecured Objective within its per-player three-piece capacity, ignores only
Supply access, and gives the opponent no future contribution. A fixed result
is therefore conservative. The 6x6 local-fixed rate reveals a real mechanical
or locally settled component, while the other measures reject treating the
whole Objective-heavy endgame as passive filling.

## Sensitivity checks

- Mean active fronts increase from the third to fourth band for Seeded Random,
  UCT 100, and UCT 1000 on 6x6. UCT 500 shows only a small decline, from 5.923
  to 5.853. A stable contraction pattern is absent.
- The 6x6 HHI opportunity gap falls from band three to four for Seeded Random,
  UCT 100, and UCT 500, but rises from 0.0296 to 0.0356 at UCT 1000. Late
  concentration is search-level dependent.
- Under the primary censor rule, selective abandonment increases monotonically
  by board size at every search level. At UCT 1000 it is 1.72%/8.87%/11.63%.
- For UCT 1000, 6x6 selective abandonment is 8.77% with the `<10%` censor and
  3.40% with `<20%`. The stronger censor removes much of the apparent late
  abandonment and no longer preserves a 3x3 < 4x4 < 6x6 ordering.
- Raw-turn front trajectories agree with normalized bands and do not reveal a
  hidden final-turn collapse.

## Interpretation

The evidence supports the following qualified account:

1. Larger boards, especially 6x6, continue to carry a broad unresolved front
   backlog into the endgame.
2. Some 6x6 regions are selectively abandoned more often than on smaller
   boards, but this is a minority pattern within otherwise broad late play.
3. Placement narrows modestly after the broadest third-band phase at UCT 1000,
   yet the opportunity-adjusted effect is not stronger than earlier play and
   is not robust across search strengths.
4. Late Objective play mixes locally settled filling with consequential moves;
   the global comparison is almost always still conservatively mutable.

Therefore Issue 70 does not establish a general strategic contraction from
many fronts to a small chosen subset. It instead finds continued multi-front
play with selective pruning at the margins and a mixed consequential/mechanical
Objective endgame.

## Limitations

- The common nine-region mapping contains different point counts and mixtures
  on each board.
- Primary samples are unequal at 100/100/50 games.
- The active definition retains a fixed four-turn rather than normalized-time
  window.
- Turn-start opportunities deduplicate legal targets and do not weight
  alternative Supply sources or later within-turn choices.
- The conservative fixed bound proves some outcomes fixed but intentionally
  leaves many practically settled positions classified as mutable.
- Final-band survival and post-final-placement abandonment are different
  measures: a region can receive a late placement and then be abandoned.
- UCT iteration limits do not establish convergence, optimal play, or intent.

## Reproduction

From the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  .\experiments\issue-70\scripts\run-analysis.ps1 `
  -LudiiJar C:\Users\verti\Ludii-1.3.14.jar
```

The command verifies pinned inputs and trial hashes, legally replays all saved
trials, tests the classification and bound calculations, regenerates detailed
and aggregate CSV files, and records the execution environment.
