# Issue 44: Reversal precursors in Heitan

## Summary

This analysis tests whether frozen checkpoint and recent-history features distinguish leaders who are later reversed from leaders who preserve their lead. It uses 100 UCT 10,000 games as the primary sample and 100 UCT 3,000 games as separate sensitivity evidence. No new self-play was generated.

The primary sample contains modest predictive signal rather than a strong checkpoint classifier. At Turn 16 the Supply-only model has ROC AUC 0.589 and the combined model 0.561. At Turn 20 the combined model reaches 0.640, compared with 0.630 for the current Objective-state baseline. The Turn-20 combined gain beyond current Objective state is therefore small in this sample.

Models, features, L2 regularization, preprocessing, and folds were frozen before evaluation. Each checkpoint was trained and evaluated separately; univariate effects were descriptive and were not used for feature selection.

## Primary out-of-fold results

| Turn | Model | ROC AUC | Balanced accuracy | Average precision |
|---:|---|---:|---:|---:|
| 16 | majority_class | 0.500 | 0.500 | 0.487 |
| 16 | decisive_margin_only | 0.525 | 0.572 | 0.497 |
| 16 | current_objective_state | 0.407 | 0.394 | 0.439 |
| 16 | objective_only | 0.395 | 0.359 | 0.414 |
| 16 | supply_only | 0.589 | 0.525 | 0.608 |
| 16 | allocation_recent_trend | 0.483 | 0.548 | 0.530 |
| 16 | combined | 0.561 | 0.575 | 0.542 |
| 20 | majority_class | 0.500 | 0.500 | 0.444 |
| 20 | decisive_margin_only | 0.505 | 0.500 | 0.446 |
| 20 | current_objective_state | 0.630 | 0.506 | 0.517 |
| 20 | objective_only | 0.546 | 0.494 | 0.468 |
| 20 | supply_only | 0.588 | 0.589 | 0.586 |
| 20 | allocation_recent_trend | 0.629 | 0.592 | 0.517 |
| 20 | combined | 0.640 | 0.578 | 0.561 |

These values are finite-sample predictive associations. Differences among models are reported descriptively; the reported folds were not used to revise model definitions or select regularization.

## Pre-checkpoint signals

Standardized mean differences below are reversal minus lead-preserved; negative support-edge changes mean the checkpoint leader's support worsened more before games that reversed.

| Turn | Frozen feature | Reversal mean | Preserved mean | Standardized difference |
|---:|---|---:|---:|---:|
| 16 | decisive margin | 1.051 | 1.195 | -0.440 |
| 16 | leader support-edge change, 2 turns | -1.462 | -0.780 | -0.336 |
| 16 | opponent support-edge change, 2 turns | 0.103 | -0.317 | +0.159 |
| 16 | important-site Control margin | 0.436 | 0.146 | +0.233 |
| 16 | opponent Supply-allocation change | 0.154 | 0.024 | +0.427 |
| 20 | decisive margin | 1.167 | 1.267 | -0.200 |
| 20 | leader support-edge change, 2 turns | -1.056 | -0.844 | -0.107 |
| 20 | opponent support-edge change, 2 turns | 1.056 | -0.156 | +0.522 |
| 20 | important-site Control margin | 0.472 | -0.200 | +0.475 |
| 20 | opponent Supply-allocation change | 0.194 | 0.044 | +0.472 |

## Questions from the issue

- **Can later losers be distinguished?** Only modestly. The best pre-specified primary AUC is 0.589 at Turn 16 and 0.640 at Turn 20; neither supports a strong or production-ready predictor.
- **How much is in the Objective score?** The current Objective-state baseline is below chance in the Turn-16 sample (AUC 0.407) but reaches 0.630 at Turn 20. Objective information becomes more useful late, but its direction is not stable across every search-strength/checkpoint cell.
- **Does Supply add information?** At Turn 16 Supply-only exceeds the current Objective baseline (0.589 versus 0.407), and combined exceeds it (0.561 versus 0.407). At Turn 20 Supply-only is 0.588 and combined improves only slightly over the Objective baseline (0.640 versus 0.630). This is suggestive of Supply-added signal at Turn 16 and mostly complementary signal at Turn 20, not a uniform gain.
- **Do usable support edges matter?** The leader-relative two-turn support-edge trend is lower in reversals at both checkpoints (standardized differences -0.396 and -0.556). The static important-site Control margin has a positive primary effect but reverses direction in UCT 3,000, so important-site Control is not robust on its own.
- **Does recent Supply degradation appear?** Yes descriptively: checkpoint leaders in reversals lost more absolute usable support before Turn 16, and their relative support-edge trend was substantially worse before Turn 20. This is a pre-checkpoint association, not a causal degradation mechanism flag.
- **Does trailing-player Supply reinvestment warn of reversal?** The opponent's four-turn Supply-allocation increase is higher in reversal games at both checkpoints, with primary standardized differences +0.427 and +0.472. The direction agrees in UCT 3,000 at both checkpoints, although effect sizes remain sample-specific.
- **Are narrow leads fragile?** At Turn 16, 37/70 narrow leads reverse (52.9%), compared with 2/10 larger leads (20.0%). At Turn 20 the corresponding rates are 31/66 (47.0%) and 5/15 (33.3%). Narrow leads are more fragile in this primary sample.
- **Are signals stronger at Turn 20?** The combined model is stronger at Turn 20 (0.640 versus 0.561), as are the Objective and allocation/trend models. Supply-only performance is nearly unchanged, so the strengthening is not uniform across feature groups.
- **Does UCT 3,000 agree?** Only partly. Descriptive feature directions agree for 48/89 features at Turn 16 and 45/89 at Turn 20. The combined model has AUC 0.667 at both checkpoints in UCT 3,000, but several individual effects, including important-site Control, change direction. Sensitivity evidence therefore supports some recurring signal without establishing stable individual predictors.

## Integrity

- 200 complete games and 4800 game-turn boundaries were reused.
- 800 checkpoint-game rows were reconstructed.
- Issue #41 checkpoint counts and Issue #43 independently derived cohort labels were reproduced.
- Every feature uses only data at or before its checkpoint.
- Exact folds, out-of-fold predictions, and training-fold preprocessing metadata are retained.
- The runner regenerates deterministic outputs twice and records the hash comparison in `results/environment.json`.

All conclusions are predictive associations in finite UCT self-play samples. They are not causal effects, calibrated game-theoretic probabilities, or evidence that the same performance will generalize beyond these samples.

See `experiments/issue-44/README.md` for frozen definitions, output inventory, and reproduction commands.
