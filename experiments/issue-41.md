# Issue 41: Game-state progression and decision timing

## Summary

The analysis reconstructs all 24 turn boundaries in 100 primary UCT 10,000
games and 100 UCT 3,000 comparison games. It reuses the legal Issue #37
replays; no new self-play or targeted continuation was run. Results are
descriptive properties of these samples, not game-theoretic probabilities.

## Persistence in the primary sample

Values are median turns. Parentheses give games for which the measure is
defined among decisive games. `last lead change` is winner-independent and its
median excludes games with no lead-side switch.

| Comparison layer | Strict persistence | Nonlosing persistence | Last lead change |
|---|---:|---:|---:|
| Secured only | 23.0 (52/90) | 18.0 (90/90) | 20.0 |
| Secured + Advantage | 22.0 (83/90) | 20.5 (90/90) | 21.0 |
| Full lexicographic | 22.0 (90/90) | 21.0 (90/90) | 22.0 |

Strict persistence forbids both a later tie and a later opponent lead.
Nonlosing persistence permits later ties. They are deliberately not treated as
the same turning point. Winner-based persistence is null for all draws.

## Reversal after selected turns

The table uses the full Secured -> Advantage -> Objective Pieces comparison.
Rates exclude games tied at the checkpoint. The reversal rate means that the
current leader eventually loses; eventual draws are separate.

| Turn | Games with leader | Leader wins | Leader loses | Final draw | Tied at turn |
|---:|---:|---:|---:|---:|---:|
| 8 | 84 | 42.9% | 45.2% | 11.9% | 16 |
| 12 | 82 | 42.7% | 45.1% | 12.2% | 18 |
| 16 | 88 | 46.6% | 44.3% | 9.1% | 12 |
| 20 | 91 | 49.5% | 39.6% | 11.0% | 9 |

Complete results for all turns and all three comparison layers are in
`results/reversal-by-turn.csv`. Per-game strict/nonlosing timing and equality
history are in `results/lead-change-summary.csv`.

The approximately 40% reversal rate at Turn 20 and the full-lexicographic
strict-persistence median of Turn 22 indicate substantial late reversibility
in this sample. The data do not support describing the late game as merely
preserving an already fixed result.

## Supply and turning-point interpretation

Primary important-site analysis uses only S23, S21, S12, S13, and S22: the
Issue #39 UCT 10,000 top five by actual Objective placements supplied per
player-game. This is a direct Supply-usage measure, not a composite value
ranking. Alternative top-five definitions are retained only as sensitivity
sets in the machine-readable analysis.

`results/turning-point-events.csv` preserves persistence type, comparison
layer, turning turn, and relative turn (-2 through +2), alongside Objective,
Supply, allocation, and important-site events. This permits strict and
nonlosing event windows to be compared without pooling them. The turn-level
Supply-to-Objective allocation sequence is in
`results/supply-objective-transition.csv`.

For full-lexicographic strict persistence, the winner newly Secured an average
of 1.156 Objectives
on the turning turn. Two turns earlier, the winner newly Secured
0.244 Supply Points
and gained Control of 0.333
primary important sites per available game. This timing is consistent with
Supply preparation preceding Objective conversion, but it is an association,
not a causal estimate.

Objective placements first exceeded half of placements on Turn
10, peaked at
67.3% on Turn
13, and first exceeded half
of cumulative placements on Turn
21. The final
cumulative Objective share returned to
48.8%, showing
a midgame conversion phase followed by renewed Supply allocation rather than a
one-way transition.

## Integrity

- 200 complete, legally replayed games were reused.
- 4800 game-turn rows were reconstructed.
- 196800 point-turn states matched Piece counts.
- 8200 point state chains were continuous.
- 200 final 41-point boards matched source evidence.
- 200 winners were reproduced from the three lexicographic components.
- 7302 Objective Supply-source uses were checked.
- Winner-based persistence was null for every draw.

See `experiments/issue-41/README.md` for the frozen definitions and reproduction
commands.
