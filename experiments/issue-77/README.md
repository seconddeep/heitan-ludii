# Issue 77: 7x7 piece-count sensitivity

This directory preregisters the 7x7 resource-sensitivity experiment. The
definitions, comparison directions, sample sizes, and interpretation order
below are frozen before any production aggregate is inspected. The 84- and
96-piece configurations are Issue 77 experiment conditions; they do not
change `docs/rules-ja.md` or `docs/rules.md`.

## Conditions and samples

The 7x7 topology remains 64 Supply Points, 49 Objectives, and 113 total
points. Exactly three placements form every turn.

The `7x7-84` and `7x7-96` game options were temporary experiment conditions
and were removed from the current game definition after this experiment was
completed. Use commit `3d22faa` when reproducing trial generation or replay
that requires those historical options.

| Pieces/player | Total placements | Turns | Advantage weight | Secured weight |
| ---: | ---: | ---: | ---: | ---: |
| 72 | 144 | 48 | 73 | 3650 |
| 84 | 168 | 56 | 85 | 4250 |
| 96 | 192 | 64 | 97 | 4850 |

All available 72-piece trials are reused from Issue 73: Seeded Random 100
games and UCT 100, 500, and 1000 at 50 games each. No 72-piece game is
regenerated. Matching new samples are generated only for 84 and 96 pieces.

Before outcome analysis, an audit found that all 250 trial hashes recorded in
the committed Issue 73 manifest differ from both the committed trial blobs and
the CRLF working-tree bytes. This is a pre-existing provenance inconsistency,
not an Issue 77 game-definition change. Issue 77 preserves each recorded
Issue 73 hash, pins the current trial using SHA-256 after CRLF-to-LF
normalization, legally replays it, and stops unless the replayed game summaries
and every placement match the separately pinned Issue 73 raw outputs exactly.
The exception count and procedure are frozen in `config.json` before aggregate
outcomes are inspected.

UCT 1000 is primary. Seeded Random, UCT 100, and UCT 500 are sensitivity
conditions. Operational-only smoke may justify reducing a sensitivity sample,
but the final decision must be recorded in this file and `config.json` before
any production outcome or aggregate is inspected. Primary sample sizes remain
50 new games per budget.

## Frozen contrasts and inference

Every contrast has an immutable direction:

1. `84 - 72`
2. `96 - 72`
3. `96 - 84`

The analyzer records minuend and subtrahend explicitly. Tests must verify the
direction of the point estimate and both interval endpoints for all three
contrasts. Primary intervals are two-sample game-level 95% percentile
bootstrap intervals with 2,000 replicates and the fixed seed in `config.json`
plus a deterministic contrast/metric offset.

## Smoke-information firewall

Smoke trials are never analysis inputs. Before runtime freeze, inspection is
limited to elapsed time, exit status, expected file/trial counts, and legal
replay status. Winners, scores, placement shares, and all derived metrics must
not be printed or inspected. Production aggregation cannot run while
`runtime_freeze.status` is not `frozen`.

## Frozen definitions

Issue 73's nine-region mapping and its direct reuse of Issue 65 concurrent
fronts, Issue 68 dormancy/revisit state machines, and Issue 70 late-game
classification remain unchanged. The only mechanical parameters that vary are
piece budget, total turns/placements, and scoring weights.

The fixed spatial window remains four turns and exactly 12 placements.
Normalized progress uses each condition's own 48, 56, or 64 turns. Raw-turn
and normalized-progress results remain separate. Fixed follow-up windows and
normalized progress-band analyses are reported separately.

Counts for secured points, resolution, and late Objective play are reported as
raw per-game values and, where applicable, normalized by total placements and
the 49 available Objectives. Higher raw counts alone are not interpreted as
improvement.

## Validation stop conditions

Analysis stops unless all of the following hold:

- all three Ludii configurations load with the unchanged 113-site topology;
- every trial replays legally and ends naturally at 144, 168, or 192 moves;
- every turn has exactly three placements and each player places its budget;
- reconstructed lexicographic scores and winners match Ludii;
- all 113 sites map one-to-one to the frozen nine regions;
- reused Issue 73 artifacts match their pinned SHA-256 values, all 250 known
  source-manifest trial-hash mismatches are accounted for, each current trial
  matches its canonical LF hash, and its replay matches pinned Issue 73 game
  and placement rows exactly;
- seeds, game keys, paths, and hashes are unique; and
- progress, censoring, revisit lag, and the three contrast directions pass
  automated tests for all game lengths.

## Interpretation order

1. spatial breadth beyond the 72-piece baseline;
2. backlog and selective abandonment relative to active-front breadth;
3. whether revisits lead to resolution;
4. conversion beyond the mechanical effect of more placements; and
5. growth of already-settled or mechanically forced late play.

The final report may conclude resource-limited fragmentation, board-size
saturation, an overextended game, or a mixed result. Non-monotonic and
contradictory results are reported directly.

## Intended commands

```powershell
./experiments/issue-77/scripts/run-experiments.ps1 -Smoke -Parallelism 4
./experiments/issue-77/scripts/run-experiments.ps1 -Parallelism 6
./experiments/issue-77/scripts/run-analysis.ps1
```

Requirements: Ludii Player 1.3.14, Java 21, Node.js 24 or later, and Windows
PowerShell 5.1 or later.

## Runtime freeze decision

Frozen before production generation and without inspecting any winner, score,
or analysis metric: **retain all preregistered sample sizes**. One operational
smoke game per new condition completed successfully and replayed legally.

| Budget | Condition | Seconds |
| ---: | --- | ---: |
| 84 | Seeded Random | 0.442 |
| 84 | UCT 100 | 150.591 |
| 84 | UCT 500 | 918.676 |
| 84 | UCT 1000 | 1643.992 |
| 96 | Seeded Random | 0.288 |
| 96 | UCT 100 | 197.926 |
| 96 | UCT 500 | 1160.148 |
| 96 | UCT 1000 | 1861.943 |

With six parallel workers, the complete 500-game generation is operationally
practical despite the longer 96-piece UCT conditions. Smoke artifacts remain
excluded from every production manifest and aggregate.
