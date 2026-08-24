# Issue 75: 8x8 board configuration and validation

This directory records the experimental 8x8 Heitan board added as a
larger-scale board for later comparison with the existing 3x3, 4x4, 6x6, and
7x7 boards.

The 8x8 board uses the shared Heitan mechanics unchanged. Its Piece count is
an initial scale-analysis configuration and is not a universal Heitan rule.

## Experimental 8x8 parameters

| Parameter | Value |
| --- | ---: |
| Supply grid | 9x9 |
| Supply Points | 81 (`S00`-`S88`) |
| Objective grid | 8x8 |
| Objectives | 64 (`O00`-`O77`) |
| Total graph vertices | 145 |
| Pieces per player | 84 |
| Total placements | 168 |
| Heitan turns per player | 28 |
| Total Heitan turns | 56 |
| Advantage score weight | 85 |
| Secured score weight | 5525 |

Every Objective is connected to the four Supply Points at the corners of its
square. The Supply-grid graphics contain the 72 horizontal and 72 vertical
lines of the 9x9 Supply lattice.

## Scoring weights

The weights encode the existing lexicographic victory order:

1. Secured Objectives
2. Advantage Objectives
3. Pieces on Objectives

For the 8x8 limits:

```text
AdvantageWeight = PiecesPerPlayer + 1
                = 84 + 1
                = 85

SecuredWeight = ObjectiveCount * AdvantageWeight
              + PiecesPerPlayer
              + 1
              = 64 * 85 + 84 + 1
              = 5525
```

The resulting Ludii score is:

```text
5525 * SecuredObjectives
  + 85 * AdvantageObjectives
       + PiecesOnObjectives
```

## Validation coverage

`Heitan8x8Validation.java` selects `Board/8x8` explicitly and checks:

- 145 graph vertices and exactly 256 Objective-to-Supply edges;
- the exact `SupplyPoints` and `Objectives` regions;
- every named region from `S00` through `S88` and `O00` through `O77`;
- degree 4 and the exact four corner Supply Points for every Objective;
- exactly 144 Supply-grid graphics lines;
- three placements per Heitan turn;
- turn-end state updates only after the third placement;
- Objective access only through Supply controlled at turn start;
- one use per Supply per turn and reset on the following turn;
- the two-Piece per-turn Supply placement limit;
- closing of Secured Points and continued Control from Secured Supply;
- score-weight inequalities preserving the lexicographic victory order;
- seeded uniform-random games reaching the 168-placement natural end; and
- final Piece totals, independent scores, and lexicographic winners.

## Run

Use Ludii Player 1.3.14:

```sh
java -cp /path/to/Ludii-1.3.14.jar \
    experiments/issue-75/Heitan8x8Validation.java \
    games/Heitan.lud \
    20
```

The optional final argument is the number of seeded random games. Use `0` to
run only the structural, scoring, and deterministic mechanics checks.

## Validation results

Automated validation was run on 2026-08-24 with Ludii Player 1.3.14.

- The complete 8x8 validation passed for 20 seeded uniform-random games.
- Every random game ended naturally after 168 placements and 56 Heitan turns.
- Final Piece totals, independently calculated scores, and lexicographic
  winners matched in all 20 games.
- The deterministic shared-mechanics scenario passed.
- All 145 vertices, all named regions, all 256 expected Objective-to-Supply
  edges, and all 144 expected Supply-grid graphics lines passed validation.
- The existing 3x3, 6x6, and 7x7 validation suites each passed for 20 seeded
  uniform-random games after the 8x8 option was added.
- The default 4x4 option was compared with the definition immediately before
  this change. Across 202 existing complete trials and 14,746 positions,
  legal decisions, board states, natural endings, scores, and winners matched.

Commands used for regression validation:

```sh
java -cp /path/to/Ludii-1.3.14.jar \
    experiments/issue-61/Heitan3x3Validation.java \
    games/Heitan.lud \
    20

java -cp /path/to/Ludii-1.3.14.jar \
    experiments/issue-51/Heitan6x6Validation.java \
    games/Heitan.lud \
    20

java -cp /path/to/Ludii-1.3.14.jar \
    experiments/issue-71/Heitan7x7Validation.java \
    games/Heitan.lud \
    20

java -cp /path/to/Ludii-1.3.14.jar \
    experiments/issue-50/HeitanRegression.java \
    /path/to/pre-8x8/Heitan.lud \
    games/Heitan.lud \
    experiments/issue-32/results/trials/uct-10000-self-play \
    experiments/issue-32/results/trials/uct-3000-self-play \
    experiments/trials
```

The core rule documents and the standard 4x4 board reference remain unchanged
because this issue adds only an experimental board configuration.
