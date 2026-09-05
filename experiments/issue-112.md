# Issue 112: corrected-rule 4x4 deep UCT

## Corrected-rule primary balance

| UCT | Validated | P1 | P2 | Draw | P1 rate | Bootstrap 95% CI |
|---:|---:|---:|---:|---:|---:|---:|
| 10,000 | 100 | 47 | 40 | 13 | 47.0% | 37.0–57.0% |
| 30,000 | 100 | 48 | 38 | 14 | 48.0% | 38.0–58.0% |
| 100,000 | 100 | 55 | 31 | 14 | 55.0% | 45.0–65.0% |

Draws remain in the primary denominator. Labels below are auxiliary; point estimates and intervals are primary.

## Corrected search-depth contrasts

| Contrast | P1-rate change | Bootstrap 95% CI | Draw-rate change |
|---|---:|---:|---:|
| corrected 30k - corrected 10k | +1.0 pp | -13.0 to +15.0 pp | +1.0 pp |
| corrected 100k - corrected 30k | +7.0 pp | -7.0 to +21.0 pp | +0.0 pp |
| corrected 100k - corrected 10k | +8.0 pp | -6.0 to +22.0 pp | +1.0 pp |

## Matched historical comparisons

| UCT | Baseline | P1 difference | Bootstrap 95% CI | Draw difference |
|---:|---|---:|---:|---:|
| 10,000 | issue-105-terminal-rescore | -3.0 pp | -17.0 to +11.0 pp | +5.0 pp |
| 10,000 | issue-83-historical-original | -2.0 pp | -16.0 to +12.0 pp | +3.0 pp |
| 30,000 | issue-105-terminal-rescore | -10.0 pp | -24.0 to +4.0 pp | +11.0 pp |
| 30,000 | issue-83-historical-original | -8.0 pp | -21.0 to +6.0 pp | +8.0 pp |
| 100,000 | issue-105-terminal-rescore | -1.7 pp | -15.9 to +12.4 pp | +6.8 pp |
| 100,000 | issue-83-historical-original | -4.8 pp | -18.9 to +8.4 pp | +9.9 pp |

#105 remains a terminal-rescore counterfactual and is not combined with regenerated trajectories. Differences can indicate that search-generation effects may matter, but do not identify a causal mechanism.

## Trend-shape comparison

| Depth contrast | Corrected change | Original change | Difference-in-differences | Bootstrap 95% CI |
|---|---:|---:|---:|---:|
| 100k - 30k | +7.0 pp | +3.8 pp | +3.2 pp | -15.9 to +22.4 pp |
| 100k - 10k | +8.0 pp | +10.8 pp | -2.8 pp | -22.0 to +16.4 pp |

## Corrected 4x4 versus corrected 3x3

| UCT | P1-rate difference (4x4 - 3x3) | Bootstrap 95% CI |
|---:|---:|---:|
| 10,000 | -16.0 pp | -30.0 to -3.0 pp |
| 30,000 | -6.0 pp | -20.0 to +8.0 pp |
| 100,000 | +15.0 pp | +1.0 to +28.0 pp |

Matched nominal UCT iterations are not interpreted as equal effective search depth across board sizes.

## Preregistered interpretation

- Primary depth contrast: corrected 100k minus corrected 30k.
- Historical-pattern label: **unresolved**.
- Search-depth classification: **monotonic but unresolved**.
- No material-change label is used.

## Structural diagnostics

| UCT | Secured / Advantage / Piece / Draw decisions | Mean margins S / A / Piece | Persistent-lead games | Mean first persistent turn |
|---:|---:|---:|---:|---:|
| 10,000 | 55 / 25 / 7 / 13 | 0.13 / 0.37 / 0.44 | 87 | 20.22 |
| 30,000 | 61 / 21 / 4 / 14 | 0.08 / 0.60 / 0.70 | 86 | 19.07 |
| 100,000 | 61 / 18 / 7 / 14 | 0.34 / 0.06 / -0.10 | 86 | 19.01 |

### Late reversals

| UCT | Checkpoint turn | Eligible | Reversals | Rate |
|---:|---:|---:|---:|---:|
| 10,000 | 18 | 74 | 24 | 32.4% |
| 10,000 | 22 | 83 | 22 | 26.5% |
| 30,000 | 18 | 79 | 21 | 26.6% |
| 30,000 | 22 | 76 | 23 | 30.3% |
| 100,000 | 18 | 74 | 19 | 25.7% |
| 100,000 | 22 | 82 | 14 | 17.1% |

### Supply allocation

| UCT | Mean first securing turn | Mean final Secured Supplies | Supply placement share | Objective placement share |
|---:|---:|---:|---:|---:|
| 10,000 | 7.24 | 3.85 | 51.2% | 48.8% |
| 30,000 | 5.92 | 4.26 | 51.8% | 48.2% |
| 100,000 | 4.99 | 4.51 | 53.1% | 46.9% |

## Incomplete games

No production tasks are incomplete.

#105 terminal rescoring remains separate from regenerated trajectories. These finite self-play samples do not establish convergence, optimal play, or solved-game balance.
