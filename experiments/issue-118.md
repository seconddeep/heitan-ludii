# Issue 118: corrected-rule 7x7 UCT 10k screen

Production accounting: planned=30 / validated=30 / failed=0.

Rates use validated completed games as the denominator. Failed seeds were not replaced.

## Primary 7x7 result

| UCT | Planned | Validated | Failed | P1 | P2 | Draw | P1 rate | 95% CI | Draw rate | 95% CI |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10k | 30 | 30 | 0 | 11 | 18 | 1 | 36.7% | 21.9%–54.5% | 3.3% | 0.6%–16.7% |

## Screening interpretation

1. Draw rate: 7x7 estimated 3.3% (Wilson 95% CI 0.6%–16.7%), compared with 13.0% on 4x4 and 11.0% on 3x3. The point estimate is lower, while the wide interval still includes the small-board range.
2. P1 balance: 7x7 estimated 36.7% (Wilson 95% CI 21.9%–54.5%); the interval includes parity.
3. Versus corrected 4x4: the P1-rate difference was -10.3% and the draw-rate difference was -9.7%.
4. Versus corrected 3x3: the P1-rate difference was -26.3% and the draw-rate difference was -7.7%.
5. Limited terminal scoring diagnostics are reported below; no spatial or strategic analysis was added.

## Corrected UCT 10k board-size comparison

| Board | Games | P1 rate | Draw rate |
|---|---:|---:|---:|
| 3x3 | 100 | 63.0% | 11.0% |
| 4x4 | 100 | 47.0% | 13.0% |
| 7x7 | 30 | 36.7% | 3.3% |

## Preregistered contrasts

| Contrast | Measure | Difference | Bootstrap 95% CI |
|---|---|---:|---:|
| 7x7 - 4x4 | p1 | -10.3% | -29.7%–10.0% |
| 7x7 - 4x4 | draw | -9.7% | -18.0%–0.0% |
| 7x7 - 3x3 | p1 | -26.3% | -45.7%–-6.0% |
| 7x7 - 3x3 | draw | -7.7% | -16.0%–2.0% |

## Limited terminal diagnostics

| Deciding layer | Games |
|---|---:|
| secured_objectives | 14 |
| advantage_objectives | 13 |
| objective_pieces | 2 |
| draw | 1 |

| Final margin (P1 - P2) | Minimum | Median | Maximum |
|---|---:|---:|---:|
| secured_margin_p1_minus_p2 | -2 | 0.0 | 2 |
| advantage_margin_p1_minus_p2 | -5 | 0.5 | 5 |
| corrected_objective_piece_margin_p1_minus_p2 | -9 | 0.0 | 7 |

Draw games: 1. All draw games tied at every lexicographic layer: true.

## Limitations

- 30 planned games provide a screening estimate with wide uncertainty
- UCT 10k is not a convergence claim and is not equal effective depth across board sizes
- self-play does not establish optimal play or solved balance
- board-size contrasts are descriptive and not pure causal effects
- a lower draw rate does not by itself prove that board size causes fewer draws, and a high draw rate would not by itself establish a scoring defect
