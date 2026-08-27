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
      + ScoringPiecesOnObjectives
```

## Validation coverage

`Heitan6x6Validation.java` selects `Board/6x6` explicitly and checks:

- 85 graph vertices and exactly 144 graph edges;
- the exact `SupplyPoints` and `Objectives` regions;
- every named region from `S00` through `S66` and `O00` through `O55`;
- degree 4 for every Objective;
- for every `O(r,c)`, exact adjacency to `S(r,c)`, `S(r,c+1)`,
  `S(r+1,c)`, and `S(r+1,c+1)`, with no missing or extra edge;
- exactly 84 Supply-grid graphics lines, matching all and only the 42
  horizontal and 42 vertical adjacent pairs in the 7x7 grid;
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

Automated validation was run on 2026-08-13 with Ludii Player 1.3.14.

- The complete 6x6 validation passed for 20 seeded uniform-random games.
- Every random game ended naturally after 144 placements and 48 Heitan turns.
- Final Piece totals, independently calculated scores, and lexicographic
  winners matched in all 20 games.
- The deterministic mechanics scenario passed.
- All 85 vertices, all named regions, and the exact set of 144 expected
  Objective-to-Supply edges passed structural validation.
- All 84 expected Supply-grid graphics lines passed metadata validation.
- The current default 4x4 option was compared with the definition at commit
  `6148688`, immediately before the 6x6 option was added. Across 202 existing
  complete trials and 14,746 positions, legal decisions, board states, natural
  endings, scores, and winners matched.

Commands used:

```powershell
java -cp C:\path\to\Ludii-1.3.14.jar `
    experiments\issue-51\Heitan6x6Validation.java `
    games\Heitan.lud `
    20

java -cp C:\path\to\Ludii-1.3.14.jar `
    experiments\issue-50\HeitanRegression.java `
    C:\path\to\pre-6x6\Heitan.lud `
    games\Heitan.lud `
    experiments\issue-32\results\trials\uct-10000-self-play `
    experiments\issue-32\results\trials\uct-3000-self-play `
    experiments\trials
```

GUI verification was completed on 2026-08-13 with Ludii Player 1.3.14:

- the `Board/6x6` option was selectable;
- the 7x7 Supply grid and 6x6 Objective layout displayed correctly;
- no missing, duplicate, or extra grid line was visible;
- no Point, Piece, or line was misaligned or clipped;
- Piece placement worked and the mover changed after three placements; and
- returning to the default 4x4 option displayed the existing board correctly.
