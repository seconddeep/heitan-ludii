# Issue 41 game-state progression analysis

This directory contains the reproducible workflow for GitHub Issue #41,
"Analyze game-state progression and decision timing in Heitan." It reuses the
legally replayed Issue #37 turn states from the complete Issue #32 trials and
the Issue #39 site-value evidence. It does not generate new self-play or modify
the game definition or rule specifications.

## Data sets and analysis unit

- Primary: 100 `uct-10000-self-play` games.
- Search-strength comparison: 100 `uct-3000-self-play` games.
- Unit: every completed turn boundary from Turn 1 through Turn 24.
- All three victory components are retained separately; an opaque scalar score
  is not used by this analysis.

## Frozen comparison layers

Differences are P1 minus P2. Each layer is compared lexicographically in the
listed order:

1. `secured`: Secured Objectives only;
2. `secured_advantage`: Secured Objectives, then Advantage Objectives; and
3. `full_lexicographic`: Secured Objectives, Advantage Objectives, then Pieces
   on Objectives.

The sign is positive for a P1 lead, negative for a P2 lead, and zero for a tie
under that layer.

## Frozen persistence definitions

For every decisive game and every comparison layer, two winner-based measures
are stored separately:

- `strict_persistent_lead_turn` is the earliest turn after which the eventual
  winner has a strictly positive winner-relative lead at every remaining turn
  boundary. Neither equality nor an opponent lead is allowed later.
- `nonlosing_persistence_turn` is the earliest turn after which the eventual
  winner is never behind at any remaining turn boundary. Equality is allowed;
  an opponent lead is not.

`last_lead_change_turn` is a different, winner-independent concept: it is the
last turn on which the non-zero leader differs from the most recent prior
non-zero leader. Equality does not itself name a leader. Thus `P1, tie, P1`
has no lead-side change, while `P1, tie, P2` changes on the P2-leading turn.

Temporary equality and later lead recovery mean `last_lead_change_turn`,
`strict_persistent_lead_turn`, and `nonlosing_persistence_turn` need not be the
same. A persistence value may also be null for a layer: for example, a game
decided by Objective Pieces can finish tied on the Secured-only layer.

For a final draw, all winner-based persistence fields are null/NA. Draws are
never assigned to a winner or loser. Winner-independent lead changes, equality
periods, and the final return to equality are still retained.

## Reversal-by-turn denominator

At every Turn N, `reversal-by-turn.csv` separately reports:

- current leader eventually wins;
- current leader eventually loses;
- the game eventually draws; and
- the number of games tied at Turn N.

The reversal rate is exactly **current leader at Turn N eventually loses**.
Its denominator contains only games with a non-tied current leader at Turn N.
Tied positions are excluded, while eventual draws from non-tied positions are
reported as their own outcome.

## Frozen important Supply Point sets

The primary important-site set is the top five sites by **actual Objective
placements supplied per player-game** in the Issue #39 UCT 10,000 primary
analysis:

`S23`, `S21`, `S12`, `S13`, `S22`.

This is a single pre-frozen measure of direct Supply function, not a composite
site-value ranking. Primary conclusions use only this set.

Top-five sets for placement frequency, unsecured Control, Secured frequency,
and combined ownership/control are retained as explicitly named sensitivity
sets in `config.json` and `analysis.json`. They are never merged with the
primary set.

## Turning-point windows

`turning-point-events.csv` keeps `persistence_type`, `comparison_layer`,
`turning_turn`, and `relative_turn`. Each strict and nonlosing turning point is
examined independently at relative turns -2, -1, 0, +1, and +2 where those
turns exist. This prevents the two persistence definitions from being mixed.

## Workflow

Requirements: Python 3.9 or newer. No Ludii JAR is needed because the inputs
are the already validated Issue #37 replay outputs.

From the repository root:

```sh
python3 -m unittest discover -s experiments/issue-41/scripts -p 'test_*.py'
python3 experiments/issue-41/scripts/run_analysis.py
```

## Outputs

- `results/raw/turn-progression.csv`
- `results/turn-advantage-summary.csv`
- `results/lead-change-summary.csv`
- `results/reversal-by-turn.csv`
- `results/turning-point-events.csv`
- `results/supply-objective-transition.csv`
- `results/source-files.csv`
- `results/analysis.json`
- `results/environment.json`
- `experiments/issue-41.md`

Targeted continuation search is disabled for the baseline. If later evidence
shows that it is needed, it must use a separate configuration and outputs and
must not be described as a game-theoretic win probability.
