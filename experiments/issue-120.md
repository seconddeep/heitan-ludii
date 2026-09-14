# Issue 120: corrected-rule 7x7 UCT 30k follow-up

Production accounting: planned=30 / validated=30 / failed=0. `corrupt` tasks are included in failed.

Rates retain draws in the validated-game denominator. Failed seeds were not replaced.

## Primary 7x7 30k result

| UCT | Planned | Validated | Failed | P1 | P2 | Draw | P1 rate | 95% CI | Draw rate | 95% CI |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 30k | 30 | 30 | 0 | 6 | 20 | 4 | 20.0% | 9.5%–37.3% | 13.3% | 5.3%–29.7% |

## 7x7 depth comparison

| UCT | Validated | P1 rate | Draw rate |
|---:|---:|---:|---:|
| 10k | 30 | 36.7% | 3.3% |
| 30k | 30 | 20.0% | 13.3% |

## Primary depth contrasts

| Contrast | Measure | Difference | Bootstrap 95% CI |
|---|---|---:|---:|
| 30k - 10k | p1 | -16.7% | -40.0%–6.7% |
| 30k - 10k | draw | 10.0% | -3.3%–23.3% |

## Directional interpretation

The 30k P1 estimate is 20.0%; the independent 30k - 10k difference is -16.7%.
The 30k draw estimate is 13.3%; the independent 30k - 10k difference is 10.0%.
These finite-sample point estimates and intervals are directional evidence, not convergence classifications.

## Secondary corrected UCT 30k board-size context

| Board | Games | P1 rate | Draw rate |
|---|---:|---:|---:|
| 3x3 | 100 | 54.0% | 13.0% |
| 4x4 | 100 | 48.0% | 14.0% |
| 7x7 | 30 | 20.0% | 13.3% |

| Contrast | Measure | Difference | Bootstrap 95% CI |
|---|---|---:|---:|
| 7x7 - 4x4 | p1 | -28.0% | -44.7%–-10.7% |
| 7x7 - 4x4 | draw | -0.7% | -13.7%–14.0% |
| 7x7 - 3x3 | p1 | -34.0% | -50.7%–-15.7% |
| 7x7 - 3x3 | draw | 0.3% | -12.7%–15.3% |

## Limited terminal diagnostics

| Deciding layer | Games |
|---|---:|
| secured_objectives | 12 |
| advantage_objectives | 11 |
| objective_pieces | 3 |
| draw | 4 |

| Final margin (P1 - P2) | Minimum | Median | Maximum |
|---|---:|---:|---:|
| secured_margin_p1_minus_p2 | -2 | 0.0 | 2 |
| advantage_margin_p1_minus_p2 | -3 | 0.0 | 5 |
| corrected_objective_piece_margin_p1_minus_p2 | -6 | 0.0 | 9 |

Draw games: 4. All draw games tied at every lexicographic layer: true.

## Limitations

- 30 planned games provide a relatively wide estimate
- UCT 30k does not establish convergence, optimal play, or solved balance
- the 7x7 UCT 10k and 30k samples are independent finite self-play samples
- nominal UCT 30k does not represent equal effective depth across board sizes
- board-size comparisons are descriptive rather than pure causal effects
- a 10k-to-30k change does not identify the strategic mechanism causing it
