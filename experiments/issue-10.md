# Issue 10 Validation Report

This report records the validation performed for GitHub Issue #10,
"Validate Heitan implementation in Ludii."

## Environment

- Date: 2026-08-10
- Ludii Player: 1.3.14
- Java: OpenJDK 21.0.11
- Game definition: `games/Heitan.lud`
- Specifications:
  - `docs/rules-ja.md` (primary rule specification)
  - `docs/rules.md` (English rule specification)
  - `docs/board.md` (board structure and connections)

## Specification audit

The Ludii definition was checked against `docs/rules-ja.md`, `docs/rules.md`,
and `docs/board.md`. The English rules were also checked for consistency with
the primary Japanese rules.

| Requirement | Implementation | Result |
| --- | --- | --- |
| English and Japanese rule specifications describe the same behaviour | Sections 1-10 of both rule documents | Pass |
| Two players; P1 Black and P2 White | `(players 2)` and player colour metadata | Pass |
| 25 Supply Points and 16 Objectives | Regions `0..24` and `25..40` | Pass |
| Each Objective connects to its four corner Supply Points | 16 graph vertices with four specified edges each | Pass |
| Each player places exactly three Pieces per turn | `RecordPlacement`, `moveAgain`, and `MovesThisTurn` | Pass |
| At most three Pieces per player on one point | `WithinPointLimit` | Pass |
| At most two placements on one Supply Point per turn | `SupplyPointPlacementAllowed` and `PlacementsThisTurn` | Pass |
| Objective placement requires an adjacent controlled Supply Point | `ObjectivePlacement` and `AvailableControlledSupplyPoint` | Pass |
| A Supply Point may supply one Objective placement per turn | `UsedSupplyPoints` | Pass |
| Point states update after all three placements | `UpdatePointStates` runs after the third move | Pass |
| A point with three Pieces from one player becomes Secured | `PointStateAfterTurn` states 3 and 4 | Pass |
| Secured points are closed to further placement | State checks `< 3` in both placement rules | Pass |
| Game ends after both players place all 36 Pieces | `AllPiecesPlaced` checks for 72 Pieces | Pass |
| Only Objectives determine the result | `ObjectiveScore` only counts the Objectives region | Pass |

No discrepancy was found between the specifications and the implementation.

## Manual rule checks

The following behaviours were exercised in the Ludii GUI and passed:

- The game compiles and loads successfully.
- Only Supply Points are legal on the initial move.
- A turn contains exactly three placements.
- No more than two Pieces can be placed on one Supply Point in a turn.
- Controlled Supply Points enable only their connected Objectives.
- A Supply Point cannot be reused for Objective placement in the same turn.
- Different Supply Points can place multiple Pieces on the same Objective.
- Supply Points and Objectives become Secured after a player reaches three
  Pieces there.
- Secured Supply Points and Objectives reject further placements.
- State updates and the player change occur after the third placement.
- Complete games end naturally after all 72 Pieces have been placed.

No illegal move or invalid state was observed.

## Random AI vs AI evaluation

Three independent evaluations of 10 trials were run with Random agents.

| Metric | Result |
| --- | ---: |
| Completed games | 30 / 30 |
| Moves per game | 72 |
| P1 wins | 17 |
| P2 wins | 13 |
| Draws | 0 |
| Timeouts | 0 |
| Completion | 1.0 in every evaluation |

The agents generated legal moves throughout every game. No stall, timeout, or
failure to complete was observed.

## Human vs AI evaluation

Two games were completed with Human and Random AI roles reversed. The saved
trials are:

- `experiments/trials/human-black-vs-random-white.trl`
- `experiments/trials/random-black-vs-human-white.trl`

| Trial | Moves | Secured Objectives P1/P2 | Advantage Objectives P1/P2 | Objective Pieces P1/P2 | Independent score P1/P2 | Ludii winner |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Human Black vs Random White | 72 | 7 / 0 | 0 / 7 | 22 / 11 | 4425 / 270 | P1 |
| Random Black vs Human White | 72 | 2 / 8 | 4 / 1 | 10 / 25 | 1416 / 5094 | P2 |

Both trials have `endtype=NaturalEnd`. The independently calculated result
matches the winner recorded by Ludii in both games.

## Result calculation

The implementation encodes the specified lexicographic comparison as:

```text
score = 629 * securedObjectives
      +  37 * advantageObjectives
      +       piecesOnObjectives
```

The weights preserve the required priority order:

- A player owns at most 36 Pieces, so a one-point Advantage lead worth 37
  cannot be offset by the Piece-count criterion.
- There are 16 Objectives, and `16 * 37 + 36 = 628`, so a one-point Secured
  lead worth 629 cannot be offset by either lower criterion.
- Equal values for all three criteria produce equal scores and therefore a
  draw under `byScore`.

This matches the required order: Secured Objectives, Advantage Objectives,
then Pieces on Objectives.

## Conclusion

The checks performed satisfy the acceptance criteria for Issue #10:

- Human vs AI games completed with the human playing either colour.
- AI vs AI completed in all 30 evaluation trials.
- No illegal move, invalid state, stall, or timeout was observed.
- Every evaluated game completed after 72 placements.
- The implementation was verified against the Heitan rules and board specifications.
- Natural-game winners matched independent score calculations, and the score
  weights preserve all specified tie-break priorities.

This work only adds validation documentation and saved trial evidence. No game
rule or implementation behaviour was changed.
