# Issue 104 Objective-score validation

`HeitanObjectiveScoreValidation.java` plays complete, reproducible 4x4 games
and independently calculates each final score. The third tiebreak includes only
a player's own Pieces on Objectives where that player has Advantage.

The validation requires representative final positions containing each kind of
excluded Piece:

- a Piece on a Secured Objective;
- a Piece on an Objective where the opponent has Advantage;
- a Piece on a neutral Objective.

It also checks the final Ludii scores and winner, and confirms that the existing
4x4 score weights still preserve the lexicographic victory order.

Run with Ludii Player 1.3.14:

```powershell
java -cp C:\path\to\Ludii-1.3.14.jar `
    experiments\issue-104\HeitanObjectiveScoreValidation.java `
    games\Heitan.lud
```
