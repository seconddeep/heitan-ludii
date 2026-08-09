# Heitan Rules Specification

## 1. Game Overview

### Objective

The objective of Heitan is to control more Scoring Sites than the opponent at the end of the game.

Only Scoring Sites are used to determine the winner.
The number of controlled Supply Sites does not directly affect the result.

---

## 2. Players

Heitan is a two-player game.

- Player 1 (Black): Moves first
- Player 2 (White): Moves second

Both players have the same number of pieces.

---

## 3. Board

The board consists of a 4×4 square grid.

There are two types of sites:

- Supply Sites
- Scoring Sites

### Supply Sites

Supply Sites are placed on grid intersections.

- 5 × 5 layout
- Total: 25 sites

### Scoring Sites

Scoring Sites are placed at the center of each grid cell.

- 4 × 4 layout
- Total: 16 sites

Each Scoring Site is connected to the four surrounding Supply Sites.

Detailed coordinates and connections are defined in `board.md`.

---

## 4. Pieces

Each player has 36 pieces.

All pieces have the same properties.

In the standard 4×4 board, each player takes 12 turns.

---

## 5. Turn

Each turn, a player must place exactly three pieces.

A turn is completed after all three placements are finished.

The three pieces may be freely distributed among one to three sites.

Examples:

- Place three pieces on one site
- Split pieces between two sites
- Place pieces on three different sites

Pieces can also be added to sites that already contain pieces.

Each player can place a maximum of three pieces on a single site.
The total number of pieces from both players on a site is not limited.

---

## 6. State Update During a Turn

The state of sites is not updated until all three placements of a turn are completed.

After all three placements are completed:

1. Update Supply Site control states.
2. Update Scoring Site states.
3. Determine newly confirmed sites.

Changes caused by placements during the same turn do not affect the remaining placements of that turn.

---

## 7. Supply Sites

### Placement Limit

A player may place a maximum of two pieces on Supply Sites during one turn.

### Control

The controller of a Supply Site is determined by the number of pieces placed on it.

- A player with more pieces controls the Supply Site.
- If both players have the same number of pieces, the Supply Site is neutral.

The control state of an unconfirmed Supply Site may change through additional placements.

### Confirmation

When either player places three pieces on a Supply Site, the Supply Site becomes confirmed.

The player controlling the Supply Site at the time of confirmation becomes its permanent controller.

After confirmation:

- The controller cannot change.
- The Supply Site cannot be reversed.
- No additional pieces can be placed.

---

## 8. Scoring Sites

### Placement Condition

To place a piece on a Scoring Site, a player must use an adjacent Supply Site controlled by that player.

Each Supply Site can provide one piece placement to a Scoring Site.

Therefore, the number of pieces that can be placed on a Scoring Site is determined by the number of available controlled Supply Sites.

The maximum number of pieces that can be placed on a Scoring Site in one turn is three.

### Supply Site Usage Limit

The usage state of Supply Sites is reset at the beginning of each turn.

A single Supply Site cannot be used as a placement condition for multiple Scoring Sites during the same turn.

Multiple Supply Sites can be used for the same Scoring Site.

### States

Each Scoring Site has one of three states.

### Confirmed

When a player places three pieces on a Scoring Site, the Scoring Site becomes that player's confirmed site.

Confirmation is determined by the number of pieces after placement.

After confirmation, no additional pieces can be placed.

### Advantage

For an unconfirmed Scoring Site, the player with more pieces placed on the site has advantage.

### Neutral

If both players have the same number of pieces on an unconfirmed Scoring Site, it is neutral.

---

## 9. Game End

The game ends when both players have placed all of their pieces.

For the standard 4×4 board:

- Each player has 36 pieces.
- Each player takes 12 turns.

The game ends immediately after the third placement of the final turn.

---

## 10. Winning Condition

Only Scoring Sites are used to determine the winner.

The winner is determined by comparing the following in order.

### 1. Number of Confirmed Scoring Sites

The player with more confirmed Scoring Sites wins.

### 2. Number of Advantage Scoring Sites

If the number of confirmed sites is equal, the player with more advantage Scoring Sites wins.

### 3. Number of Pieces on Scoring Sites

If both confirmed and advantage counts are equal, the player with more total pieces placed on Scoring Sites wins.

### Draw

If all comparisons are equal, the game is a draw.

---

## 11. Game Characteristics

Heitan is an abstract strategy game where players build supply networks and compete for control of Scoring Sites.

Key characteristics:

- Managing Supply Sites and choosing where to use them is important.
- Players must decide between securing confirmed sites or gaining advantage across multiple sites.
- Balancing concentrated placement and distributed placement is central to strategy.
