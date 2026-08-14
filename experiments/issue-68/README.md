# Issue 68: dormant fronts and regional revisits

This directory preregisters the temporal-front analysis requested by Issue
68. All definitions in this file and `config.json` are frozen before the
production aggregate outputs are examined. No new games are generated.

## Samples and frozen inputs

The analysis reuses the legally replayed, provenance-checked outputs from
Issue 65. The primary UCT 1000 comparison contains 100 3x3 games from Issue
62, 100 4x4 games from Issue 30, and 50 6x6 games from Issues 58 and 60.
Seeded Random, UCT 100, and UCT 500 are sensitivity checks. The Issue 65
configuration, preregistration, game rows, placements, regional turn states,
and trial manifest are pinned by SHA-256 in `config.json`.

The frozen normalized `LL`--`HH` regions and the Issue 65 active-front rule
are unchanged. At the end of turn `t`, a region is active when it received at
least one placement in turns `t-3` through `t` and either both players placed
there in that window or both players currently have a Piece on an Unsecured
point there.

## Dormancy and backlog

For region `r` and turn `t`, `placement(r,t)` is the number of the turn's
three placements assigned to `r`.

- A backlog region is active at the end of `t` and has
  `placement(r,t) = 0`.
- A dormant active front has been a backlog region for `k` consecutive turns.
- The primary threshold is `k = 2`; `k = 1` and `k = 3` are sensitivity
  checks.

Because the active rule uses a four-turn recent-investment window, an
unattended region can remain active for at most three turns. The primary
threshold is fixed at the middle of that observable range.

## Departure-cycle state machine

A candidate departure starts on the first zero-placement turn after a turn
on which the region both received placement and was active. The candidate
turn must also end active. It becomes a qualifying departure only if the
region remains active through the selected dormancy threshold. A candidate
that loses active status before qualifying is discarded.

After qualification, the cycle ends in exactly one of these states:

- `persistent_revisit`: the region remains active at every turn through the
  turn immediately before its first later placement, and that placement turn
  ends active. The return placement may itself refresh the recent-investment
  condition; this does not change the classification because activity did
  not lapse before the return.
- `reactivation_revisit`: the region is inactive for at least one turn after
  qualification, but both players' Unsecured presence continues, and its
  first later placement makes the region active at the end of that turn.
- `never_revisited_resolved`: before a later placement, the region is both
  inactive and no longer has both players' Unsecured presence.
- `never_revisited_nonfront_return`: a later placement occurs, but the region
  is not active at the end of that turn.
- `right_censored`: natural game end is reached without one of the preceding
  endpoints while the region remains active or retains both players'
  Unsecured presence.

An inactive turn caused only by expiry of the recent-investment window does
not close a cycle while both players' Unsecured presence remains. A revisit
closes the cycle; a later departure starts a new cycle. Revisit lag is
`revisit_turn - departure_turn`, so it equals the number of intervening
zero-placement turns. Normalized lag divides raw lag by total game turns.

## Focus switching with unresolved carryover

The Issue 65 focus definition is unchanged. A unique `3` or `2+1` plurality
defines the turn's dominant region; `1+1+1` has no dominant focus. Only
adjacent turns with a dominant focus at both endpoints are eligible. A
no-focus turn is not skipped across.

A focus switch carries the previous region unresolved when that region is
active at the end of the new-focus turn. Carryover duration is the consecutive
active run beginning at that endpoint. A later revisit requires a subsequent
placement into the previous region that ends active; secondary placement on
the switch turn is not itself a later revisit.

## Aggregation and timing controls

Turn prevalence, backlog, and run measures are computed within each game and
then average games equally. Event rates distinguish revisits, observed never
revisited endpoints, and right censoring. Event-time tables retain censoring
and competing endpoints separately. Confidence intervals use 2,000
game-cluster bootstrap replicates with seed 680068.

Raw-turn and game-length-normalized timing are both reported. Two fixed
opportunity diagnostics guard against attributing a result only to longer
games:

1. revisit within four turns among departures with at least four turns left;
2. revisit within the next 25% of game length among departures no later than
   50% progress.

## Validation stop conditions

Every game key must agree across the manifest, game, placement, and regional
state inputs. Trial paths, hashes, seeds, and game keys must be unique. Every
game must have the board-specific natural length: 18, 24, or 48 turns and
exactly three placements per turn.

Each placement must have a unique `(game, turn, placement_number)` key and
must map to exactly one of the frozen nine regions. Unmapped placements,
unknown regions, inconsistent target-to-region assignments, or duplicate
placement keys stop the analysis. Player-by-region placement totals must
match the regional turn states, and the nine-region total must be exactly
three on every turn.

Regional activity is independently reconstructed from the frozen four-turn
definition. Any malformed sequence, count mismatch, hash mismatch, or trial
hash mismatch stops the analysis.

## Interpretation hierarchy

Interpretation follows: dormant-front prevalence, unresolved backlog,
revisit rate and lag, unresolved carryover after focus switches, then local
lead and repeated-cycle diagnostics. A longer raw revisit lag alone is not a
temporal multi-front result. Support requires agreement among normalized
prevalence/backlog, censor-aware revisit behavior, and carryover measures.
Non-monotonic and contradictory results are reported directly.

## Run

Use the pinned Issue 65 replay outputs:

```powershell
./experiments/issue-68/scripts/run-analysis.ps1
```

For a complete replay from the saved trials before analysis:

```powershell
./experiments/issue-68/scripts/run-analysis.ps1 `
  -RefreshReplay -LudiiJar C:\Users\verti\Ludii-1.3.14.jar
```

Requirements: Ludii Player 1.3.14 for `-RefreshReplay`, Java 21, PowerShell,
and Node.js 24 or later.
