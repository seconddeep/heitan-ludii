# Issue 65: regional independence and concurrent fronts

## Summary

Existing validated 3x3, 4x4, and 6x6 trials were replayed under the frozen
nine-region mapping to distinguish broad spatial coverage from concurrent,
semi-independent regional contests. The primary UCT 1000 comparison contains
100, 100, and 50 games respectively. Seeded Random, UCT 100, and UCT 500 were
retained as sensitivity checks.

The evidence strongly supports **more concurrent regional fronts on 6x6**.
It does not support a simple monotonic claim that regional dynamics become
progressively more statistically independent from 3x3 to 4x4 to 6x6.

The proposed description therefore needs qualification:

- 3x3 is highly coupled, but it is not predominantly single-theatre under the
  preregistered operational definitions.
- 4x4 contains interacting local situations.
- 6x6 contains more numerous, longer-lived concurrent fronts and more
  coexisting opposing local leads.
- Those 6x6 fronts remain measurably coupled; lead-dependence does not fall
  monotonically with board size.

## Validation

All configured sources passed provenance checks and legal replay:

| Item | Validated total |
| --- | ---: |
| Games | 1,050 |
| Primary UCT 1000 games | 250 |
| Placements | 86,400 |
| Three-placement turns | 28,800 |
| Regional turn states | 259,200 |
| Regional opportunity rows | 259,200 |

Every game ended naturally at its board-specific move and turn total. Every
recorded move replayed legally, every turn added exactly three Pieces, and the
reconstructed winner and score matched Ludii. Regional placement totals,
local lead reconstruction, legal-target totals, and opportunity shares were
also checked. Trial provenance, seeds, source issues, and SHA-256 hashes are
recorded in `results/trial-sources.csv`.

## Primary UCT 1000 results

Intervals below are preregistered 95% game-bootstrap intervals.

### 1. Concurrent active regions

| Measure | 3x3 | 4x4 | 6x6 |
| --- | ---: | ---: | ---: |
| Mean active regions | 2.776 [2.670, 2.886] | 3.360 [3.249, 3.478] | 4.810 [4.667, 4.945] |
| Turns with 2+ active regions | 84.72% [82.72, 86.50] | 86.38% [84.92, 87.79] | 93.04% [92.04, 93.96] |
| Longest 2+ active run / game length | 79.28% [75.83, 82.67] | 81.83% [78.54, 85.00] | 92.54% [91.21, 93.75] |

The mean active count increases at each board size, with non-overlapping
intervals. The 6x6 result is also visible in persistence: multiple active
regions coexist for most of a typical game rather than appearing only in
isolated turns.

The count of regions receiving placements from both players in the same
four-turn window is not monotonic: 1.794 on 3x3, 1.695 on 4x4, and 1.794 on
6x6. Likewise, the fraction of turns with at least two such regions is 63.22%,
57.46%, and 59.29%. The growth in active fronts is therefore not simply a
growth in regions receiving immediate investment from both players. It also
reflects unresolved opposing presence persisting while play continues in
other regions.

### 2. Coexisting opposing local leads

| Measure | 3x3 | 4x4 | 6x6 |
| --- | ---: | ---: | ---: |
| Mixed-leadership turns | 79.89% [78.72, 81.06] | 83.71% [82.67, 84.67] | 90.63% [89.71, 91.46] |
| Longest mixed-lead run / game length | 79.39% [77.94, 80.67] | 83.29% [82.21, 84.38] | 90.29% [89.29, 91.25] |
| Mean led regions | 4.811 [4.682, 4.937] | 4.833 [4.705, 4.959] | 6.560 [6.415, 6.704] |
| Mean opposing-lead breadth | 2.038 [1.973, 2.111] | 1.948 [1.880, 2.022] | 2.720 [2.632, 2.807] |

The 6x6 board much more often contains a P1-led region and a different
P2-led region at the same time. The effect is not only a longer game: both
turn fractions and normalized longest-run duration increase. This is the
clearest direct evidence that several local contests coexist.

### 3. Regional-state dependence

Dependence excess is observed absolute association minus the mean absolute
association over every non-zero circular shift of the paired second region.
Zero means no more association than the autocorrelation-preserving null.

| Series | 3x3 | 4x4 | 6x6 |
| --- | ---: | ---: | ---: |
| Local lead | 0.159 [0.149, 0.168] | 0.135 [0.122, 0.148] | 0.138 [0.114, 0.162] |
| Supply-state change | -0.008 [-0.014, -0.002] | -0.003 [-0.007, 0.001] | -0.005 [-0.010, -0.001] |
| Objective-state change | -0.023 [-0.026, -0.020] | -0.010 [-0.014, -0.007] | -0.004 [-0.006, -0.001] |

Lead trajectories remain more associated than the circular-shift null on all
boards. Dependence falls from 3x3 to 4x4, but 4x4 and 6x6 overlap and do not
form a monotonic progression. Restricting each pair to its engaged interval
gives the same conclusion: 0.142, 0.127, and 0.136.

Supply and Objective change events are close to, or slightly less associated
than, their circular-shift nulls. Objective-change excess approaches zero as
board size increases, but this does not combine with a monotonic lead result.
The dependence family therefore supports local differentiation, not a claim
that 6x6 regions are broadly independent.

### 4. Regional focus switching

| Measure | 3x3 | 4x4 | 6x6 |
| --- | ---: | ---: | ---: |
| Dominant-focus switch rate | 73.36% [66.93, 79.51] | 82.82% [78.18, 87.03] | 89.45% [85.82, 92.81] |
| Eligible adjacent-turn fraction | 18.94% [16.35, 21.41] | 21.22% [19.13, 23.30] | 14.98% [13.45, 16.47] |
| No-dominant turns | 58.00% [55.50, 60.56] | 56.83% [54.67, 58.92] | 61.63% [59.92, 63.54] |
| Mean focus persistence | 1.130 [1.095, 1.171] | 1.089 [1.067, 1.111] | 1.046 [1.031, 1.063] |
| Mean switch distance | 1.925 [1.784, 2.070] | 1.820 [1.726, 1.912] | 2.080 [1.961, 2.197] |

At UCT 1000, a defined dominant focus switches more often and persists for
less time as board size grows. However, 6x6 has the smallest eligible
denominator because `1+1+1` turns have no dominant region. Focus switching is
therefore supporting evidence, not the main basis for the conclusion. At
least one eligible adjacent pair exists in 94/100 3x3 games, 99/100 4x4
games, and 50/50 6x6 games; the rate excludes all other games and turn pairs.

## Opportunity and capacity diagnostics

The mean opportunity-adjusted activity, averaging the nine region-level
ratios within each game, is:

| 3x3 | 4x4 | 6x6 |
| ---: | ---: | ---: |
| 2.980 [2.851, 3.113] | 3.637 [3.513, 3.761] | 4.890 [4.711, 5.047] |

The monotonic active-front result remains after comparing each region's
active-turn rate with its mean share of legal target points. Region-level
capacity shares, opportunity shares, and adjusted activity are preserved in
`results/regional-activity-summary.csv`. This check argues against explaining
the 6x6 result only by larger regional capacity or more legal placement
opportunities. The ratio remains diagnostic and is not interpreted as an
independence measure.

## Sensitivity checks

The active-region ordering is unchanged for two-, four-, and six-turn recent
windows. Mean active counts for those windows are:

| Window | 3x3 | 4x4 | 6x6 |
| --- | ---: | ---: | ---: |
| 2 turns | 2.047 | 2.440 | 3.402 |
| 4 turns | 2.776 | 3.360 | 4.810 |
| 6 turns | 3.207 | 3.898 | 5.504 |

The same monotonic pattern in mean active regions and mixed leadership occurs
at Seeded Random, UCT 100, UCT 500, and UCT 1000. For example, mean active
regions on 3x3/4x4/6x6 are 3.594/4.369/5.506 for Seeded Random and
3.064/3.632/5.013 for UCT 500. Mixed-leadership turn rates are likewise
66.56%/74.79%/84.73% for Seeded Random and 77.83%/82.50%/89.04% for UCT 500.

Focus switching is less stable across strength: 4x4 exceeds 6x6 for Seeded
Random and UCT 100, while 6x6 exceeds 4x4 at UCT 500 and UCT 1000. Lead
dependence also remains non-monotonic across the sensitivity conditions.
These checks reinforce the priority given to concurrent activity and mixed
leadership over focus or a single association statistic.

## Interpretation

The coherent supported result is:

1. Larger boards, especially 6x6, sustain more active regional contests at
   once and for a larger fraction of the game.
2. Different players simultaneously lead different regions much more often
   on 6x6.
3. The activity difference survives diagnostics for static capacity and
   actual legal placement opportunity.
4. Focus shifts rapidly at stronger search, but that measure has a smaller
   eligible denominator on 6x6 and is not monotonic at weaker search.
5. Regional lead trajectories remain coupled, with no monotonic reduction in
   dependence from 3x3 through 6x6.

Thus Issue 65 supports **concurrent multi-front play on larger boards** and a
qualified notion of semi-independent fronts. It does not support the stronger
claim that 3x3 is mostly a single theatre or that statistical independence
increases monotonically at every board size.

## Limitations

- The common nine-region normalization maps different numbers and mixtures of
  Supply Points and Objectives into regions on each board.
- UCT 1000 samples are unequal: 100/100/50 games.
- The four-turn window is a fixed 12-placement comparison, not a fixed
  fraction of game length.
- Circular-shift nulls contain only 17, 23, or 47 distinct offsets on the
  three board sizes.
- The active definition is operational and combines recent investment with
  unresolved opposing presence.
- Legal opportunity is sampled at the first placement of each turn and
  deduplicated by target; it does not represent every within-turn opportunity
  after the first placement changes state.
- UCT iteration limits do not establish strategic convergence or optimal play.

## Reproduction

From the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  .\experiments\issue-65\scripts\run-analysis.ps1 `
  -LudiiJar C:\Users\verti\Ludii-1.3.14.jar
```

The command regenerates the trial manifest, legally replays all sources,
runs the analysis tests, writes every detailed and aggregate CSV, and records
the environment and source hashes.
