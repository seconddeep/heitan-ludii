# Issue 37 Supply Point securing-timing analysis

This directory contains the reproducible workflow for GitHub Issue #37,
"Analyze Supply Point securing timing in Heitan." It replays the existing
complete-game trials from Issue #32. It does not generate new UCT games and
does not modify the game definition or either rule specification.

## Data set and turn phases

The primary analysis is the 100 `uct-10000-self-play` games. The 100
`uct-3000-self-play` games are used only for the search-strength comparison.
A Heitan turn is three consecutive placements by one player. The 24 turns are
reported as early (Turns 1-8), midgame (Turns 9-16), and late (Turns 17-24).

## Frozen securable-opportunity definition (version 1)

The analysis unit is `player x Supply Point x turn`, evaluated at the start of
that player's turn. A Supply Point is **securable** exactly when all of the
following hold:

1. the Supply Point is not already Secured;
2. the player has fewer than the three Pieces required to Secure it;
3. `placements_needed_to_secure = 3 - own_piece_count_at_turn_start`; and
4. `placements_needed_to_secure <= legal_max_additional_placements_this_turn`.

`legal_max_additional_placements_this_turn` is obtained from the current Ludii
game, not inferred solely from Piece counts. At every turn boundary the replay
extractor clones the Ludii `Context`, repeatedly finds a legal Supply placement
on the point, applies it to the clone, and stops when another such placement is
illegal or the turn ends. This incorporates the current per-point Piece cap,
the per-turn Supply placement cap, the remaining placements in the turn, the
Secured-state restriction, and any other condition enforced by the legal move
generator.

Under the current 4x4 rules, `own_count=1` or `own_count=2` is normally
securable. That is a consequence checked by the integrity validation, not a
hard-coded analyzer predicate.

The raw opportunity data records at least:

- `securable`;
- `own_piece_count_at_turn_start`;
- `opponent_piece_count_at_turn_start`;
- `placements_needed_to_secure`; and
- `legal_max_additional_placements_this_turn`.

An opportunity is "taken" only if that player Secures that point at the end of
the same turn. This makes the reported "securable but left unresolved" rate a
legal-move-based measurement.

## Frozen Supply spatial categories (version 1)

The internal category IDs and their report labels are:

- `corner`: the four corner Supply Points;
- `edge`: non-corner Supply Points on the outer boundary; and
- `interior`: the 3x3 non-edge interior Supply Points, reported as
  **central (interior 3x3)**.

Thus `central` does not mean only `S22`. The expected category sizes are 4, 12,
and 9 respectively. These same categories are used for securing rate, securing
timing, future usage, securable-opportunity rate, and winner/loser comparison.

## Requirements and workflow

- Java 21
- Ludii Player 1.3.14 JAR
- Python 3.9 or newer

From the repository root:

```sh
python3 experiments/issue-37/scripts/run_analysis.py \
  --ludii-jar /path/to/Ludii-1.3.14.jar

python3 -m unittest discover \
  -s experiments/issue-37/scripts -p 'test_*.py'
```

`run_analysis.py` first uses Ludii to replay every source trial and extract
turn-boundary state and legal-placement capacity. It then runs
`analyze_results.py` to validate and aggregate those raw records.

## Outputs

- `results/raw/replay-summary.csv`: legal replay result for every game
- `results/raw/placements.csv`: every placement and Objective Supply source
- `results/raw/supply-turn-states.csv`: start/end state and legal capacity
- `results/raw/objective-turn-states.csv`: adjacent-Objective state by turn
- `results/raw/securable-opportunities.csv`: rule-accurate opportunity records
- `results/raw/supply-events.csv`: one record per newly Secured Supply Point
- `results/per-turn-supply-state.csv`: analysis-ready per-turn Supply data
- `results/securing-timing-summary.csv`: first and all Securing timing
- `results/winner-loser-comparison.csv`: result-status comparison
- `results/spatial-comparison.csv`: corner/edge/interior comparison
- `results/future-usage-summary.csv`: event-level post-Securing utility
- `results/securable-opportunities.csv`: aggregate opportunity outcomes
- `results/source-trials.csv`: source paths and SHA-256 hashes
- `results/analysis.json`: machine-readable metrics and integrity checks
- `results/environment.json`: tool, input, configuration, and script hashes

The narrative result is in `experiments/issue-37.md`.
