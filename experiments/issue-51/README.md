# Issue 51: 6x6 board validation

This directory contains the validation harness for the experimental 6x6
Heitan board added for scale analysis.

The 6x6 board uses the same Heitan mechanics as the existing 4x4 game. The
shared rule specifications and the 4x4 board reference are unchanged. The
values below are provisional experiment parameters, not final balance tuning.

## Provisional 6x6 parameters

| Parameter | Value |
| --- | ---: |
| Supply grid | 7x7 |
| Supply Points | 49 (`S00`-`S66`) |
| Objective grid | 6x6 |
| Objectives | 36 (`O00`-`O55`) |
| Total graph vertices | 85 |
| Pieces per player | 72 |
| Total placements | 144 |
| Heitan turns per player | 24 |
| Total Heitan turns | 48 |
| Advantage score weight | 73 |
| Secured score weight | 2701 |

Each player has 72 Pieces because that is the initial value selected for this
scale experiment. It is kept in the board option so that a later experiment
can change it without changing the shared mechanics.

The score weights encode the existing lexicographic victory order:

1. Secured Objectives
2. Advantage Objectives
3. Pieces on Objectives

For the provisional limits:

```text
AdvantageWeight = PiecesPerPlayer + 1
                = 72 + 1
                = 73

SecuredWeight = ObjectiveCount * AdvantageWeight
              + PiecesPerPlayer
              + 1
              = 36 * 73 + 72 + 1
              = 2701
```

The resulting Ludii score is:

```text
2701 * SecuredObjectives
 + 73 * AdvantageObjectives
      + PiecesOnObjectives
```

## Validation coverage

`Heitan6x6Validation.java` selects `Board/6x6` explicitly and checks:

- 85 graph vertices and exactly 144 graph edges;
- the exact `SupplyPoints` and `Objectives` regions;
- every named region from `S00` through `S66` and `O00` through `O55`;
- degree 4 for every Objective;
- for every `O(r,c)`, exact adjacency to `S(r,c)`, `S(r,c+1)`,
  `S(r+1,c)`, and `S(r+1,c+1)`, with no missing or extra edge;
- three placements per Heitan turn and state updates only after placement three;
- Objective access only through Supply controlled at the start of the turn;
- one use per Supply per turn and reset on the following turn;
- the two-Piece per-turn Supply placement limit;
- closing of Secured Points and continued Control from a Secured Supply;
- the score-weight inequalities that preserve the victory order;
- seeded uniform-random games reaching the 144-placement natural end;
- final Piece totals, independent scores, and lexicographic winners.

## Run

Use Ludii Player 1.3.14:

```powershell
java -cp C:\path\to\Ludii-1.3.14.jar `
    experiments\issue-51\Heitan6x6Validation.java `
    games\Heitan.lud `
    20
```

The optional final argument is the number of seeded random games. Use `0`
to run only the structural, scoring, and deterministic mechanics checks.

## Validation results

Results will be recorded after the full validation step.
