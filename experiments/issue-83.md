# Issue 83: 3x3 and 4x4 first-player balance under deep UCT search

## Primary balance

| Board | UCT | Games | P1 | P2 | Draw | P1 rate | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|---:|---:|
| 3x3 | 10k | 100 | 71 | 26 | 3 | 71.0% | 61.5%–79.0% |
| 3x3 | 30k | 100 | 70 | 28 | 2 | 70.0% | 60.4%–78.1% |
| 3x3 | 100k | 100 | 43 | 48 | 9 | 43.0% | 33.7%–52.8% |
| 4x4 | 10k | 100 | 49 | 41 | 10 | 49.0% | 39.4%–58.7% |
| 4x4 | 30k | 100 | 56 | 38 | 6 | 56.0% | 46.2%–65.3% |
| 4x4 | 100k | 97 | 58 | 35 | 4 | 59.8% | 49.8%–69.0% |

## Cross-board contrasts

Positive values mean greater observed P1 advantage on 4x4.

| UCT | 4x4 - 3x3 | Bootstrap 95% CI | Games (4x4 / 3x3) |
|---:|---:|---:|---:|
| 10k | -22.0 pp | -35.0 pp to -9.0 pp | 100 / 100 |
| 30k | -14.0 pp | -27.0 pp to +0.0 pp | 100 / 100 |
| 100k | +16.8 pp | +2.6 pp to +30.9 pp | 97 / 100 |

## Search-depth trends

| Board | Contrast | P1-rate change | Bootstrap 95% CI | Draw-rate change |
|---|---|---:|---:|---:|
| 3x3 | 30k - 10k | -1.0 pp | -14.0 pp to +12.0 pp | -1.0 pp |
| 3x3 | 100k - 30k | -27.0 pp | -40.0 pp to -13.0 pp | +7.0 pp |
| 3x3 | 100k - 10k | -28.0 pp | -41.0 pp to -14.0 pp | +6.0 pp |
| 4x4 | 30k - 10k | +7.0 pp | -7.0 pp to +21.0 pp | -4.0 pp |
| 4x4 | 100k - 30k | +3.8 pp | -10.4 pp to +17.8 pp | -1.9 pp |
| 4x4 | 100k - 10k | +10.8 pp | -3.4 pp to +24.9 pp | -5.9 pp |

## Draw behavior

| UCT | 3x3 draw rate | 4x4 draw rate | 4x4 - 3x3 | Bootstrap 95% CI |
|---:|---:|---:|---:|---:|
| 10k | 3.0% | 10.0% | +7.0 pp | +1.0 pp to +14.0 pp |
| 30k | 2.0% | 6.0% | +4.0 pp | -1.0 pp to +10.0 pp |
| 100k | 9.0% | 4.1% | -4.9 pp | -11.9 pp to +2.2 pp |

## Difference in differences

The directly bootstrapped endpoint DiD is **+38.8 pp** (95% CI +19.6 pp to +58.0 pp). Every replicate independently resamples all four board-budget samples.

## Frozen classification

**非単調** (`non-monotonic`): material positive and negative contrasts both occur.

The practical-equivalence margin is ±5 percentage points. This is a descriptive, mechanically applied classification; confidence intervals are reported separately and are not treated as equivalence tests.

## Progress-based diagnostics

Late-reversal checkpoints use end-of-turn state at 75% and 90% progress: turns 14 and 17 on 3x3, and turns 18 and 22 on 4x4.

| Board | UCT | Progress | Turn | Eligible | Reversals | Rate | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|---:|---:|
| 3x3 | 10k | 75.0% | 14 / 18 | 82 | 19 | 23.2% | 15.4%–33.4% |
| 3x3 | 10k | 90.0% | 17 / 18 | 96 | 20 | 20.8% | 13.9%–30.0% |
| 3x3 | 30k | 75.0% | 14 / 18 | 85 | 17 | 20.0% | 12.9%–29.7% |
| 3x3 | 30k | 90.0% | 17 / 18 | 98 | 19 | 19.4% | 12.8%–28.3% |
| 3x3 | 100k | 75.0% | 14 / 18 | 62 | 25 | 40.3% | 29.0%–52.7% |
| 3x3 | 100k | 90.0% | 17 / 18 | 82 | 34 | 41.5% | 31.4%–52.3% |
| 4x4 | 10k | 75.0% | 18 / 24 | 80 | 26 | 32.5% | 23.2%–43.4% |
| 4x4 | 10k | 90.0% | 22 / 24 | 80 | 24 | 30.0% | 21.1%–40.8% |
| 4x4 | 30k | 75.0% | 18 / 24 | 80 | 21 | 26.2% | 17.9%–36.8% |
| 4x4 | 30k | 90.0% | 22 / 24 | 91 | 26 | 28.6% | 20.3%–38.6% |
| 4x4 | 100k | 75.0% | 18 / 24 | 78 | 23 | 29.5% | 20.5%–40.4% |
| 4x4 | 100k | 90.0% | 22 / 24 | 90 | 22 | 24.4% | 16.7%–34.2% |

## Secondary scoring diagnostics

| Board | UCT | Secured / Advantage / Pieces / Draw | Mean margins (Secured / Advantage / Pieces) |
|---|---:|---:|---:|
| 3x3 | 10k | 61 / 35 / 1 / 3 | +0.420 / +0.140 / +1.190 |
| 3x3 | 30k | 70 / 26 / 2 / 2 | +0.490 / -0.100 / +1.210 |
| 3x3 | 100k | 48 / 39 / 4 / 9 | +0.160 / +0.050 / +0.540 |
| 4x4 | 10k | 52 / 31 / 7 / 10 | +0.050 / +0.610 / +0.960 |
| 4x4 | 30k | 59 / 33 / 2 / 6 | +0.120 / +0.350 / +0.980 |
| 4x4 | 100k | 57 / 29 / 7 / 4 | +0.113 / +0.464 / +1.082 |

## Limitations

The 4x4 UCT-100k result contains 97 validated games. Games 61, 78, and 93 failed during memory-intensive MCTS and were not replaced. The missing games may be missing not at random.

Matched nominal UCT iterations do not imply equal effective depth, branching burden, memory use, or convergence quality across board sizes. These results do not identify a pure causal board-size effect, establish optimal play, or demonstrate game-theoretic convergence.

## Reproducibility

All source manifests, trials, validation artifacts, aggregate inputs, source analyses, seeds, exclusions, and hashes are pinned by `experiments/issue-83/source-lock.json`. No new self-play is included.
