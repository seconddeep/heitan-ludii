# Heitan Board Definition

## 1. Board Overview

Heitan uses a 4×4 square grid board.

The board consists of two types of sites:

- Supply Sites
- Scoring Sites

## Supply Sites

Supply Sites are placed on grid intersections.

- 5 × 5 layout
- Total: 25 sites

Coordinates:

    S00 ─ S01 ─ S02 ─ S03 ─ S04
     │     │     │     │     │
    S10 ─ S11 ─ S12 ─ S13 ─ S14
     │     │     │     │     │
    S20 ─ S21 ─ S22 ─ S23 ─ S24
     │     │     │     │     │
    S30 ─ S31 ─ S32 ─ S33 ─ S34
     │     │     │     │     │
    S40 ─ S41 ─ S42 ─ S43 ─ S44

---

## Scoring Sites

Scoring Sites are placed at the center of each grid cell.

- 4 × 4 layout
- Total: 16 sites

Coordinates:

    C00   C01   C02   C03

    C10   C11   C12   C13

    C20   C21   C22   C23

    C30   C31   C32   C33

---

# 2. Connections

Each Scoring Site is connected to the four surrounding Supply Sites.

## Connection Table

| Scoring Site | Connected Supply Sites |
| ------------ | ---------------------- |
| C00          | S00, S01, S10, S11     |
| C01          | S01, S02, S11, S12     |
| C02          | S02, S03, S12, S13     |
| C03          | S03, S04, S13, S14     |
| C10          | S10, S11, S20, S21     |
| C11          | S11, S12, S21, S22     |
| C12          | S12, S13, S22, S23     |
| C13          | S13, S14, S23, S24     |
| C20          | S20, S21, S30, S31     |
| C21          | S21, S22, S31, S32     |
| C22          | S22, S23, S32, S33     |
| C23          | S23, S24, S33, S34     |
| C30          | S30, S31, S40, S41     |
| C31          | S31, S32, S41, S42     |
| C32          | S32, S33, S42, S43     |
| C33          | S33, S34, S43, S44     |

---

# 3. Site Types

| Type         | Count | Description                             |
| ------------ | ----: | --------------------------------------- |
| Supply Site  |    25 | Used to provide supply to Scoring Sites |
| Scoring Site |    16 | Sites that determine the winner         |
