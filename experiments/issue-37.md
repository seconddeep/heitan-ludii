# Issue 37: Supply Point securing timing

## Summary

The complete-game evidence supports **delayed, context-dependent
infrastructure**, not a general policy of Securing a Supply Point as soon as it
becomes legally possible.

In the primary 10,000-iteration data set, all 100 games eventually Secured at
least one Supply Point, but the first event occurred at mean Turn 7.28 (median
Turn 7). Of 367 Securing events, 112 (30.5%) were early, 157 (42.8%) were in the
midgame, and 98 (26.7%) were late. At the same time, only 367 of 10,079 legal
player-Supply-turn opportunities (3.64%) were taken immediately. Most legal
opportunities were therefore deferred, while Secured points that were chosen
usually remained useful: 336 of 367 events (91.6%) supported at least one
later Objective placement.

The result reconciles the earlier experiments. Issue #35 found no immediate
Securing in its selected one-turn searches, while Issue #32 found more Secured
Supply Points on deeper-UCT final boards. Complete trials show the transition:
UCT often leaves a legally securable point flexible across multiple turns,
then Secures selected infrastructure that continues to supply Objectives.

## Data and method

The analysis replays the existing Issue #32 trials:

| Role | Search budget | Games |
|---|---:|---:|
| Primary | 10,000 iterations per placement | 100 |
| Strength comparison | 3,000 iterations per placement | 100 |

No new UCT self-play was generated. Every trial was loaded through Ludii
1.3.14 and each recorded decision was matched to a legal move before being
applied. A turn is three placements by one player; early is Turns 1-8,
midgame is Turns 9-16, and late is Turns 17-24.

### Legally securable opportunities

A `player x Supply Point x turn` record is securable at the start of the
player's turn only when the point is not Secured, the player needs a positive
number of Pieces to reach three, and Ludii permits at least that many further
placements on the point during the turn.

The legal maximum is measured by cloning the turn-start Ludii context and
repeatedly applying a legal placement to that Supply Point. It is not inferred
from `own_count` alone. Under the current rules the result normally corresponds
to own counts 1 or 2; all 120,000 Supply-turn records were checked against that
current-rule expectation.

### Spatial categories

- `corner`: the four corner Supply Points;
- `edge`: the 12 non-corner points on the outer boundary;
- `interior`: the nine non-edge points in the 3x3 interior, reported as
  **central (interior 3x3)**.

The same classification is used in timing, opportunity, future-use, and
winner/loser comparisons.

## Primary 10,000-iteration results

### Timing

| Measure | Result |
|---|---:|
| Games with a Securing event | 100 / 100 |
| First Securing turn, mean | 7.28 |
| First Securing turn, median | 7 |
| All Securing events | 367 |
| Mean turn of all events | 12.44 |
| Early events | 112 (30.5%) |
| Midgame events | 157 (42.8%) |
| Late events | 98 (26.7%) |

### Pre-Securing state

The turn-start Piece-count pattern was dominated by `2-2`:

| P1-P2 pattern | Events | Share |
|---|---:|---:|
| `2-2` | 279 | 76.0% |
| `1-2` | 47 | 12.8% |
| `2-1` | 39 | 10.6% |
| `1-1` | 2 | 0.5% |

Using first unresolved control by the eventual securing player as the point's
"strategically relevant" boundary, 286 events (77.9%) had an intervening
opponent placement before Securing. This operational measure indicates that
Securing commonly follows contest rather than uncontested early commitment.

### Spatial comparison

| Category | Events | Mean turn | Legal opportunities | Immediate take rate | Mean later uses |
|---|---:|---:|---:|---:|---:|
| corner | 1 | 21.00 | 70 | 1.43% | 1.00 |
| edge | 12 | 20.75 | 1,329 | 0.90% | 0.67 |
| central (interior 3x3) | 354 | 12.13 | 8,680 | 4.08% | 3.88 |

Interior Supply Points account for 354 of 367 events (96.5%). This is not a
claim that `S22` alone is central: the category contains all nine points in the
interior 3x3. The location difference is also visible after normalizing by
legal opportunity count.

### Future Objective utility

At Securing, an event had a mean 3.33 adjacent live and future-placeable
Objectives. Of the 367 Secured Supply Points, 336 (91.6%) were used later, with
a mean 3.77 later Objective placements per event. Because one Supply Point may
be used only once per turn, future-use turn count equals supported-placement
count in these trials.

### Securable opportunities left flexible

There were 10,079 legally securable player-Supply-turn records. Only 367 were
Secured in the same turn, leaving 9,712 (96.4%) unresolved at that turn
boundary. For 8,584 opportunity records (85.2%), that player never later
Secured the point.

These are opportunity records rather than independent points: the same
player-point pair can appear on several turns while the decision remains open.
Both the raw opportunity history and eventual outcome are retained so the
repeated-turn interpretation is explicit.

## Winner and loser comparison

For the 90 decisive primary games, winners produced 167 events at mean Turn
11.63, while losers produced 159 at mean Turn 12.80. Immediate opportunity
take rates were 3.70% and 3.51%, respectively. The timing difference is modest
relative to the strong spatial and search-budget effects, so it should not be
read as causal evidence that earlier Securing itself wins games.

The ten drawn games are reported separately: their 20 player-games produced
41 events at mean Turn 14.32.

## Search-strength comparison

| Measure | 3,000 iterations | 10,000 iterations |
|---|---:|---:|
| Games with any Securing | 91 / 100 | 100 / 100 |
| Mean first Securing turn | 12.81 | 7.28 |
| Total events | 245 | 367 |
| Mean turn of all events | 16.28 | 12.44 |
| Events with later use | 194 (79.2%) | 336 (91.6%) |
| Mean later uses | 2.29 | 3.77 |

Within these fixed samples, stronger UCT shifts Securing earlier, produces more
Secured Supply Points, and selects points with greater subsequent use. This is
a between-sample comparison, not paired play from identical positions, so the
direction is evidence of an association with search budget rather than a
standalone causal estimate.

## Interpretation

- **Early commitment:** not supported as a general rule. Immediate take rates
  are low and most events do not occur in the early phase.
- **Delayed infrastructure:** strongly supported. Opportunities persist, while
  selected Secured points usually continue to support Objective play.
- **Context-dependent securing:** strongly supported. Interior points dominate
  both absolute events and opportunity-normalized take rates; contested `2-2`
  positions are the most common precursor.
- **Low securing value:** supported for many individual opportunities, but not
  for the infrastructure ultimately selected by 10,000-iteration UCT, which
  has high subsequent-use rates.

## Integrity checks

- 200/200 source trials replayed legally to NaturalEnd.
- Every replay contained 72 placements and 24 complete turns.
- All replay winners and final 41-point boards matched Issue #32.
- 120,000 Supply-turn and 76,800 Objective-turn rows matched Piece-derived
  state and formed continuous state chains.
- All 14,400 placements were retained; every Objective Supply source was
  adjacent, controlled, and used at most once in its turn.
- All source paths and SHA-256 hashes are in
  `results/source-trials.csv`; configuration, game, JAR, scripts, and source
  index hashes are in `results/environment.json`.

See `experiments/issue-37/README.md` for reproduction commands and the complete
output inventory.
