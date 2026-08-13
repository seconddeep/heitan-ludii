# Issue 50 regression check

`HeitanRegression.java` compares a baseline and candidate Heitan definition
while replaying existing complete 4x4 trials. It first checks:

- 41 graph vertices and the exact set of 64 Objective-to-Supply edges;
- the 25-site `SupplyPoints` and 16-site `Objectives` regions;
- every named region from `S00` through `S44` and `O00` through `O33`.

At every replayed position it then checks:

- mover identity;
- the complete legal decision set (`mover`, `from`, and `to`);
- every Piece owner and state at every stack level on all 41 sites;
- natural end, move and turn counts, end type, scores, and winner.

Run with Ludii Player 1.3.14 and one or more directories of `.trl` files:

```powershell
java -cp C:\path\to\Ludii-1.3.14.jar `
    experiments\issue-50\HeitanRegression.java `
    C:\path\to\baseline\Heitan.lud `
    games\Heitan.lud `
    experiments\issue-32\results\trials\uct-10000-self-play `
    experiments\issue-32\results\trials\uct-3000-self-play
```
