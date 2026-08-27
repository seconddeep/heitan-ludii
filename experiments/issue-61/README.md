# Issue 61: 3x3 board configuration and validation

This directory records the experimental 3x3 Heitan board added as the
small-scale baseline for later comparison with the existing 4x4 and 6x6
boards.

The 3x3 board uses the shared Heitan mechanics unchanged. Its Piece count is
an initial experimental configuration selected from prior human test play; it
is not a universal Heitan rule.

## Experimental 3x3 parameters

| Parameter | Value |
| --- | ---: |
| Supply grid | 4x4 |
| Supply Points | 16 (`S00`-`S33`) |
| Objective grid | 3x3 |
| Objectives | 9 (`O00`-`O22`) |
| Total graph vertices | 25 |
| Pieces per player | 27 |
| Total placements | 54 |
| Heitan turns per player | 9 |
| Total Heitan turns | 18 |
| Advantage score weight | 28 |
| Secured score weight | 280 |

Every Objective is connected to the four Supply Points at the corners of its
square. The Supply-grid graphics contain the 12 horizontal and 12 vertical
lines of the 4x4 Supply lattice.

## Scoring weights

The weights encode the existing lexicographic victory order:

1. Secured Objectives
2. Advantage Objectives
3. Pieces on Objectives

For the 3x3 limits:

```text
AdvantageWeight = PiecesPerPlayer + 1
                = 27 + 1
                = 28

SecuredWeight = ObjectiveCount * AdvantageWeight
              + PiecesPerPlayer
              + 1
              = 9 * 28 + 27 + 1
              = 280
```

The resulting Ludii score is:

```text
280 * SecuredObjectives
 + 28 * AdvantageObjectives
      + ScoringPiecesOnObjectives
```

## Validation coverage

`Heitan3x3Validation.java` selects `Board/3x3` explicitly and checks:

- 25 graph vertices and exactly 36 Objective-to-Supply edges;
- the exact `SupplyPoints` and `Objectives` regions;
- every named region from `S00` through `S33` and `O00` through `O22`;
- degree 4 and the exact four corner Supply Points for every Objective;
- exactly 24 Supply-grid graphics lines;
- three placements per Heitan turn;
- turn-end state updates only after the third placement;
- Objective access only through Supply controlled at turn start;
- one use per Supply per turn and reset on the following turn;
- the two-Piece per-turn Supply placement limit;
- closing of Secured Points and continued Control from Secured Supply;
- score-weight inequalities preserving the lexicographic victory order;
- seeded uniform-random games reaching the 54-placement natural end; and
- final Piece totals, independent scores, and lexicographic winners.

## Run

Use Ludii Player 1.3.14:

```powershell
$env:LUDII_JAR = '<path-to-Ludii-1.3.14.jar>'
java -cp $env:LUDII_JAR `
    experiments\issue-61\Heitan3x3Validation.java `
    games\Heitan.lud `
    20
```

The optional final argument is the number of seeded random games. Use `0` to
run only the structural, scoring, and deterministic mechanics checks.

## Validation results

Automated validation was run on 2026-08-14 with Ludii Player 1.3.14.

- The complete 3x3 validation passed for 20 seeded uniform-random games.
- Every random game ended naturally after 54 placements and 18 Heitan turns.
- Final Piece totals, independently calculated scores, and lexicographic
  winners matched in all 20 games.
- The deterministic shared-mechanics scenario passed.
- All 25 vertices, all named regions, all 36 expected Objective-to-Supply
  edges, and all 24 expected Supply-grid graphics lines passed validation.
- The existing 6x6 validation passed for 20 seeded uniform-random games after
  the 3x3 option was added.
- The default 4x4 option was compared with the definition at commit `f0502d5`,
  immediately before the 3x3 option was added. Across 202 existing complete
  trials and 14,746 positions, legal decisions, board states, natural endings,
  scores, and winners matched.

Commands used for regression validation:

```powershell
java -cp $env:LUDII_JAR `
    experiments\issue-51\Heitan6x6Validation.java `
    games\Heitan.lud `
    20

java -cp $env:LUDII_JAR `
    experiments\issue-50\HeitanRegression.java `
    C:\path\to\f0502d5\games\Heitan.lud `
    games\Heitan.lud `
    experiments\issue-32\results\trials\uct-10000-self-play `
    experiments\issue-32\results\trials\uct-3000-self-play `
    experiments\trials
```

GUI verification was completed on 2026-08-14 with Ludii Player 1.3.14:

- the `Board/3x3` option was selectable;
- the 4x4 Supply grid and 3x3 Objective layout displayed correctly;
- no missing, duplicate, or misaligned grid line was observed;
- Piece placement worked and the mover changed after three placements; and
- switching to the existing 4x4 and 6x6 options displayed both boards
  correctly.

The core rule documents and the standard 4x4 board reference remain unchanged
because this issue adds only an experimental board configuration.
