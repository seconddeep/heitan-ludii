# Issue 68: dormant fronts and regional revisits across board sizes

## Summary

The preregistered temporal analysis supports the conclusion that larger
Heitan boards, especially 6x6, carry more unresolved regional fronts while
placement attention moves elsewhere. The result is not merely broader
spatial coverage or a longer raw revisit delay:

- dormant active fronts and unresolved backlog increase monotonically from
  3x3 through 4x4 to 6x6;
- a previous dominant-focus region remains active after a focus switch much
  more often on 6x6;
- qualifying fronts are usually revisited, including within fixed raw-turn
  and normalized follow-up windows;
- raw revisit lag is non-monotonic, and normalized revisit lag is shortest on
  6x6.

The evidence therefore describes frequent circulation among a larger set of
persisting fronts on 6x6, not simply longer abandonment caused by its longer
game. This is behavioral evidence of temporal multi-front management; it does
not by itself establish player intent or strategic optimality.

## Validation

All pinned Issue 65 inputs and all source trials passed the frozen validation
checks.

| Item | Validated total |
| --- | ---: |
| Games | 1,050 |
| Primary UCT 1000 games | 250 |
| Placements | 86,400 |
| Turns | 28,800 |
| Regional turn states | 259,200 |
| Unique trial hashes | 1,050 |
| Unique board/target region assignments | 151 |

Every input artifact matched its preregistered SHA-256. Every saved trial
matched the manifest hash. Game keys agreed across the manifest, game,
placement, and regional-state inputs. Every game ended naturally at 54/72/144
placements and 18/24/48 turns for 3x3/4x4/6x6.

Every placement had a unique game/turn/placement-number key and exactly one
of the frozen nine region labels. No target had inconsistent region labels.
For every turn, the three placement rows matched the player-by-region counts
in the nine regional states, with neither missing nor duplicate regional
allocation.

## Primary UCT 1000 results

Intervals are preregistered 95% game-bootstrap intervals. Dormancy uses the
primary threshold of two consecutive unattended turns while active.

### Dormant active fronts

| Measure | 3x3 | 4x4 | 6x6 |
| --- | ---: | ---: | ---: |
| Mean dormant fronts | 0.569 [0.527, 0.615] | 0.834 [0.792, 0.877] | 1.400 [1.340, 1.455] |
| Turns with 1+ dormant front | 44.56% [41.78, 47.44] | 58.54% [56.50, 60.67] | 78.04% [76.21, 79.88] |
| Turns with 2+ dormant fronts | 11.11% [9.39, 12.78] | 20.75% [18.71, 22.96] | 44.25% [41.54, 46.88] |
| Longest dormant run / game length | 25.22% [22.44, 28.22] | 28.71% [26.33, 31.29] | 39.21% [35.00, 43.75] |

All four measures increase monotonically. On 6x6, at least one active front
has gone unattended for two turns during more than three quarters of play,
and two or more such fronts coexist during 44% of turns.

### Concurrent unresolved backlog

Backlog counts every active region receiving no placement on the current
turn, independently of the two-turn dormancy threshold.

| Measure | 3x3 | 4x4 | 6x6 |
| --- | ---: | ---: | ---: |
| Mean backlog size | 1.287 [1.213, 1.361] | 1.752 [1.676, 1.822] | 2.770 [2.673, 2.863] |
| Mean per-game maximum | 3.050 [2.900, 3.190] | 3.870 [3.720, 4.030] | 5.400 [5.240, 5.560] |
| Turns with backlog 1+ | 74.67% [72.56, 76.72] | 83.17% [81.67, 84.67] | 92.50% [91.71, 93.29] |
| Turns with backlog 2+ | 39.00% [35.56, 42.44] | 56.96% [54.08, 59.83] | 82.04% [79.67, 84.08] |
| Longest backlog run / game length | 57.50% [53.39, 61.61] | 67.71% [63.33, 72.04] | 88.96% [86.13, 91.38] |

The 6x6 difference is large in both count and normalized persistence. It is
therefore not produced only by having 48 rather than 18 or 24 turns.

### Departure outcomes and revisits

| Measure | 3x3 | 4x4 | 6x6 |
| --- | ---: | ---: | ---: |
| Qualifying departures / game | 6.64 [6.17, 7.11] | 11.87 [11.27, 12.50] | 39.00 [37.42, 40.62] |
| Persistent revisits / game | 2.46 [2.15, 2.78] | 4.36 [3.97, 4.77] | 18.26 [17.20, 19.34] |
| Reactivation revisits / game | 1.45 [1.25, 1.67] | 3.95 [3.61, 4.31] | 15.96 [14.92, 16.98] |
| Observed revisit rate | 77.38% [73.16, 81.44] | 94.64% [92.94, 96.26] | 99.02% [98.58, 99.45] |
| Observed never-revisited rate | 22.62% [18.51, 27.00] | 5.36% [3.79, 6.98] | 0.98% [0.55, 1.42] |
| Right-censored fraction | 23.72% [20.41, 27.42] | 26.21% [24.54, 27.92] | 11.46% [10.62, 12.32] |

The pooled primary event counts were 664/1,187/1,950 cycles. Respectively,
391/831/1,711 ended in revisit, 115/47/17 ended in an observed never-revisited
state, and 158/309/222 were right-censored. Censored cycles are not included
in the observed revisit denominator.

The distinction between persistent and reactivation revisits matters. Of the
6x6 revisits, 798 followed an inactive interval with continuing opposing
Unsecured presence; treating those as continuously active would overstate
front persistence. They nevertheless represent a return to a contest that
remained mechanically unresolved.

### Revisit timing

| Measure | 3x3 | 4x4 | 6x6 |
| --- | ---: | ---: | ---: |
| Mean raw revisit lag | 3.505 [3.315, 3.702] | 4.639 [4.430, 4.858] | 4.485 [4.347, 4.623] |
| Mean lag / game length | 19.47% [18.43, 20.50] | 19.33% [18.41, 20.19] | 9.34% [9.05, 9.63] |
| Revisit within 4 turns | 51.57% [46.37, 56.49] | 49.44% [46.54, 52.39] | 59.97% [58.01, 61.83] |
| Early departure revisited within next 25% of game | 65.46% [59.50, 71.83] | 64.47% [60.16, 68.94] | 96.42% [95.25, 97.56] |

Raw lag does not increase monotonically: 4x4 is slightly longer than 6x6.
After normalization, 6x6 revisits occur in roughly half the fraction of a
game observed on 3x3 or 4x4. Both fixed-opportunity diagnostics also favor
6x6. The larger unresolved backlog therefore coexists with faster relative
cycling among fronts rather than longer relative neglect.

### Focus switches with unresolved carryover

| Measure | 3x3 | 4x4 | 6x6 |
| --- | ---: | ---: | ---: |
| Dominant-focus switches / game | 2.39 [2.04, 2.76] | 4.11 [3.67, 4.57] | 6.26 [5.56, 6.94] |
| Previous region remains active | 63.24% [55.94, 70.50] | 63.18% [57.53, 68.97] | 83.07% [78.08, 87.86] |
| Mean active carryover duration | 4.295 [3.779, 4.824] | 5.526 [4.931, 6.156] | 7.396 [6.477, 8.458] |
| Carried region later revisited | 69.16% [59.83, 77.43] | 75.79% [69.20, 82.15] | 84.38% [78.40, 89.77] |

The carryover rate is nearly identical on 3x3 and 4x4 but substantially
higher on 6x6. This directly connects Issue 65's concurrent-front result to a
temporal mechanism: stronger-search play often changes dominant region while
leaving the previous 6x6 front active, and usually returns to it later.

## Sensitivity checks

The monotonic dormant-front ordering survives both alternative thresholds.
Mean dormant-front counts for UCT 1000 are:

| Threshold | 3x3 | 4x4 | 6x6 |
| ---: | ---: | ---: | ---: |
| 1 turn | 1.287 | 1.752 | 2.770 |
| 2 turns | 0.569 | 0.834 | 1.400 |
| 3 turns | 0.201 | 0.339 | 0.587 |

At the primary two-turn threshold, the same 3x3 < 4x4 < 6x6 ordering occurs
for Seeded Random (0.930/1.259/1.692), UCT 100
(0.859/1.165/1.679), UCT 500 (0.714/0.948/1.486), and UCT 1000
(0.569/0.834/1.400). Backlog size and observed revisit rate retain the same
board ordering at every search level.

Normalized revisit lag consistently decreases toward 6x6. At the primary
threshold it is 19.49%/14.91%/8.66% for Seeded Random,
20.13%/15.99%/8.63% for UCT 100, 20.47%/18.14%/8.99% for UCT 500, and
19.47%/19.33%/9.34% for UCT 1000. This stable contradiction to a
longer-relative-delay explanation is reported as part of the primary
interpretation rather than retuned away.

## Interpretation

The supported temporal account is:

1. Larger boards sustain more unattended but still active fronts at once.
2. The unresolved backlog occupies a larger fraction of play and persists
   for a larger normalized portion of the game.
3. Focus switches on 6x6 more often leave the prior region active.
4. Those carried regions are usually revisited, and 6x6 revisits are faster
   relative to total game length.
5. The result is robust to dormancy thresholds and search-level sensitivity
   conditions.

Thus the larger-board pattern is more specific than spatial spread: play
cycles among several unresolved regional contests. The results do not
support an alternative story in which the primary difference is simply a
longer revisit delay on a longer board.

## Limitations

- The common nine-region mapping contains different numbers and mixtures of
  Supply Points and Objectives on each board.
- Primary sample sizes are unequal at 100/100/50 games.
- The active definition is operational and retains Issue 65's fixed
  four-turn, 12-placement window.
- A reactivation revisit preserves opposing Unsecured presence, but inactive
  time means it is not continuous active-front persistence.
- End-of-game right censoring differs by board and remains visible rather
  than being folded into never revisited.
- Focus switching has the Issue 65 denominator limitation: `1+1+1` turns
  have no dominant focus and break adjacency.
- UCT iteration limits do not establish convergence, optimal play, or
  deliberate intent.

## Reproduction

From the repository root, analyze the pinned Issue 65 replay outputs:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  .\experiments\issue-68\scripts\run-analysis.ps1
```

To regenerate the Issue 65 state outputs by legally replaying every saved
trial before running this analysis:

```powershell
$env:LUDII_JAR = '<path-to-Ludii-1.3.14.jar>'
powershell -NoProfile -ExecutionPolicy Bypass -File `
  .\experiments\issue-68\scripts\run-analysis.ps1 `
  -RefreshReplay -LudiiJar $env:LUDII_JAR
```

The workflow checks pinned artifacts and trial hashes, runs the analysis
tests, validates every placement-to-region allocation, writes detailed event
and turn tables, produces game-level bootstrap summaries, and records the
execution environment.
