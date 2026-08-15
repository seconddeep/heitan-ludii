# Issue 73: 7x7 Heitan scale analysis

This directory preregisters the 7x7 scale analysis requested by Issue 73.
The definitions and decision rules below are frozen before any production
aggregate is inspected.

## Primary contrast and samples

The primary contrast is **7x7 UCT 1000 minus 6x6 UCT 1000**. The primary
sample contains 50 new 7x7 UCT 1000 games and the 50 validated 6x6 UCT 1000
games from Issues 58 and 60. For every primary measure, the main result is:

```text
mean(7x7 UCT 1000) - mean(6x6 UCT 1000)
```

with a two-sample game bootstrap 95% percentile interval. The bootstrap
resamples games independently within each board, uses 2,000 replicates, and
uses the fixed seed in `config.json` plus a deterministic metric-key offset.

The planned 7x7 sensitivity samples are Seeded Random 100 games, UCT 100 at
50 games, and UCT 500 at 50 games. The 3x3--7x7 sequence and all lower-search
comparisons are secondary analyses; they do not replace the primary 6x6
versus 7x7 contrast.

## Smoke-information firewall

Smoke runs are excluded from production analysis. Before production sample
sizes are frozen, smoke inspection is restricted to operational information:

- wall-clock and per-condition elapsed time;
- process exit success or failure;
- expected file and trial counts; and
- whether generated trials can be loaded and legally replayed by the harness.

Smoke winners, scores, placement shares, spatial measures, front measures,
revisit measures, late-game measures, and every other game or analysis
outcome must not be displayed or inspected. `run-experiments.ps1 -Smoke`
writes only the permitted operational summary outside the individual raw
runner files. The raw runner files and trials exist solely for automated
validation and are not analysis inputs. Any sensitivity-sample reduction is
recorded here and in `config.json` using only the permitted operational
information, before production aggregation is run.

## Frozen nine-region mapping

The Issue 62/65 normalized `LL`--`HH` mapping is unchanged. Each normalized
coordinate axis is assigned to its nearest value among `1/6`, `1/2`, and
`5/6`, with the existing middle-first and low-before-high tie rules.

For 7x7, Supply coordinates have fixed axis bands `3 / 2 / 3` and Objective
coordinates have fixed axis bands `2 / 3 / 2`. Consequently:

- `LL`, `LH`, `MM`, `HL`, and `HH` contain 13 points each;
- `LM`, `ML`, `MH`, and `HM` contain 12 points each; and
- all 113 board points map to exactly one region.

The mapping is validated before aggregation and is not retuned after results
are observed.

## Frozen placement and spatial definitions

Issue 62 definitions are reused unchanged:

- exactly three placements form a Heitan turn;
- per-turn allocation is `3`, `2+1`, or `1+1+1` by region;
- the fixed window is four turns, hence exactly 12 placements;
- normalized entropy uses `log(9)`;
- largest-region share, HHI, and coverage use the same 12 placements; and
- progress checkpoints are 25%, 50%, 75%, and 90%, using
  `ceil(checkpoint * total_turns)`.

Supply/Objective shares, final Secured Supply and Objective counts, later use
of Secured Supply, and regions receiving placements per turn are reported.
Raw-turn and normalized-progress outputs remain separate.

## Frozen concurrent-front definitions

Issue 65 is reused without semantic change. At the end of turn `t`, a region
is active when it received placement in the four-turn window ending at `t`
and either both players placed there in that window or both players currently
have a Piece on an Unsecured point there. Local leadership remains the
lexicographic order Secured Objectives, Advantage Objectives, then Objective
Pieces. Dominant focus, focus-switch eligibility, mixed leadership, legal
target deduplication, opportunity share, and opportunity-adjusted activity
are unchanged. Two- and six-turn active windows are secondary sensitivity
checks.

## Frozen dormancy and revisit definitions

Issue 68 is reused without semantic change. Backlog, dormant active front,
the departure-cycle state machine, persistent and reactivation revisits,
terminal outcomes, raw and normalized revisit lag, and unresolved carryover
after a focus switch remain exactly as preregistered there. The primary
dormancy threshold is `k=2`; `k=1` and `k=3` are sensitivity checks. Fixed
four-turn and normalized-quarter follow-up diagnostics are unchanged.

## Frozen late-game definitions

Issue 70 is reused without semantic change. The progress bands, final-front
cohort, exclusive classification order, censoring rules, placement and legal
opportunity concentration, and Objective-placement consequence flags are
unchanged. The conservative local/global outcome bound uses the same formula;
the only mechanical extension is the already validated 7x7 board constants:

```text
Objectives = 49
Pieces per player = 72
Advantage weight = 73
Secured weight = 3650
```

This does not alter the bound's meaning or classification order.

## Definition-change register

No Issue 65, 68, or 70 semantic definition is changed at preregistration.
Adding board name `7x7`, 113 sites, 49 Objectives, the fixed regional
capacities above, and the 7x7 scoring constants is a mechanical domain
extension only. If another 7x7 adaptation proves necessary, aggregation must
stop until its reason, old definition, exact difference, semantic/mechanical
classification, and comparability effect are registered in this section and
in `config.json`.

## Interpretation hierarchy

The primary interpretation order is:

1. multi-turn spatial breadth;
2. concurrent active and unresolved fronts;
3. dormant fronts, revisits, and carryover;
4. saturation or fragmentation relative to 6x6; and
5. late-game consequence, legal opportunity, and resource density.

More active regions alone do not establish continued strategic scaling.
Continued scaling requires agreement among multiple primary contrasts.
Saturation is supported by broadly similar 6x6 and 7x7 measures.
Fragmentation additionally requires broader geometry accompanied by weaker
interaction, fewer revisits, less unresolved carryover, or comparable
evidence of regional isolation. Non-monotonic and contradictory results are
reported directly.

## Validation stop conditions

Every 7x7 production trial must have unique seed, game key, path, and SHA-256;
replay as legal Ludii moves; end naturally after 144 placements and 48 turns;
contain exactly three placements per turn; give each player 72 placements;
and reproduce the Ludii winner and score by independent reconstruction.
Every board target and legal target must map to exactly one frozen region.
Regional placement and legal-opportunity totals must match board totals.
Every reused artifact must match its pinned SHA-256. Any failure stops the
analysis.

## Intended commands

```powershell
./experiments/issue-73/scripts/run-experiments.ps1 -Smoke -Parallelism 4
./experiments/issue-73/scripts/run-experiments.ps1 -Parallelism 6
./experiments/issue-73/scripts/run-analysis.ps1
```

Requirements: Ludii Player 1.3.14, Java 21, Node.js 24 or later, and Windows
PowerShell 5.1 or later.

## Runtime freeze decision

Frozen before production generation and without inspecting any outcome or
analysis metric: **retain every preregistered sample size** (Seeded Random
100, UCT 100 at 50, UCT 500 at 50, and primary UCT 1000 at 50).

The one-game-per-condition smoke recorded only permitted operational data:
0.882 seconds for Seeded Random, 101.191 seconds for UCT 100, 516.548 seconds
for UCT 500, and 723.289 seconds for UCT 1000. All four processes exited
successfully, emitted the expected trial, and passed legal replay. Parallel
production execution therefore makes the planned samples practical. Smoke
outcomes and analysis metrics were not displayed or inspected, and all smoke
artifacts remain excluded from production analysis.
