# Issue 43 reversal-mechanism analysis

This directory contains the reproducible workflow for GitHub Issue #43,
"Analyze reversal mechanisms in Heitan." The primary sample is the 100
`uct-10000-self-play` games; the 100 `uct-3000-self-play` games are separate
sensitivity evidence. The workflow reuses the validated Issue #37, #39, and
#41 data and generates no new self-play.

## Frozen checkpoint and timing definitions

The primary checkpoints are Turns 16 and 20; Turns 8 and 12 are reference
checkpoints. Leaders are determined by the full lexicographic comparison:
Secured Objectives, Advantage Objectives, then Objective Pieces.

- `global_strict_persistence_turn` is the first turn in the complete game after
  which the eventual winner leads at every remaining boundary. This is the
  Issue #41 strict-persistence definition.
- `post_checkpoint_takeover_turn` is defined only for a checkpoint reversal.
  It is the first turn strictly after the checkpoint at which the eventual
  winner leads at every remaining boundary.
- Lead-preserved, eventual-draw, and checkpoint-tied rows have a null
  `post_checkpoint_takeover_turn`. Global persistence remains descriptive
  context and is never substituted for checkpoint takeover.

The reversal-only aligned window uses `post_checkpoint_takeover_turn` as
relative Turn 0 and retains relative Turns -3 through +3 where available.

## Frozen usable Supply-support edge definition

**A usable Supply-support edge is one player-controlled-or-secured Supply Point × adjacent live Objective pair. Shared Objectives are counted once for each usable Supply adjacency.**

A Supply Point is usable for a player when its turn-boundary state is that
player's unsecured Control or Secured state. A live Objective has unresolved
state 0, 1, or 2 at the same boundary. Every valid adjacency pair counts:
there is no deduplication by Objective or Supply Point. Thus, if S22 supports
three live Objectives and S23 supports two, the count is five even when one
Objective is adjacent to both Supply Points. Distinct supported Objectives and
distinct usable Supply Points may be reported separately but never replace or
mix with `usable_supply_support_edges`.

Raw P1 and P2 edge counts are retained alongside checkpoint-leader-relative
and eventual-winner-relative differences in cohort and window data.

## Frozen Supply-mechanism windows

For takeover Turn `T`, the lookback is Turns `T-4` through `T-1`; its baseline
is Turns `T-8` through `T-5`. Support-edge window values are arithmetic means
across all four turn boundaries. Placement and source-usage values are means
over only the relevant player's own turns. Thresholds are fixed in
`config.json` and are not tuned after inspecting results.

Supply degradation requires at least two indicators for the checkpoint
leader: an unsecured-Control loss, a primary-important-site Control loss, a
lookback-minus-baseline support-edge mean no greater than -1, or a Supply-source
usage mean decline of at least 0.5.

Supply reinvestment requires at least two indicators for the eventual winner:
an own-turn Supply-placement mean increase of at least 0.5, a newly Secured
Supply Point, a primary-important-site Control gain, or a support-edge mean
increase of at least 1.

The primary important-site set is frozen from Issue #39 as S23, S21, S12,
S13, and S22.

## Objective mechanisms and decisive layers

`takeover_decisive_layer` is the first nonzero eventual-winner-relative
lexicographic component at checkpoint takeover. `final_decisive_layer` is the
first nonzero component at the final boundary. They are retained separately.

Objective mechanism flags record qualifying transitions between checkpoint
and takeover: neutralizing or overturning a Secured deficit; doing so on
Advantage while Secured is tied; and doing so on Objective Pieces while both
higher layers are tied. Objective and Supply mechanism flags are independent.
`mechanism_mixed` is an additional flag when at least two substantive flags
apply and never replaces them. Supporting event and threshold columns remain
in the raw cohort data.

## Perspectives and outputs

Raw P1/P2 values are never overwritten. Checkpoint-leader-relative and
eventual-winner-relative fields are added separately so sign changes are
auditable.

Run from the repository root:

```sh
python3 -m unittest discover -s experiments/issue-43/scripts -p 'test_*.py'
python3 experiments/issue-43/scripts/run_analysis.py
```

The workflow writes raw checkpoint cohorts, checkpoint-to-final windows,
reversal-aligned windows, all Issue #43 summary CSVs, `analysis.json`,
`environment.json`, and `experiments/issue-43.md`. Findings are descriptive
temporal associations, not causal claims.
