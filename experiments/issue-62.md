# Issue 62: 3x3 Heitan as the small-scale baseline

## Summary

The 3x3 board is a valid small-scale baseline, but the evidence supports a
qualified rather than universal `3x3 < 4x4 < 6x6` progression.

The clearest scale sequence appears over the frozen 12-placement window and
in Supply-site concentration. At UCT 100, 500, and 1000, 3x3 has the lowest
four-turn spatial entropy and 6x6 the highest. Stronger 3x3 search also puts a
larger share of Pieces on Supply, concentrates those placements more heavily,
and converts Secured Supply into later Objective access more often than the
larger boards. These results support a compressed, tactically coupled 3x3.

Per-turn breadth does not scale monotonically. In particular, 4x4 is slightly
narrower than 3x3 at UCT 100 and UCT 1000, while 6x6 is broadest at those
levels. Leader reversal and victory layer also have important non-monotonic
results. The data therefore support broader multi-turn spatial play with board
size more strongly than a universal increase in simultaneous per-turn fronts.

## Samples and validation

Production used Ludii Player 1.3.14 and the preregistered samples:

| Board | Random | UCT 100 | UCT 500 | UCT 1000 |
| --- | ---: | ---: | ---: | ---: |
| 3x3 | 100 | 100 | 100 | 100 |
| 4x4 | 100 | 100 | 100 | 100 |
| 6x6 | 100 | 50 | 50 | 50 |

The 400 new 3x3 games used seeds `620000`--`620399`. Generation took
2358.773 wall-clock seconds at parallelism 12. No runtime reduction was made.

All 1,050 analyzed trials passed provenance and replay validation:

- 86,400 placements and 28,800 Heitan turns;
- natural board-specific completion;
- exactly three placements per turn;
- legal replay of every saved placement;
- replayed winner and independent score matching the saved trial; and
- no duplicate game keys, seeds, or trial SHA-256 hashes.

## Placement layers and securing

Supply placement share shows the clearest small-to-large ordering at stronger
search:

| Agent | 3x3 | 4x4 | 6x6 |
| --- | ---: | ---: | ---: |
| Random | 69.33% | 66.90% | 61.52% |
| UCT 100 | 56.06% | 54.44% | 55.74% |
| UCT 500 | 52.87% | 46.64% | 45.61% |
| UCT 1000 | 54.20% | 45.60% | 40.86% |

UCT 100 is not monotonic, but UCT 500 and 1000 show substantially greater
Supply investment on 3x3. At UCT 1000, the corresponding Objective shares are
45.80%, 54.40%, and 59.14%.

The proportion of Secured player-Supplies later used for Objective placement
also orders cleanly at every tested UCT level:

| Agent | 3x3 | 4x4 | 6x6 |
| --- | ---: | ---: | ---: |
| UCT 100 | 52.94% | 45.67% | 41.41% |
| UCT 500 | 70.16% | 64.49% | 55.91% |
| UCT 1000 | 79.20% | 72.22% | 56.32% |

Random is an exception (`37.18%`, `36.41%`, `44.50%`). The UCT result is
consistent with tighter coupling between Supply control and later Objective
play on the smaller board rather than a purely geometric artifact seen under
all policies.

The first securing turn is earlier in absolute turn numbers on 3x3, but the
games have 18, 24, and 48 turns respectively. Those raw turn values must not
be interpreted as a frozen equal-progress comparison; progress checkpoints
provide the appropriate phase-aligned view.

At UCT 1000, Secured Objectives per game are 6.49 of 9 on 3x3, 10.66 of 16 on
4x4, and 23.44 of 36 on 6x6. Thus 3x3 has the highest secured density even
though its absolute count is necessarily smallest.

## Per-turn spatial allocation

The three-region (`1+1+1`) share and mean regions used are:

| Agent | 3x3 | 4x4 | 6x6 |
| --- | ---: | ---: | ---: |
| Random | 66.28% / 2.645 | 71.83% / 2.706 | 68.79% / 2.674 |
| UCT 100 | 65.39% / 2.639 | 64.96% / 2.632 | 70.83% / 2.698 |
| UCT 500 | 59.72% / 2.576 | 63.38% / 2.613 | 62.88% / 2.609 |
| UCT 1000 | 58.00% / 2.554 | 56.83% / 2.541 | 61.63% / 2.596 |

The Random ordering is `3x3 < 6x6 < 4x4`. UCT 500 puts 3x3 lowest, but UCT
100 and 1000 put 4x4 slightly below 3x3. Therefore simultaneous per-turn
breadth does not form a stable three-size monotonic sequence. The reliable
conclusion is narrower: 6x6 is broadest at UCT 100 and 1000, while 3x3 and
4x4 exchange order depending on search level.

## Fixed 12-placement spatial breadth

Mean normalized entropy over the frozen four-turn window is:

| Agent | 3x3 | 4x4 | 6x6 |
| --- | ---: | ---: | ---: |
| Random | 0.8008 | 0.8189 | 0.8096 |
| UCT 100 | 0.7903 | 0.8024 | 0.8163 |
| UCT 500 | 0.7603 | 0.7701 | 0.7957 |
| UCT 1000 | 0.7357 | 0.7421 | 0.7840 |

All UCT levels show `3x3 < 4x4 < 6x6`. Largest-region share and HHI move in
the opposite direction, as expected for greater concentration, and coverage
moves with entropy. For UCT 1000, largest-region share is `0.3277`, `0.3246`,
and `0.2961`, while HHI is `0.2288`, `0.2249`, and `0.2027`.

This is a fixed-placement comparison, not a fixed-progress-width comparison.
Four turns are 22.2% of a 3x3 game, 16.7% of a 4x4 game, and 8.3% of a 6x6
game. The result supports broader allocation over the same 12 placements on
larger boards, but it must not be described as the same fraction of play.

At the separately normalized UCT 1000 checkpoints, recent-window entropy is
lower on 3x3 than 6x6 at every checkpoint. The 3x3/4x4 ordering varies by
checkpoint, reinforcing that the strongest stable contrast is between the
smallest and largest boards rather than strict monotonicity everywhere.

## Supply-site concentration

Mean per-game Supply-placement HHI rises with compression at every search
level:

| Agent | 3x3 | 4x4 | 6x6 |
| --- | ---: | ---: | ---: |
| Random | 0.0812 | 0.0565 | 0.0295 |
| UCT 100 | 0.0919 | 0.0624 | 0.0312 |
| UCT 500 | 0.1068 | 0.0723 | 0.0344 |
| UCT 1000 | 0.1148 | 0.0791 | 0.0370 |

Some of this ordering is mechanically induced by the available site counts
(16, 25, and 49), so HHI alone is not evidence of strategic selection.
However, search consistently raises concentration within each board. On 3x3
UCT 1000, `S12` receives 13.80% of Supply placements and appears at the top in
80.75% of game-bootstrap resamples. Exact cross-board site ranks remain
exploratory because site identities and geometries are not equivalent.

## Deciding layer and lead persistence

At UCT 1000, games decided first by Secured Objectives account for 52 of 100
on 3x3, 52 of 100 on 4x4, and 20 of 50 on 6x6. Pieces decide 5, 11, and 13
respectively. UCT 500 similarly has a larger Secured-layer share on 3x3
(59%) than on 4x4 (44%) or 6x6 (40%). This suggests that the compressed board
more often resolves at the highest scoring layer under stronger search, but
the other conditions are not monotonic.

The preregistered primary reversal measure uses the full lexicographic leader,
excludes checkpoint ties and eventual draws from its denominator, and counts
a reversal when that leader differs from the final winner. It does not show a
coherent size ordering. At the 90% checkpoint under UCT 1000, reversal rates
are 27.78% on 3x3, 48.24% on 4x4, and 20.00% on 6x6. Other checkpoints and
search levels also change order. Midgame persistence is therefore preserved
as a strategic feature on 3x3, but the present samples do not support a simple
compression-to-persistence law.

Seat results are also unstable across conditions, including strong Player 2
advantages in several UCT samples. They are reported descriptively and are
not treated as solved balance estimates.

## Conclusion

The evidence supports the following qualified interpretation:

- **3x3:** concentrated Supply investment, high later use of Secured Supply,
  and the narrowest multi-turn spatial allocation under UCT;
- **4x4:** an intermediate multi-turn scale, but not invariably intermediate
  in per-turn breadth or leader persistence; and
- **6x6:** broader 12-placement spatial play and generally broader per-turn
  play at comparable UCT levels, with less concentrated Supply use.

Heitan therefore shows a coherent 3x3-to-6x6 scaling structure in multi-turn
spatial breadth and Supply coupling, but not a universal monotonic sequence
for every metric. The result is limited by 50-game 6x6 UCT samples, shallow
UCT iteration limits, unequal game lengths, the fixed-placement window, and
the geometry imposed by a common nine-region normalization.

## Reproduction

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  .\experiments\issue-62\scripts\run-experiments.ps1 `
  -Parallelism 12 -BatchSize 5

powershell -NoProfile -ExecutionPolicy Bypass -File `
  .\experiments\issue-62\scripts\run-analysis.ps1
```

The exact source and environment hashes are recorded in
`experiments/issue-62/results/environment-run.json`,
`experiments/issue-62/results/environment.json`, and
`experiments/issue-62/results/trial-sources.csv`.
The full raw turn-state table is committed as
`experiments/issue-62/results/raw/turn-states.csv.zip`; the analysis command
regenerates its ignored uncompressed CSV form.
