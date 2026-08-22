# Issue 82: 3x3 deep-UCT first-player balance

## Primary balance

| UCT | Validated | P1 | P2 | Draw | P1 rate | Wilson 95% CI |
|---:|---:|---:|---:|---:|---:|---:|
| 10,000 | 100 | 71 | 26 | 3 | 71.0% | 61.5–79.0% |
| 30,000 | 100 | 70 | 28 | 2 | 70.0% | 60.4–78.1% |
| 100,000 | 100 | 43 | 48 | 9 | 43.0% | 33.7–52.8% |

The unconditional P1 rate retains draws in its denominator. Decisive-game shares are secondary and are available in the CSV.

## Search-depth contrasts

| Contrast | P1-rate change | 95% CI | Draw-rate change |
|---|---:|---:|---:|
| 30k - 10k | -1.0 pp | -13.5 to +11.5 pp | -1.0 pp |
| 100k - 30k | -27.0 pp | -39.3 to -13.3 pp | +7.0 pp |
| 100k - 10k | -28.0 pp | -40.2 to -14.3 pp | +6.0 pp |

## Empirical stability

**unresolved**

This label applies the unchanged Issue #47 thresholds mechanically. It describes robustness across these samples only; it does not establish optimal play or solved-game balance.

## Incomplete games

No production games failed.

## Scope

This result is a 3x3 deep-search baseline. It makes no cross-board balance claim. Secondary structural diagnostics are reported separately and do not redefine the primary conclusion.
