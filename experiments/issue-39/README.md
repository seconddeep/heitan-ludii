# Issue 39 Supply Point site-value analysis

This directory contains the reproducible analysis for GitHub Issue #39,
"Analyze Supply Point site value in Heitan." It reuses the legally replayed
Issue #37 data derived from the complete Issue #32 trials. It does not generate
new UCT self-play and does not modify the game definition or rule documents.

## Data sets and phases

- Primary: 100 `uct-10000-self-play` games.
- Search-strength comparison: 100 `uct-3000-self-play` games.
- Early: Turns 1-8; midgame: Turns 9-16; late: Turns 17-24.

## Frozen Control aggregation definition (version 1)

Under the game rules, a Secured Supply Point is Controlled by its owner. The
analysis preserves that relationship in `is_controlled_or_secured`, but
separates reversible unsecured Control from the permanent Secured state:

- `is_unsecured_controlled`: the turn-end state is unresolved Control by the
  player (`state_at_turn_end == player`);
- `is_secured`: the turn-end state is permanently Secured by the player
  (`state_at_turn_end == player + 2`); and
- `is_controlled_or_secured`: either of the preceding flags is true.

Consequently, every lifecycle and aggregate must satisfy:

```text
controlled_or_secured_turns = unsecured_controlled_turns + secured_turns
```

The corresponding shares use all 24 game turns for lifecycle/site summaries
and the eight turns in each phase for phase summaries. A turn after Securing
never contributes to `unsecured_controlled_turns`.

`is_neutral` means turn-end state 0, including an empty point.
`is_contested` means both players have at least one Piece at turn end,
regardless of which player Controls an unresolved point.

## Opportunity and coverage normalization

Legal Securing is reported with both denominators:

- repeated `player x Supply Point x own turn` legal opportunities and their
  same-turn take rate; and
- `game x player x Supply Point` units that were ever securable and their
  eventual Securing conversion rate.

Objective coverage is the number of distinct adjacent Objectives actually
supplied divided by that Supply Point's adjacency degree. Raw Objective counts
remain available.

## Workflow

Requirements: Python 3.9 or newer. No Ludii JAR is needed because the input is
the already validated Issue #37 replay output.

From the repository root:

```sh
python3 -m unittest discover -s experiments/issue-39/scripts -p 'test_*.py'
python3 experiments/issue-39/scripts/run_analysis.py
```

## Outputs

- `results/raw/site-turn-lifecycle.csv`
- `results/raw/site-lifecycle.csv`
- `results/site-value-summary.csv`
- `results/site-phase-summary.csv`
- `results/site-control-summary.csv`
- `results/site-securing-summary.csv`
- `results/site-usage-summary.csv`
- `results/winner-loser-site-comparison.csv`
- `results/search-strength-site-comparison.csv`
- `results/source-trials.csv`
- `results/source-files.csv`
- `results/analysis.json`
- `results/environment.json`

The narrative report is `experiments/issue-39.md`. No single composite value
score is produced: placement, unsecured Control, Secured infrastructure,
combined ownership/control, actual Supply usage, normalized Objective coverage,
competition, and outcome association remain separate dimensions.
