# Issue 93: 5x5 board configuration and validation

This directory records the experimental 5x5 Heitan board added as a
smaller-scale board for comparison with the existing Heitan board sizes.

The 5x5 board uses the shared Heitan mechanics unchanged. Its Piece count is
an initial scale-analysis configuration and is not a universal Heitan rule.

## Experimental 5x5 parameters

| Parameter | Value |
| --- | ---: |
| Supply grid | 6x6 |
| Supply Points | 36 (`S00`-`S55`) |
| Objective grid | 5x5 |
| Objectives | 25 (`O00`-`O44`) |
| Total graph vertices | 61 |
| Pieces per player | 48 |
| Total placements | 96 |
| Heitan turns per player | 16 |
| Total Heitan turns | 32 |
| Advantage score weight | 49 |
| Secured score weight | 1274 |

Every Objective is connected to the four Supply Points at the corners of its
square. The Supply-grid graphics contain the 30 horizontal and 30 vertical
lines of the 6x6 Supply lattice.

## Scoring weights

The weights encode the existing lexicographic victory order:

1. Secured Objectives
2. Advantage Objectives
3. Pieces on Objectives

For the 5x5 limits:

```text
AdvantageWeight = PiecesPerPlayer + 1
                = 48 + 1
                = 49

SecuredWeight = ObjectiveCount * AdvantageWeight
              + PiecesPerPlayer
              + 1
              = 25 * 49 + 48 + 1
              = 1274
```

The resulting Ludii score is:

```text
1274 * SecuredObjectives
  + 49 * AdvantageObjectives
       + PiecesOnObjectives
```

## Validation coverage

`Heitan5x5Validation.java` selects `Board/5x5` explicitly and checks:

- 61 graph vertices and exactly 100 Objective-to-Supply edges;
- the exact `SupplyPoints` and `Objectives` regions;
- every named region from `S00` through `S55` and `O00` through `O44`;
- degree 4 and the exact four corner Supply Points for every Objective;
- exactly 60 Supply-grid graphics lines;
- three placements per Heitan turn;
- turn-end state updates only after the third placement;
- Objective access only through Supply controlled at turn start;
- one use per Supply per turn and reset on the following turn;
- the two-Piece per-turn Supply placement limit;
- closing of Secured Points and continued Control from Secured Supply;
- score-weight inequalities preserving the lexicographic victory order;
- seeded uniform-random games reaching the 96-placement natural end; and
- final Piece totals, independent scores, and lexicographic winners.

## Run

Use Ludii Player 1.3.14:

```sh
java -cp /path/to/Ludii-1.3.14.jar \
    experiments/issue-93/Heitan5x5Validation.java \
    games/Heitan.lud \
    20
```

The optional final argument is the number of seeded random games. Use `0` to
run only the structural, scoring, and deterministic mechanics checks.

## Validation results

Automated validation was run on 2026-08-24 with Ludii Player 1.3.14.

- The complete 5x5 validation passed for 20 seeded uniform-random games.
- Every random game ended naturally after 96 placements and 32 Heitan turns.
- Final Piece totals, independently calculated scores, and lexicographic
  winners matched in all 20 games.
- The deterministic shared-mechanics scenario passed.
- All 61 vertices, all named regions, all 100 expected Objective-to-Supply
  edges, and all 60 expected Supply-grid graphics lines passed validation.
- The existing 3x3, 6x6, 7x7, and 8x8 validation suites each passed for 20
  seeded uniform-random games after the 5x5 option was added.
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
    experiments/issue-75/Heitan8x8Validation.java \
    games/Heitan.lud \
    20

java -cp /path/to/Ludii-1.3.14.jar \
    experiments/issue-50/HeitanRegression.java \
    /path/to/pre-5x5/Heitan.lud \
    games/Heitan.lud \
    experiments/issue-32/results/trials/uct-10000-self-play \
    experiments/issue-32/results/trials/uct-3000-self-play \
    experiments/trials
```

The core rule documents and the standard 4x4 board reference remain unchanged
because this issue adds only an experimental board configuration.
