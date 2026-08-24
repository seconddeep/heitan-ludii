# Issue 70: front selection and late-game concentration

This directory preregisters the Issue 70 analysis. All definitions in this
file and `config.json` are frozen before production aggregation. No new games
are generated.

## Samples and fixed inputs

The analysis reuses the Issue 65 legally replayed 3x3, 4x4, and 6x6 trials
and its frozen normalized `LL`--`HH` mapping. UCT 1000 is primary (100, 100,
and 50 games). Seeded Random, UCT 100, and UCT 500 are sensitivity checks.
Input artifacts and trials are checked by SHA-256 before analysis.

Issue 65's four-turn active-front definition and Issue 68's primary dormant
threshold `k=2` are unchanged. A backlog region is active and receives no
placement on the current turn. Progress uses end-of-turn progress and the
bands `(0,.25]`, `(.25,.50]`, `(.50,.75]`, and `(.75,1]`.

## Exclusive final-front classification

The cohort contains every region active at least once through 75% progress.
After its final placement, exactly the first matching category below applies:

1. `mechanically_closed`: at least one later turn start is observable and the
   region has zero legal target points at every later turn start;
2. `resolved_or_settled`: opposing Unsecured presence has ended, or the local
   lexicographic outcome is fixed by the conservative bound below;
3. `end_censored`: the applicable remaining-game threshold is met; or
4. `selectively_abandoned`: the region remains unresolved and outcome-mutable,
   has a later legal opportunity, and receives no later placement.

Because Heitan updates point states after all three placements, classification
uses the end-of-turn snapshot containing the region's final placement.

No later observation makes a region ineligible for `mechanically_closed`, so
an unobserved last-turn tail is not called mechanical. The primary censoring
rule is fewer than four complete turns after the final-placement turn. Fixed
sensitivity rules use remaining fractions strictly below 10% and 20%:

```
remaining_turns = total_turns - final_placement_turn
remaining_fraction = remaining_turns / total_turns
```

The category order never changes in sensitivity analysis.

## Conservative local and global outcome bound

The same calculation is used for the Objectives in one region and for all
Objectives. If the scope has `n` Objectives, define:

```
A = 3*n + 1
S = n*A + 3*n + 1
L(p) = S*secured(p) + A*advantage(p) + objective_pieces(p)
```

These weights preserve the rules' lexicographic order. For challenger `p`
against `q`, let `c[p,i]` be p's current count on unsecured Objective `i` and
let integer `x[i]` be an optimistic additional allocation:

```
0 <= x[i] <= 3 - c[p,i]
sum(x[i]) <= R[p]
R[p] = board_piece_count_per_player - placements_by_player_so_far
```

`placements_by_player_so_far` counts actual moves already applied at the
evaluated snapshot. It includes the current move for an after-move or
turn-end snapshot and excludes it for a before-move snapshot. The configured
board counts are 27, 36, and 72 for 3x3, 4x4, and 6x6. The calculation never
uses a Ludii internal stock.

Secured sites are excluded and every player's three-piece site cap is kept.
Only Objective supply-source/control/usage legality is relaxed. The opponent
is assigned no future contribution, giving the challenger an intentionally
optimistic upper bound; unused budget may remain off the scoped Objectives.
For every allocation, reaching three secures the Objective for the challenger
and all other Advantage states are recomputed. A deterministic integer
knapsack maximizes

```
U(p,q) = max_x (L(p,x) - L(q,x)).
```

If q currently leads, q is fixed only when `U(p,q) < 0`. A current tie is
fixed only when `U(P1,P2) <= 0` and `U(P2,P1) <= 0`. The symmetric rule applies
when P1 leads. This is a sufficient, not necessary, fixed-outcome test.

## Primary measures

By game and progress band report active, dormant, and backlog counts; rates
with at least two active or unattended unresolved fronts; and decline from
the game's peak active count. Report final-band survival and the exclusive
classifications above for earlier-active fronts.

For placements and turn-start legal target opportunities separately report
normalized entropy, HHI, largest and top-two shares, and occupied regions.
Primary interpretation uses placement minus opportunity concentration.

For every final-band Objective placement report target-state change, local
lead change, same-turn securing contribution, global comparison change,
whether the global result can still change under the bound, and whether its
regional result was already fixed before placement. These flags overlap and
are not forced into one category.

## Validation, inference, and run

Validation stops on hash, provenance, game-key, move-key, region, natural-end,
three-placement-turn, remaining-piece, replay winner, or reconstructed-score
failure. In particular `0 <= R[p]` always and `R[p] == 0` at natural end.
Intervals use 2,000 game-bootstrap replicates with seed 700070. Contradictory
or non-monotonic results are reported directly.

```powershell
$env:LUDII_JAR = '<path-to-Ludii-1.3.14.jar>'
./experiments/issue-70/scripts/run-analysis.ps1 `
  -LudiiJar $env:LUDII_JAR
```

Requirements: Ludii Player 1.3.14, Java 21, Node.js 24, and PowerShell.
