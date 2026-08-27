# Issue 105: corrected Objective-piece tiebreak impact

## Scope and gate

This is a read-only counterfactual rescore of the 597 validated games frozen by Issue #83 plus 1,940 non-duplicate retained completed games from earlier Random, UCT, and board-scale datasets.
No source trial was modified and no self-play was generated.

The previous-winner reconstruction gate passed **597 / 597** games. The corrected comparison is therefore enabled.
A failed reconstruction would have been retained as `unresolved` and would have blocked this comparison.

## Corrected definition

The corrected third tiebreak counts only a player's own pieces on Objectives where that player has Advantage.
It excludes own-Secured, opponent-Secured, opponent-Advantage, and neutral Objective pieces.

Own-Secured pieces are not dead pieces. At the third tiebreak, Secured counts are tied and each own-Secured
Objective contributes exactly three pieces, so both players add the same `3 × Secured count` and no margin.

## Direct terminal-result impact

In the minimum sample, 57 of 597 games reached the third tiebreak, 21 of those games changed the third-tiebreak margin, and 20 recorded outcomes changed
when the same terminal positions were rescored.

| Board | UCT | Games | Reach third | Winner changes | Original P1/P2/D | Corrected P1/P2/D |
|---|---:|---:|---:|---:|---:|---:|
| 3x3 | 10k | 100 | 4 | 1 | 71/26/3 | 71/25/4 |
| 3x3 | 30k | 100 | 4 | 3 | 70/28/2 | 68/29/3 |
| 3x3 | 100k | 100 | 13 | 1 | 43/48/9 | 42/48/10 |
| 4x4 | 10k | 100 | 17 | 9 | 49/41/10 | 50/42/8 |
| 4x4 | 30k | 100 | 8 | 3 | 56/38/6 | 58/39/3 |
| 4x4 | 100k | 97 | 11 | 3 | 58/35/4 | 55/35/7 |

The 20 changed minimum-sample outcomes comprise 1 P1->P2, 0 P2->P1, 10 win->draw, and 9 draw->win transitions.

The corrected counts above are counterfactual terminal-state results on old trajectories. They are not corrected-rule UCT production results.

## Extended retained-data audit

The same reconstruction completed for all 2,537 selected games across 3x3, 4x4, 6x6, and 7x7 datasets. Across that combined scope, 285 games reached the third tiebreak and 143 recorded outcomes changed. Dataset-level results remain separated by source issue and experiment ID in the machine-readable summaries.

## Impact interpretation

1. Direct terminal impact is recorded in `per-game-scoring.csv` and the dataset summaries.
2. Derived metrics can be recomputed from retained trajectories as listed in `affected-analysis-inventory.csv`.
3. UCT search-generation impact cannot be inferred from terminal rescoring; the old result may have changed value propagation and move selection.

## Rerun recommendation

Prioritize corrected-rule deep UCT in this order: (1) the Issue #82/#83 3x3 and 4x4 balance families, including Issue #47 sources; (2) earlier 3x3/4x4 convergence families; (3) 6x6/7x7 scaling families; and (4) trajectory-derived reversal and spatial analyses after their source families are regenerated. The 3x3 deep-UCT rerun remains a separate follow-up issue.
