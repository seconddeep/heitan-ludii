# Issue 44 reversal-precursor prediction analysis

This directory contains the reproducible workflow for GitHub Issue #44,
"Analyze reversal precursors in Heitan." It uses the existing 100-game UCT
10,000 sample as primary evidence and the existing 100-game UCT 3,000 sample
as separate sensitivity evidence. It generates no new self-play.

## Frozen evaluation policy

All primary model specifications are frozen in `config.json` before evaluation.
Each model explicitly lists its feature columns, feature group, L2 coefficient,
standardization policy, zero-variance policy, and applicable checkpoints. The
shared L2 coefficient is fixed at 0.1 and is not selected using the reported
cross-validation results.

Cross-validation is used only for out-of-sample performance estimation. It is
not used to select features, change feature groups, tune regularization, alter
thresholds, or modify checkpoint-specific preprocessing. Univariate effect
rankings are descriptive and never feed back into a configured predictive
feature list. No post-hoc model or regularization tuning is performed from the
reported CV results.

**Primary predictive models are trained and evaluated separately for each
checkpoint. Rows from different checkpoints are not pooled into the same
primary model.** The same separation applies to the Turn 8 and Turn 12
reference analyses. A pooled checkpoint model is not part of this workflow.

Every experiment/checkpoint pair uses one deterministic, class-stratified
five-fold assignment shared by every model. Exact game-to-fold assignments are
written to `results/raw/cv-fold-assignments.csv`. Numeric standardization uses
only the training fold's population mean and standard deviation. A feature
with zero training-fold variance is excluded for that fold without inspecting
validation values. Fold preprocessing metadata is retained in
`results/raw/preprocessing-metadata.csv`.

## Frozen prediction target and features

Leaders are determined at Turns 8, 12, 16, and 20 by the full lexicographic
comparison: Secured Objectives, Advantage Objectives, then Objective Pieces.
Leader-preserved and reversal games form the binary predictive sample. Draws
and games tied at the checkpoint are retained in descriptive counts but are
excluded from model training and validation.

Features use only information available at or before their checkpoint. Recent
windows contain the previous two or four game turns, including the checkpoint
turn. State trends compare the checkpoint boundary with the boundary two or
four turns earlier. Raw P1/P2 values are retained for provenance; configured
leader-relative models do not combine raw values and their derived difference
for the same quantity.

The usable Supply-support edge definition is frozen from Issue #43:

> A usable Supply-support edge is one player-controlled-or-secured Supply
> Point × adjacent live Objective pair. Shared Objectives are counted once for
> each usable Supply adjacency.

The primary important Supply sites are S23, S21, S12, S13, and S22.

## Models and metrics

The workflow evaluates these pre-specified models independently at every
checkpoint:

- majority-class baseline;
- decisive-margin-only baseline;
- current Objective-state baseline;
- Objective-only model;
- Supply-only model;
- allocation/recent-trend model;
- combined model.

The small L2-regularized logistic regression and all metrics use only the
Python standard library. Reported metrics are ROC AUC, balanced accuracy at a
fixed 0.5 threshold, and average precision. Fold variability and aggregate
out-of-fold performance are both retained.

## Reproduction

Run from the repository root:

```sh
python3 -m unittest discover -s experiments/issue-44/scripts -p 'test_*.py'
python3 experiments/issue-44/scripts/run_analysis.py
```

The runner executes the deterministic analysis twice and confirms matching
SHA-256 hashes before writing `results/environment.json`.

## Output inventory

- `results/raw/checkpoint-prediction-features.csv`: raw P1/P2 and separately
  derived leader-relative checkpoint features;
- `results/raw/cv-fold-assignments.csv`: exact eligible game-to-fold mapping;
- `results/raw/oof-predictions.csv`: every out-of-fold probability;
- `results/raw/preprocessing-metadata.csv`: training-only means, standard
  deviations, and zero-variance decisions;
- `results/feature-comparison-summary.csv`: reversal/preserved univariate
  distributions and standardized differences;
- `results/feature-effect-summary.csv`: descriptive absolute-effect ranking;
- `results/baseline-model-summary.csv`: majority, margin, and Objective-state
  baselines;
- `results/model-validation-summary.csv`: all checkpoint-specific models;
- `results/feature-group-ablation.csv`: Objective, Supply, allocation/trend,
  and combined comparisons;
- `results/checkpoint-prediction-summary.csv`: cohort denominators;
- `results/search-strength-sensitivity.csv`: UCT 10,000/3,000 effect-direction
  comparison;
- `results/analysis.json`, `results/environment.json`, and
  `results/source-files.csv`: machine-readable findings and provenance;
- `experiments/issue-44.md`: concise result report.

## Scope

This analysis does not modify `games/Heitan.lud`, either rule specification,
game mechanics, or existing self-play data. Its findings are predictive
associations in two finite UCT self-play samples, not causal effects,
game-theoretic probabilities, or production prediction claims.
