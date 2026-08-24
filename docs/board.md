# Heitan Board Definition

## 1. Board Structure

Heitan uses a square grid structure.

The diagrams and tables below use a 4×4 grid as an example.

The board consists of two types of points:

- Supply Points
- Objectives

### Supply Points

Supply Points are located at the intersections of the grid.

In the 4×4 example:

- 5×5 layout
- 25 Supply Points in total

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

### Objectives

Objectives are located at the center of each square.

In the 4×4 example:

- 4×4 layout
- 16 Objectives in total

Coordinates:

    O00   O01   O02   O03

    O10   O11   O12   O13

    O20   O21   O22   O23

    O30   O31   O32   O33

---

## 2. Connections

Each Objective is connected to the four Supply Points at the corners of its square.

The following table shows the connections for the 4×4 example.

| Objective | Connected Supply Points |
| --------- | ----------------------- |
| O00       | S00, S01, S10, S11      |
| O01       | S01, S02, S11, S12      |
| O02       | S02, S03, S12, S13      |
| O03       | S03, S04, S13, S14      |
| O10       | S10, S11, S20, S21      |
| O11       | S11, S12, S21, S22      |
| O12       | S12, S13, S22, S23      |
| O13       | S13, S14, S23, S24      |
| O20       | S20, S21, S30, S31      |
| O21       | S21, S22, S31, S32      |
| O22       | S22, S23, S32, S33      |
| O23       | S23, S24, S33, S34      |
| O30       | S30, S31, S40, S41      |
| O31       | S31, S32, S41, S42      |
| O32       | S32, S33, S42, S43      |
| O33       | S33, S34, S43, S44      |
