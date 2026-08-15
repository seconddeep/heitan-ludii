# Issue 73: 7x7 scale analysis

## Summary

The preregistered primary contrast supports a **mixed result: spatial
saturation accompanied by fragmentation of unresolved play**, rather than
continued strategic scaling from 6x6 to 7x7.

At UCT 1000, four-turn placement breadth is statistically indistinguishable
between 6x6 and 7x7. In contrast, 7x7 carries more active fronts, dormant
fronts, and unresolved backlog. It also secures fewer Supply points and
Objectives, leaves more late fronts unresolved or selectively abandoned, and
has a larger late placement-versus-opportunity largest-share gap. Revisit and
focus-carryover measures are mostly unchanged. Thus the extra active regions
do not come with broader realized placement or more effective resolution.

Every difference below is `7x7 - 6x6`. Intervals are the preregistered 95%
two-sample game-bootstrap percentile intervals with 2,000 replicates and seed
730073.

## Validation

All 250 new 7x7 trials passed generation, provenance, legal replay, and
independent reconstruction checks.

| Item | Validated total |
| --- | ---: |
| Seeded Random games | 100 |
| UCT 100 games | 50 |
| UCT 500 games | 50 |
| Primary UCT 1000 games | 50 |
| Placements | 36,000 |
| Turns | 12,000 |
| Primary 6x6 / 7x7 games | 50 / 50 |

Every game ended naturally after 144 placements and 48 turns, every turn had
three placements, and each player placed 72 pieces. Ludii winners and scores
matched the independently reconstructed results using Advantage weight 73 and
Secured weight 3650. Seeds, game keys, trial paths, and trial SHA-256 values
were unique. All point and legal-target region assignments were unique, the
nine capacities were exactly `13/12/13/12/13/12/13/12/13`, regional totals
matched board totals, and every reused artifact hash matched `config.json`.

The Issue 65, 68, and 70 functions were imported directly. No semantic change
was needed for 7x7; only the preregistered board constants were supplied.

## Primary UCT 1000 contrast

### 1. Spatial breadth saturates

| Measure | 6x6 | 7x7 | Difference [95% CI] |
| --- | ---: | ---: | ---: |
| Normalized entropy | 0.7840 | 0.7912 | +0.0072 [-0.0026, +0.0163] |
| Largest-region share | 0.2961 | 0.2924 | -0.0037 [-0.0120, +0.0046] |
| HHI | 0.2027 | 0.1996 | -0.0031 [-0.0078, +0.0018] |
| Region coverage | 0.7114 | 0.7215 | +0.0101 [-0.0021, +0.0225] |
| Regions used per turn | 2.5958 | 2.6067 | +0.0108 [-0.0192, +0.0429] |

None of the preregistered whole-game spatial measures distinguishes 7x7 from
6x6. The fixed 12-placement windows at 25%, 50%, 75%, and 90% likewise show
no clear entropy, concentration, or coverage difference: every corresponding
bootstrap interval includes zero. This is the highest-priority evidence and
supports saturation of realized spatial spread.

### 2. Concurrent and unresolved fronts increase

| Measure | 6x6 | 7x7 | Difference [95% CI] |
| --- | ---: | ---: | ---: |
| Mean active fronts | 4.8100 | 5.0663 | +0.2563 [+0.0746, +0.4358] |
| Opportunity-adjusted activity | 4.8896 | 5.1230 | +0.2334 [+0.0354, +0.4462] |
| Mean dormant active fronts | 1.3996 | 1.4917 | +0.0921 [+0.0113, +0.1725] |
| Turns with at least two dormant fronts | 0.4425 | 0.4854 | +0.0429 [+0.0054, +0.0800] |
| Mean unresolved backlog | 2.7696 | 2.9483 | +0.1788 [+0.0483, +0.3183] |
| Qualifying departures per game | 39.00 | 41.52 | +2.52 [+0.30, +4.76] |

More fronts are recently active on 7x7, including after adjustment for legal
opportunities. However, the increase is paired with more dormancy and backlog,
not with wider placement distributions. Multi-active rate, longest
multi-front run, both-invested fronts, and mixed local leadership show no
clear primary difference.

### 3. Revisit and carryover behavior is stable

| Measure | 6x6 | 7x7 | Difference [95% CI] |
| --- | ---: | ---: | ---: |
| Observed revisit rate | 0.9902 | 0.9911 | +0.0009 [-0.0054, +0.0069] |
| Mean revisit lag | 4.4853 | 4.5615 | +0.0762 [-0.1136, +0.2764] |
| Normalized revisit lag | 0.0934 | 0.0950 | +0.0016 [-0.0023, +0.0056] |
| Revisit within four turns | 0.5997 | 0.5987 | -0.0010 [-0.0305, +0.0301] |
| Unresolved focus-switch carryover | 0.8307 | 0.7954 | -0.0353 [-0.1369, +0.0548] |

The additional dormant and unresolved fronts are not explained by a clear
change in whether or how quickly departed fronts are revisited. Focus-switch
carryover duration and later revisit also remain indistinguishable.

### 4. Resolution weakens on 7x7

| Measure | 6x6 | 7x7 | Difference [95% CI] |
| --- | ---: | ---: | ---: |
| Secured Supply per game | 1.74 | 1.06 | -0.68 [-1.08, -0.28] |
| Secured Objectives per game | 23.44 | 21.64 | -1.80 [-2.66, -0.98] |
| Final-band front survival | 0.9454 | 0.9789 | +0.0335 [+0.0074, +0.0587] |
| Resolved or settled late fronts | 0.7660 | 0.6189 | -0.1470 [-0.2033, -0.0918] |
| End-censored late fronts | 0.1177 | 0.1722 | +0.0545 [+0.0099, +0.0997] |
| Selectively abandoned late fronts | 0.1163 | 0.2089 | +0.0925 [+0.0516, +0.1323] |

Supply and Objective placement shares are similar, so the lower secured
counts do not arise from a large allocation shift. At 75% progress the
Objective deficit is already -2.12 [-3.02, -1.20], and at 90% it remains
-2.06 [-2.90, -1.20]. More early-active regions survive into the final band,
yet substantially fewer are resolved or settled and more are ultimately
abandoned or censored. This is the strongest evidence for fragmentation
rather than useful continued breadth.

### 5. The late game remains consequential but more thinly resolved

| Measure | 6x6 | 7x7 | Difference [95% CI] |
| --- | ---: | ---: | ---: |
| Final-band active fronts | 5.6850 | 5.9667 | +0.2817 [+0.0117, +0.5600] |
| Final-band backlog | 3.3417 | 3.5650 | +0.2233 [+0.0067, +0.4350] |
| Placement/opportunity largest-share gap | 0.0631 | 0.0961 | +0.0331 [+0.0141, +0.0508] |
| Late Objective placements per game | 24.98 | 26.80 | +1.82 [+0.36, +3.28] |
| Region fixed before Objective placement | 0.3302 | 0.2254 | -0.1049 [-0.1574, -0.0513] |

Late Objective placements change target state, local lead, securing status,
and the global comparison at similar rates on both boards. The global result
is conservatively mutable before more than 99% of these placements on both
boards. The lower already-fixed rate on 7x7 means its late Objective play is
not simply more mechanical filling. Instead, it coexists with a larger
unresolved field and greater placement concentration relative to the legal
opportunity distribution.

## Secondary and sensitivity analyses

The 3x3--7x7 series is secondary. At UCT 1000, normalized entropy rises
`0.7357 -> 0.7421 -> 0.7840 -> 0.7912`, while active fronts rise
`2.7756 -> 3.3600 -> 4.8100 -> 5.0663`. Dormant fronts and backlog also rise
monotonically. The small entropy increment from 6x6 to 7x7, together with the
continued unresolved-front increase, agrees with the primary mixed finding;
the series is not used to override it.

The concurrent-front direction is robust to the preregistered active window:
the 7x7-minus-6x6 mean-active difference is +0.1608 at two turns and +0.3100
at six turns. The dormant-front direction is also unchanged: +0.1788 at
`k=1` and +0.0396 at `k=3`. These sensitivity values are descriptive; the
primary intervals remain those for the frozen four-turn window and `k=2`.
Seeded Random, UCT 100, and UCT 500 outputs are retained in
`secondary-series.csv` for search-level diagnostics and do not redefine the
primary contrast.

## Interpretation

The fixed interpretation hierarchy yields this classification:

1. Realized multi-turn spatial breadth saturates from 6x6 to 7x7.
2. Concurrent activity grows, but unresolved and dormant activity grows with
   it.
3. Revisit and carryover behavior does not materially improve or deteriorate.
4. Securing falls and late selective abandonment rises, indicating fragmented
   resolution across the larger set of fronts.
5. Late play remains consequential, so the pattern is not reducible to
   mechanical endgame filling or opportunity density alone.

The result is therefore **spatial saturation plus fragmentation of unresolved
fronts**. It is intentionally reported as mixed: the active-front increase is
real, but the preregistration forbids treating that fact alone as continued
scaling, and the higher-priority spatial and resolution measures do not
support that interpretation.

## Limitations

- The primary samples contain 50 independent games per board; smaller effects
  remain uncertain even with game-level bootstrap intervals.
- Nine normalized regions preserve comparability but aggregate different
  absolute point counts and local graph structures.
- Equal UCT iteration limits do not equalize wall time, branching burden, or
  convergence quality between boards.
- The fixed four-turn window has equal raw duration on 6x6 and 7x7 because
  both have 48 turns, but it is still an operational definition rather than a
  learned strategic horizon.
- Legal opportunities deduplicate target points and do not weight alternative
  Supply sources or within-turn move sequences.
- These self-play samples characterize the configured agents, not optimal play
  or human strategic intent.

## Reproduction

From the repository root, with Ludii Player 1.3.14 at the configured path:

```powershell
# Operational-only smoke; does not display or inspect outcomes or metrics.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\experiments\issue-73\scripts\run-experiments.ps1 -Smoke -Parallelism 4

# Full generation, or recovery of missing games after interruption.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\experiments\issue-73\scripts\run-experiments.ps1 -Parallelism 6
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\experiments\issue-73\scripts\run-experiments.ps1 -Parallelism 6 -Resume

# Manifest/hash verification, legal Java replay, Node tests, and aggregation.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\experiments\issue-73\scripts\run-analysis.ps1
```

The final command regenerates every aggregate, checks the pinned historical
artifacts, compresses the large point-state table, and records Java, Node,
Ludii, Git, seed, manifest, trial, and artifact provenance.
