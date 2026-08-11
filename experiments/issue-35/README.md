# Issue 35 one-turn deep-UCT analysis

This directory contains the reproducible experiment workflow for GitHub Issue
#35, "Analyze Heitan opening and midgame decisions with deep UCT search."

## Analysis unit

The analysis unit is one Heitan **turn**. Ludii represents that turn as three
consecutive moves by the same player. A sample starts at a turn boundary,
records the mover's three placements in order, and ends after the third
placement has updated Point states and passed control to the opponent. One UCT
instance selects all three placements in a repetition; they are not three
independent experiments. UCT may search beyond the current turn normally when
selecting each placement.

Candidate positions are taken after each of the first one through five
completed Heitan turns. Consequently every source-trial prefix is a positive
multiple of three placements and is the start of the next player's turn.
Position turn numbers refer to the turn about to be analyzed. For example, a
prefix after one completed turn represents the start of Turn 2 and therefore
uses a `turn-2-...` position ID.

## Three comparison keys

The analysis deliberately preserves three different views of every sample.

- `ordered_sequence` shows the actual order in which the three placements were
  selected. Placement-order differences are distinct, so it measures
  convergence of the procedure.
- `plan_signature` shows the turn-level strategic choice after removing
  placement order. It is an aggregation key, not an exact game-record or board
  comparison, so it measures convergence of strategy.
- `resulting_turn_state` is the complete state of all 41 Points after the third
  placement and Point-state update. It measures convergence of the resulting
  board itself.

Keeping these keys separate allows the report to distinguish convergence of
the procedure, convergence of the strategy, and convergence of the board
result.

### Frozen `plan_signature` version 1

`plan_signature` is the compact, sorted-key JSON encoding of the following
object. Site lists are sorted lexicographically and contain duplicates where
Piece multiplicity is strategically relevant.

```json
{
  "version": 1,
  "placement_target_category": {
    "supply_placements": 2,
    "objective_placements": 1
  },
  "supply_strategy": {
    "placement_sites": ["S11", "S12"],
    "source_sites": ["S10"],
    "secured_transitions": ["S11:P1"],
    "unresolved_transitions": ["S12:1:1:0>1:2:0"]
  },
  "objective_strategy": {
    "placement_sites": ["O11"],
    "piece_count": 1
  },
  "spatial_strategy": {
    "central": 3,
    "edge": 0,
    "corner": 0
  }
}
```

Definitions:

- `placement_sites` records placement targets, not their order. Repeated sites
  are repeated in the sorted list.
- `source_sites` records the controlled Supply Point selected for every
  Objective placement. It also preserves multiplicity before sorting.
- `secured_transitions` records Supply Points that newly became Secured during
  the turn and the securing player.
- `unresolved_transitions` records every changed, non-Secured Supply Point as
  `site:before_state:before_P1:before_P2>after_state:after_P1:after_P2`.
- `spatial_strategy` counts placement targets by central, edge, and corner.
  Supply Points use their 5x5 coordinates and Objectives their 4x4
  coordinates. A site is a corner when both coordinates are boundaries, an
  edge when exactly one is a boundary, and central otherwise.

The complete 41-site resulting state is deliberately excluded. Supply state
changes needed to describe the strategy are already represented by the
Secured and unresolved transition fields. Any remaining final-board difference
belongs exclusively to `resulting_turn_state`.

For example, `S11 -> O11(using S10) -> S12` and
`O11(using S10) -> S12 -> S11` have different `ordered_sequence` values but
the same `plan_signature` if their strategic features are the same. A different
Supply source or another listed strategic feature produces a different
signature. A complete resulting-board difference that does not change these
features remains the same plan and is preserved separately by
`resulting_turn_state`.

This version is frozen before the full experiment. `README.md`, `config.json`,
and `scripts/analyze_results.py` share the same version and fields. Once the
first full-budget stage starts, version 1 must not change. A later definition
change requires a new schema version and a new full experiment.

## Search budgets

The required budgets are 10,000, 30,000, and 100,000 UCT iterations per Ludii
move. The optional 300,000 budget is run only for positions whose plan
distribution is still changing materially between 30,000 and 100,000.

## Workflow

Requirements are Java 21, Ludii Player 1.3.14, and Python 3.9 or newer.

```sh
python3 experiments/issue-35/scripts/select_positions.py

python3 experiments/issue-35/scripts/run_experiments.py \
  --ludii-jar /path/to/Ludii-1.3.14.jar \
  --repetitions-override 2 --parallelism 2

python3 experiments/issue-35/scripts/analyze_results.py
```

The full experiment is staged by budget. The 100,000-iteration stage uses less
parallelism because the smoke test showed substantial CPU contention.

```sh
python3 experiments/issue-35/scripts/run_experiments.py \
  --ludii-jar /path/to/Ludii-1.3.14.jar \
  --budgets 10000 --parallelism 6 --batch-size 5

python3 experiments/issue-35/scripts/run_experiments.py \
  --ludii-jar /path/to/Ludii-1.3.14.jar \
  --budgets 30000 --parallelism 6 --batch-size 5 --append

python3 experiments/issue-35/scripts/run_experiments.py \
  --ludii-jar /path/to/Ludii-1.3.14.jar \
  --budgets 100000 --parallelism 3 --batch-size 5 --append

python3 experiments/issue-35/scripts/analyze_results.py
```

Use `--budgets 300000 --positions ... --append` only for positions recommended
by `results/recommend-300k.csv`; it is not required for every position.

## Outputs

- `results/raw/*.csv` and `results/trials/**`: full-run evidence
- `results/smoke/`: isolated 30-search infrastructure-validation evidence
- `results/ordered-sequence-frequencies.csv`: exact sequence distribution
- `results/plan-signature-frequencies.csv`: strategic plan distribution
- `results/resulting-state-frequencies.csv`: complete resulting-board distribution
- `results/turn-summary.csv`: allocation, spatial, and diversity summary
- `results/site-statistics.csv` and `results/supply-transitions.csv`: site detail
- `results/search-timings.csv`: raw-derived timing for every budget
- `results/budget-comparison.csv`: convergence metrics and bootstrap intervals
- `results/convergence-classification.csv`: final per-position classification
- `results/analysis.json` and `results/environment.json`: integrity and provenance

The workflow does not modify `games/Heitan.lud`, either rule specification, or
the shared full-game runner.
