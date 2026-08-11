# Issue 35 One-Turn Deep-UCT Analysis

This report records the experiment for GitHub Issue #35, "Analyze Heitan
opening and midgame decisions with deep UCT search."

## Result

The required experiment is complete: five fixed turn-start positions were each
searched 30 times at 10,000, 30,000, and 100,000 UCT iterations per Ludii
move. All 450 one-turn searches and replayable trials passed the integrity
checks.

Turn 2 through Turn 5 remained search-unstable between 30,000 and 100,000
iterations. Turn 6 converged toward a small plan set: its leading plan was
selected in 70% of 100,000-iteration searches. The optional 300,000 budget was
not run. Four positions met the configured recommendation threshold, but the
estimated additional wall time was about 25 hours; Issue #35 does not require
that optional depth.

## Analysis unit and keys

One observation is one Heitan turn. One UCT instance makes three consecutive
placements for the mover; after placement three, Point states update and the
mover changes. UCT searches future turns normally for each placement.

Three frozen keys measure different kinds of convergence:

- `ordered_sequence`: the exact placement order, including Objective Supply
  sources;
- `plan_signature` version 1: the order-independent strategic features of the
  turn, excluding the complete final board;
- `resulting_turn_state`: the complete state of all 41 Points after the turn.

The full version 1 definition is in `experiments/issue-35/README.md` and is
enforced by `config.json`, the analyzer, and regression tests.

## Positions

The selector examined turn-boundary prefixes from all 100 Issue #32
10,000-iteration trials and ranked them mechanically using Piece allocation,
unresolved and securable Supply Points, available Objectives, spatial legal
targets, mover, source trial, and prefix depth.

| Position | Completed source turns | Prefix placements | Mover | Classification |
| --- | ---: | ---: | ---: | --- |
| turn-2-supply-expansion | 1 | 3 | P2 | Supply expansion |
| turn-3-supply-securing-choice | 2 | 6 | P1 | Supply securing choice |
| turn-4-central-peripheral-competition | 3 | 9 | P2 | Central/peripheral competition |
| turn-5-objective-supply-tradeoff | 4 | 12 | P1 | Objective/Supply tradeoff |
| turn-6-early-midgame-allocation | 5 | 15 | P2 | Early-midgame allocation |

Position IDs name the turn about to be analyzed. Thus the position after one
completed source turn is the start of Turn 2. Complete boards, features,
selection reasons, source references, and SHA-256 values are in
`experiments/issue-35/positions.json`.

## Method and environment

- Required budgets: 10,000, 30,000, and 100,000 iterations per placement
- Repetitions: 30 per position and budget
- Required searches: 5 x 3 x 30 = 450
- Ludii Player: 1.3.14
- Java: OpenJDK 21.0.12
- Machine: Apple arm64, macOS 26.5.2
- Game SHA-256: `d81468535f9beb331040fd0bc736e93dfcb9bfe7da36042ce4aabf54f96b2f6c`
- Ludii JAR SHA-256: `248a8bde801f347bc380a4957fdb48012b4bdf234a5591c9bf7479913d73068e`
- Source commit: `3a183a8be10df300a7bce37957c607a92ca178e6`

The 10,000 and 30,000 stages used six workers. The 100,000 stage used three
workers to reduce the CPU contention observed in the smoke test. The 100,000
stage took 25,438 wall-clock seconds, about 7 hours 4 minutes. Raw-recorded mean
search time ranged from 23.8-30.3 seconds per turn at 10,000 and from
409.7-710.7 seconds at 100,000, depending on the position.

The outer 30,000-stage session disconnected after its workers completed, so
its runner-level timing record was not finalized. All 150 raw rows and trials
were complete and validated. `search-timings.csv`, regenerated from per-turn
raw timings, is the authoritative timing source across all three budgets.

## Integrity

| Check | Result |
| --- | ---: |
| Raw searches | 450 / 450 |
| Legal source prefixes replayed | 450 / 450 |
| Complete-turn boundaries | 450 / 450 |
| Exactly three added Pieces | 450 / 450 |
| Same mover for all three placements | 450 / 450 |
| Opponent mover after placement three | 450 / 450 |
| Point-state updates after placement three | 450 / 450 |
| Legal Objective Supply sources | 450 / 450 |
| Unique repetition IDs | 450 / 450 |
| Unique generated trial paths | 450 / 450 |
| Plan signatures regenerated | 450 / 450 |

The separate 30-search infrastructure-validation dataset remains under
`experiments/issue-35/results/smoke/` and is not included in any strategic
conclusion.

## Convergence

The table compares 30,000 with 100,000 iterations. TV is total-variation
distance; lower values indicate more similar selection distributions.

| Position | Ordered TV | Plan TV | Result TV | Top plan at 100k | Effective plans at 100k | Site-rank correlation | Classification |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Turn 2 | 0.667 | 0.367 | 0.367 | 13.3% | 15.61 | 0.999 | Search instability |
| Turn 3 | 0.800 | 0.367 | 0.367 | 13.3% | 13.21 | 0.989 | Search instability |
| Turn 4 | 0.733 | 0.467 | 0.467 | 33.3% | 6.06 | 0.866 | Search instability |
| Turn 5 | 0.500 | 0.500 | 0.500 | 26.7% | 5.58 | 0.873 | Search instability |
| Turn 6 | 0.400 | 0.200 | 0.200 | 70.0% | 2.49 | 0.827 | Convergence toward a small plan set |

Move order remains less stable than strategic plans at every position. Turn 2
and Turn 3 have nearly identical site rankings at the two high budgets, but
their plan distributions still change and remain broad. This separates stable
site-level priority from unstable turn-level strategy.

Turn 6 is the clearest convergence case. Its leading 100,000-iteration plan
places all three Pieces on Objectives O01, O12, and O13 using Supply Points
S11, S13, and S23. That plan accounts for 70% of searches. Its three most
common plans are shared with the 30,000 distribution, and plan TV is 0.20.

## Allocation and spatial priorities

Values below are averages or target shares at 100,000 iterations.

| Position | Supply placements | Objective placements | Central | Edge | Corner |
| --- | ---: | ---: | ---: | ---: | ---: |
| Turn 2 | 3.00 | 0.00 | 100.0% | 0.0% | 0.0% |
| Turn 3 | 2.03 | 0.97 | 100.0% | 0.0% | 0.0% |
| Turn 4 | 0.87 | 2.13 | 98.9% | 1.1% | 0.0% |
| Turn 5 | 0.50 | 2.50 | 83.3% | 5.6% | 11.1% |
| Turn 6 | 0.03 | 2.97 | 27.8% | 71.1% | 1.1% |

The allocation progresses from all-Supply expansion in Turn 2 toward almost
all-Objective investment in Turn 6. Central targets dominate Turns 2-5. Turn 6
is different because its converged Objective plan primarily uses edge
Objectives in that fixed source position.

At 100,000 iterations, notable target concentrations are S12 in Turn 2 (33 of
90 placements), S21 in Turn 3 (17), S32/O21/O22 in Turn 4 (25/23/20), O21 in
Turn 5 (60), and O13/O01/O12 in Turn 6 (33/30/24).

## Supply securing

No analyzed turn newly Secured a Supply Point at any budget: 0 of 450 turns.
This includes Turns 3-6, whose starting positions each offered multiple Supply
Points that the mover could Secure during the analyzed turn. Instead, searches
left such points unresolved or invested in Objectives. Observed unresolved
post-transition counts include 1-1, 1-2, 2-1, 1-0, and 0-1.

This is a strong result for these fixed early positions, but it does not imply
that deep UCT never Secures Supply Points later in a game. Issue #32 observed
more Secured Supply Points on complete final boards at high depth.

## Interpretation

- Turn 2-3 site priorities are spatially stable, but deep search preserves a
  wide and changing set of Supply-network plans.
- Turn 4-5 narrows the plan set while still changing materially from 30,000 to
  100,000; Objective timing and exact allocation have not converged.
- Turn 6 stabilizes around a small Objective-focused plan set.
- The absence of Supply securing across all selected turns indicates that deep
  UCT prefers keeping early Supply commitments reversible in these positions.
- Strategic diversity is not established for Turns 2-5 because their high
  diversity coexists with substantial budget-to-budget distribution change.

## Limitations

- Five fixed positions cannot represent every Heitan opening.
- Thirty repetitions leave uncertainty in low-frequency plan estimates.
- UCT internal randomness is not bit-for-bit controlled by the recorded numeric
  seed; preserved trials are the authoritative selected sequences.
- The optional 300,000 comparison was omitted, so instability beyond 100,000
  remains unresolved for Turns 2-5.
- Symmetry normalization was not applied because all selected positions are
  asymmetric colored positions; the basic fixed-position comparison is used.

## Reproduction and outputs

Run the three required budget stages as documented in
`experiments/issue-35/README.md`, then run:

```sh
python3 experiments/issue-35/scripts/analyze_results.py
```

The repository preserves raw CSV data, 450 replayable full-run trials, the
30-search smoke dataset, ordered-sequence frequencies, plan frequencies,
resulting-state frequencies, turn summaries, site statistics, Supply
transitions, raw-derived timings, budget comparisons, classifications,
environment hashes, and machine-readable integrity results.

The Issue #35 acceptance criteria are satisfied without the optional 300,000
stage. This work changes experiment tooling and evidence only; the game
definition, rule specifications, shared full-game runner, and mechanics remain
unchanged.
