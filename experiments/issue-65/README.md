# Issue 65: regional independence and concurrent fronts

This directory preregisters the regional-independence analysis requested by
Issue 65. All definitions in this file and `config.json` are frozen before
the production aggregate outputs are examined. No new games are generated.

## Samples

The primary comparison is UCT 1000: 100 validated 3x3 games from Issue 62,
100 validated 4x4 games from Issue 30, and 50 validated 6x6 games from Issues
58 and 60. Seeded Random, UCT 100, and UCT 500 are sensitivity checks only.
Unequal samples are retained and uncertainty is calculated by resampling
games within each board and search level.

## Frozen regions and window

The normalized `LL`--`HH` nine-region mapping is copied from the scale
analysis: each coordinate axis is assigned to its nearest value among `1/6`,
`1/2`, and `5/6`. The primary recent-investment window is four complete
Heitan turns. Two- and six-turn windows are sensitivity checks.

At the end of turn `t`, region `r` is active/contested when:

1. at least one placement entered `r` during turns `t-3` through `t`; and
2. either both players placed in `r` during that window, or both players have
   at least one Piece on a currently Unsecured point in `r`.

The primary activity measures are active-region count, the fraction and
longest run of turns with at least two active regions, the number of regions
receiving recent investment from both players, and the fraction of turns
with at least two such regions.

## Frozen local lead and dependence definitions

The local lead is determined lexicographically from Objectives in a region:

1. Secured Objectives;
2. Advantage Objectives;
3. Pieces on Objectives.

It is encoded as `+1` for a P1 lead, `0` for a tie, and `-1` for a P2 lead.
The primary lead trajectory contains every end-of-turn value through the
natural end. Spearman correlation uses midranks of this three-valued series.
A sensitivity result restricts each region pair to the inclusive interval
from the first placement in either region through the last placement in
either region.

Supply change is `1` when any P1/P2 Controlled or Secured Supply count in the
region changes from the preceding turn, otherwise `0`. Objective change is
defined analogously from P1/P2 Advantage or Secured Objective counts. Their
pairwise association is the phi correlation. A pair is unevaluable when
either input is constant; the evaluable count and fraction out of all 36
unordered region pairs are always reported.

For every evaluable pair, the null distribution is exhaustive: keep the
lexicographically first region fixed and circularly shift the second series
by every non-zero offset. This gives 17, 23, and 47 null shifts on 3x3, 4x4,
and 6x6 respectively. Report signed and absolute observed association, null
mean and median absolute association, observed absolute minus null mean, and
the fraction of null absolute values at least as large as observed. Pair
values are averaged equally within each game. The primary board comparison is
mean dependence excess, with game-bootstrap intervals.

## Frozen mixed-lead and focus definitions

Mixed leadership occurs when P1 leads at least one region and P2 leads at
least one other region at the same turn. Report its turn fraction, longest
run, both players' led-region counts, and `min(P1-led, P2-led)`.

A dominant focus exists only when one region uniquely receives the most of a
turn's three placements. Thus `3` and `2+1` have a dominant focus and
`1+1+1` does not. The focus-switching denominator contains only adjacent
turn pairs for which both turns have a dominant focus. A no-dominant turn is
excluded from numerator and denominator, breaks persistence runs, and is not
skipped across. Report the eligible-pair count and fraction, because boards
with more `1+1+1` turns have fewer switching opportunities. Focus distance
is Manhattan distance on the normalized 3x3 region grid.

## Opportunity and capacity diagnostics

At the start of every turn, legal moves are reduced to unique target points;
different Supply sources for the same Objective count as one target.

For region `r`, turn `t`, and game `g`:

```
regional_opportunity_share(r,t)
  = legal target points in r / legal target points on the board

mean_regional_opportunity_share(r,g)
  = arithmetic mean of regional_opportunity_share over all turns

opportunity_adjusted_activity(r,g)
  = active_turn_rate(r,g) / mean_regional_opportunity_share(r,g)

regional_capacity_share(r)
  = points in r / points on the board
```

If mean opportunity share is zero, adjusted activity is `NA` and the case is
counted. These are diagnostics, not evidence of independence by themselves.

## Validation and inference

Every trial must have unique provenance and SHA-256 content, replay as legal
moves, contain exactly three placements per turn, end naturally at the
board-specific total, and reproduce its winner and independently reconstructed
score. Any failure stops the analysis.

All summary intervals are 95% percentile intervals from 2,000 game-bootstrap
replicates with seed 650065. Primary interpretation follows this order:
concurrent activity, opposing local leads, dependence excess, focus switching,
then secondary settling or phase diagnostics. No single correlation, entropy,
or opportunity-adjusted value establishes strategic independence.

## Run

```powershell
./experiments/issue-65/scripts/run-analysis.ps1 `
  -LudiiJar C:\Users\verti\Ludii-1.3.14.jar
```

Requirements: Ludii Player 1.3.14, Java 21, and Node.js 24 or later.

