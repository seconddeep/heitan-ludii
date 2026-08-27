# Issue 71: 7x7 board configuration and validation

This directory records the experimental 7x7 Heitan board added as a
larger-scale board for later comparison with the existing 3x3, 4x4, and 6x6
boards.

The 7x7 board uses the shared Heitan mechanics unchanged. Its Piece count is
an initial scale-analysis configuration and is not a universal Heitan rule.

## Experimental 7x7 parameters

| Parameter | Value |
| --- | ---: |
| Supply grid | 8x8 |
| Supply Points | 64 (`S00`-`S77`) |
| Objective grid | 7x7 |
| Objectives | 49 (`O00`-`O66`) |
| Total graph vertices | 113 |
| Pieces per player | 72 |
| Total placements | 144 |
| Heitan turns per player | 24 |
| Total Heitan turns | 48 |
| Advantage score weight | 73 |
| Secured score weight | 3650 |

Every Objective is connected to the four Supply Points at the corners of its
square. The Supply-grid graphics contain the 56 horizontal and 56 vertical
lines of the 8x8 Supply lattice.

## Scoring weights

The weights encode the existing lexicographic victory order:

1. Secured Objectives
2. Advantage Objectives
3. Pieces on Objectives

For the 7x7 limits:

```text
AdvantageWeight = PiecesPerPlayer + 1
                = 72 + 1
                = 73

SecuredWeight = ObjectiveCount * AdvantageWeight
              + PiecesPerPlayer
              + 1
              = 49 * 73 + 72 + 1
              = 3650
```

The resulting Ludii score is:

```text
3650 * SecuredObjectives
 + 73 * AdvantageObjectives
      + ScoringPiecesOnObjectives
```

## Validation coverage

`Heitan7x7Validation.java` selects `Board/7x7` explicitly and checks:

- 113 graph vertices and exactly 196 Objective-to-Supply edges;
- the exact `SupplyPoints` and `Objectives` regions;
- every named region from `S00` through `S77` and `O00` through `O66`;
- degree 4 and the exact four corner Supply Points for every Objective;
- exactly 112 Supply-grid graphics lines;
- three placements per Heitan turn;
- turn-end state updates only after the third placement;
- Objective access only through Supply controlled at turn start;
- one use per Supply per turn and reset on the following turn;
- the two-Piece per-turn Supply placement limit;
- closing of Secured Points and continued Control from Secured Supply;
- score-weight inequalities preserving the lexicographic victory order;
- seeded uniform-random games reaching the 144-placement natural end; and
- final Piece totals, independent scores, and lexicographic winners.

## Run

Use Ludii Player 1.3.14:

```powershell
java -cp C:\path\to\Ludii-1.3.14.jar `
    experiments\issue-71\Heitan7x7Validation.java `
    games\Heitan.lud `
    20
```

The optional final argument is the number of seeded random games. Use `0` to
run only the structural, scoring, and deterministic mechanics checks.

## Validation results

Automated validation was run on 2026-08-15 with Ludii Player 1.3.14.

- The complete 7x7 validation passed for 20 seeded uniform-random games.
- Every random game ended naturally after 144 placements and 48 Heitan turns.
- Final Piece totals, independently calculated scores, and lexicographic
  winners matched in all 20 games.
- The deterministic shared-mechanics scenario passed.
- All 113 vertices, all named regions, all 196 expected Objective-to-Supply
  edges, and all 112 expected Supply-grid graphics lines passed validation.
- The existing 3x3 and 6x6 validation suites each passed for 20 seeded
  uniform-random games after the 7x7 option was added.
- The default 4x4 option was compared with the definition immediately before
  this change. Across 202 existing complete trials and 14,746 positions,
  legal decisions, board states, natural endings, scores, and winners matched.

Commands used for regression validation:

```powershell
java -cp C:\path\to\Ludii-1.3.14.jar `
    experiments\issue-61\Heitan3x3Validation.java `
    games\Heitan.lud `
    20

java -cp C:\path\to\Ludii-1.3.14.jar `
    experiments\issue-51\Heitan6x6Validation.java `
    games\Heitan.lud `
    20

java -cp C:\path\to\Ludii-1.3.14.jar `
    experiments\issue-50\HeitanRegression.java `
    C:\path\to\pre-7x7\Heitan.lud `
    games\Heitan.lud `
    experiments\issue-32\results\trials\uct-10000-self-play `
    experiments\issue-32\results\trials\uct-3000-self-play `
    experiments\trials
```

The core rule documents and the standard 4x4 board reference remain unchanged
because this issue adds only an experimental board configuration.
