# Issue 108: corrected-rule 3x3 deep UCT

## Corrected-rule primary balance

| UCT | Validated | P1 | P2 | Draw | P1 rate | Bootstrap 95% CI |
|---:|---:|---:|---:|---:|---:|---:|
| 10,000 | 100 | 63 | 26 | 11 | 63.0% | 53.0–73.0% |
| 30,000 | 100 | 54 | 33 | 13 | 54.0% | 44.0–64.0% |
| 100,000 | 100 | 40 | 47 | 13 | 40.0% | 31.0–50.0% |

Draws remain in the primary denominator. Labels below are auxiliary; point estimates and intervals are primary.

## Corrected search-depth contrasts

| Contrast | P1-rate change | Bootstrap 95% CI | Draw-rate change |
|---|---:|---:|---:|
| corrected 30k - corrected 10k | -9.0 pp | -22.0 to +5.0 pp | +2.0 pp |
| corrected 100k - corrected 30k | -14.0 pp | -28.0 to +0.0 pp | +0.0 pp |
| corrected 100k - corrected 10k | -23.0 pp | -36.0 to -9.0 pp | +2.0 pp |

## Matched historical comparisons

| UCT | Baseline | P1 difference | Bootstrap 95% CI | Draw difference |
|---:|---|---:|---:|---:|
| 10,000 | issue-105-terminal-rescore | -8.0 pp | -21.0 to +5.0 pp | +7.0 pp |
| 10,000 | issue-82-original | -8.0 pp | -21.0 to +5.0 pp | +8.0 pp |
| 30,000 | issue-105-terminal-rescore | -14.0 pp | -27.0 to -1.0 pp | +10.0 pp |
| 30,000 | issue-82-original | -16.0 pp | -29.0 to -3.0 pp | +11.0 pp |
| 100,000 | issue-105-terminal-rescore | -2.0 pp | -16.0 to +12.0 pp | +3.0 pp |
| 100,000 | issue-82-original | -3.0 pp | -16.0 to +10.0 pp | +4.0 pp |

#105 remains a terminal-rescore counterfactual and is not combined with regenerated trajectories. Differences can indicate that search-generation effects may matter, but do not identify a causal mechanism.

## Trend-shape comparison

| Depth contrast | Corrected change | Original change | Difference-in-differences | Bootstrap 95% CI |
|---|---:|---:|---:|---:|
| 100k - 30k | -14.0 pp | -27.0 pp | +13.0 pp | -6.0 to +32.0 pp |
| 100k - 10k | -23.0 pp | -28.0 pp | +5.0 pp | -14.0 to +24.0 pp |

## Preregistered interpretation

- Primary 100k drop: corrected 100k minus corrected 30k.
- Auxiliary drop label: **unresolved**.
- Search-depth classification: **unresolved**.
- The primary drop remains negative by point estimate, but its interval reaches zero; the drop label is therefore unresolved.
- No material-change label is used.

## Structural diagnostics

| UCT | Secured / Advantage / Piece / Draw decisions | Mean margins S / A / Piece | Persistent-lead games | Mean first persistent turn |
|---:|---:|---:|---:|---:|
| 10,000 | 54 / 33 / 2 / 11 | 0.39 / 0.01 / 0.01 | 89 | 10.93 |
| 30,000 | 59 / 26 / 2 / 13 | 0.36 / -0.07 / -0.24 | 87 | 10.34 |
| 100,000 | 41 / 43 / 3 / 13 | 0.13 / -0.01 / -0.08 | 87 | 15.59 |

### Late reversals

| UCT | Checkpoint turn | Eligible | Reversals | Rate |
|---:|---:|---:|---:|---:|
| 10,000 | 14 | 77 | 19 | 24.7% |
| 10,000 | 17 | 84 | 10 | 11.9% |
| 30,000 | 14 | 77 | 19 | 24.7% |
| 30,000 | 17 | 83 | 20 | 24.1% |
| 100,000 | 14 | 59 | 17 | 28.8% |
| 100,000 | 17 | 79 | 30 | 38.0% |

### Early central Supply

| Sample | UCT | Early placement frequency | Mean early placements | Mean first commitment turn |
|---|---:|---:|---:|---:|
| issue-108-corrected | 10,000 | 100.0% | 7.17 | 1.00 |
| issue-108-corrected | 30,000 | 100.0% | 7.37 | 1.00 |
| issue-108-corrected | 100,000 | 100.0% | 7.64 | 1.00 |
| issue-82-original | 10,000 | 100.0% | 7.38 | 1.00 |
| issue-82-original | 30,000 | 100.0% | 7.29 | 1.00 |
| issue-82-original | 100,000 | 100.0% | 7.67 | 1.00 |

Under the preregistered four-point central group, every P1 committed on its first turn in every tested sample. The mean early-placement count does not reproduce a reduced 100k central-Supply priority; this diagnostic is saturated and should not be over-interpreted.

## Incomplete games

No production tasks are incomplete.

These finite self-play samples do not establish convergence, optimal play, or solved-game balance.
