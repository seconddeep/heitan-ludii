# Heitan Rule Specification

## 1. Game Overview

### Objective

The winner is determined by the state of Objectives at the end of the game.

Only Objectives are used to determine victory. Supply Points are not used for victory determination.

---

## 2. Players

Heitan is a two-player game.

- Player 1 (Black): First player
- Player 2 (White): Second player

Both players have the same number of Pieces.

---

## 3. Board

The board consists of a square grid.

Detailed board structure is defined in `board.md`.

There are two types of points on the board.

### Supply Points

Supply Points are located at the intersections of the grid.

### Objectives

Objectives are located at the center of each square.

Each Objective is connected to the four Supply Points at the corners of its square.

### Initial State

At the start of the game, no Pieces are placed on any point.

---

## 4. Turns

On each turn, a player must place exactly 3 Pieces.

The 3 Pieces may be distributed freely among 1 to 3 points.

Examples:

- Place 3 Pieces on one point
- Split the 3 Pieces between two points
- Place the 3 Pieces across three different points

Pieces may also be added to points that already contain Pieces.

Each player may have a maximum of 3 Pieces on a single point.

---

## 5. Supply Points

### Placement Conditions

A maximum of 2 Pieces may be placed on each Supply Point in a single turn.

### State

The state of a Supply Point is determined by the number of Pieces placed on it.

- More of your Pieces than your opponent's → Controlled
- Equal number of Pieces → Neutral

---

## 6. Objectives

### Placement Conditions

To place a Piece on an Objective, a player must use an adjacent Supply Point.

Only Supply Points Controlled by that player at the start of the turn may be used.

Using one Supply Point allows the player to place one Piece on the Objective.

Each Supply Point may be used only once per turn.

Multiple Supply Points may be used to place multiple Pieces on the same Objective.

The usage state of all Supply Points is reset at the start of each turn.

### State

The state of an Objective is determined by the number of Pieces placed on it.

- More of your Pieces than your opponent's → Advantage
- Equal number of Pieces → Neutral

---

## 7. Securing Points

At the end of a turn, if either player has 3 Pieces placed on a point, that point becomes Secured.

A Secured point has its state fixed and cannot receive any additional Pieces.

---

## 8. Game End

The game ends when both players have placed all of their Pieces and the final turn has ended.

---

## 9. Victory Conditions

Only Objectives are used to determine victory.

The following criteria are compared in order.

### 1. Secured Objectives

The player with more Secured Objectives wins.

### 2. Objectives with Advantage

If both players have the same number of Secured Objectives, the player with more Objectives in Advantage wins.

### 3. Pieces on Objectives

If both players have the same number of Secured Objectives and Objectives in Advantage, the player with more Pieces on Objectives wins.

### Draw

If all of the above are equal, the game is a draw.

---

## 10. Game Characteristics

Heitan is an abstract strategy game in which players build supply networks while competing for Objectives.

Key characteristics:

- Controlling Supply Points and choosing where to use them are important
- Players must decide whether to pursue Secured Objectives or gain Advantage across a wider area
- Balancing concentrated and distributed placement is central to the strategy
