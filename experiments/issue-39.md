# Issue 39: Supply Point site value

## Summary

This analysis reconstructs every Supply Point lifecycle in the 100 primary
UCT 10,000 games and the 100 UCT 3,000 comparison games. No new self-play was
generated. Value is deliberately reported as separate placement, reversible
unsecured Control, permanent Secured infrastructure, combined ownership/control,
actual Supply use, coverage, contest, and outcome dimensions.

The primary data's top sites by placement are S31 (1.790), S13 (1.720), S23 (1.720), S21 (1.715), S33 (1.575).
The top sites by actual Objective placements supplied are
S23 (2.000), S21 (1.860), S12 (1.850), S13 (1.765), S22 (1.765).
Placement and use have Pearson correlation
0.992 and Spearman rank correlation
0.910 across the 25 sites.

## S22 versus the other eight interior points

| Dimension | S22 | Other interior mean | Difference | 25-site rank |
|---|---:|---:|---:|---:|
| Pieces placed per player-game | 1.545 | 1.627 | -0.083 | 6 |
| unsecured Control turn share | 0.171 | 0.149 | +0.022 | 1 |
| Secured turn share | 0.120 | 0.104 | +0.017 | 2 |
| combined ownership/control turn share | 0.291 | 0.253 | +0.039 | 1 |
| Objective placements supplied per player-game | 1.765 | 1.771 | -0.006 | 5 |
| normalized Objective coverage | 0.258 | 0.253 | +0.005 | 4 |

S22 is therefore not the single leader in every dimension: it ranks
6th in placement and
5th in
actual Supply use, while its reversible-Control, Secured, and combined shares
are independently reported above. S23, S21, S12, and S13 all supplied more
Objective placements per player-game in this sample. The table must not be
interpreted as a single composite site-value score.

## Competition and post-Securing utility

Among the nine sites with the greatest contested-turn share, the five with the
lowest Secured frequency are: S11 (contest 0.515, Secured frequency 0.165), S32 (contest 0.532, Secured frequency 0.175), S12 (contest 0.511, Secured frequency 0.175), S33 (contest 0.525, Secured frequency 0.185), S22 (contest 0.571, Secured frequency 0.190). This is a two-stage descriptive
filter, not a composite value score.

Requiring at least ten Secured player-sites, the highest mean actual usage
after Securing is: S23 (4.13 later uses; 46 Secured player-sites), S21 (4.12 later uses; 42 Secured player-sites), S32 (4.11 later uses; 35 Secured player-sites), S12 (4.06 later uses; 35 Secured player-sites), S11 (4.03 later uses; 33 Secured player-sites). These are the points that most clearly behave
as selectively fixed infrastructure followed by substantial use.

## Winner and loser association

The following primary-sample values are per player-game. Control columns are
the expected number of sites in each state on a randomly selected game turn
(the sum of the 25 site shares).

| Result | Supply Pieces placed | Unsecured Control | Secured | Combined | Objective placements supplied |
|---|---:|---:|---:|---:|---:|
| winner | 18.06 | 1.691 | 1.033 | 2.725 | 17.94 |
| loser | 18.90 | 1.859 | 0.898 | 2.757 | 17.10 |
| draw | 18.10 | 1.850 | 0.913 | 2.763 | 17.90 |

Winner/loser differences are associations within these self-play samples and
are not evidence that a site state causes the result. Site-specific values are
retained in `results/winner-loser-site-comparison.csv`.

## Phase shift

| Phase | Supply Pieces placed | Unsecured-Control turns | Secured turns | Objective placements supplied | Most-used site |
|---|---:|---:|---:|---:|---|
| early | 1629 | 2839 | 290 | 771 | S12 (93) |
| midgame | 909 | 2617 | 1700 | 1491 | S22 (194) |
| late | 1150 | 3101 | 2620 | 1250 | S13 (147) |

The phase table keeps reversible Control and permanent Secured occupancy
separate. All site-by-phase values are available in
`results/site-phase-summary.csv`.

## Search strength and concentration

| Search | Unsecured Control | Secured | Supply uses/player-game | Top-5 usage share | Usage HHI |
|---|---:|---:|---:|---:|---:|
| UCT 3,000 | 3.097 | 0.445 | 18.95 | 46.5% | 0.0727 |
| UCT 10,000 | 1.783 | 0.960 | 17.56 | 52.6% | 0.0926 |

For actual Supply usage in the primary data, the top three sites account for
32.5%. Search-strength differences are
between two independent 100-game samples, not paired causal estimates. Every
site-level delta is retained in `results/search-strength-site-comparison.csv`.

## Definitions

Under the game rules, Secured belongs to the owner's Control. Analytically,
`unsecured_controlled_turns` and `secured_turns` are disjoint, and
`controlled_or_secured_turns` is their sum. All three measures and shares are
retained in lifecycle, phase, site, outcome, and strength-comparison outputs.
Objective coverage is normalized by each site's number of adjacent Objectives.
Repeated legal Securing opportunities and ever-securable player-sites use
separate denominators.

## Integrity

- 200 source trial paths and SHA-256 hashes were verified.
- 200 legally completed Issue #37 replays were reused.
- 240000 player-site-turn records and 10000 player-site lifecycle records were generated.
- Control separation identities were checked for all lifecycle and phase rows.
- 7302 actual Objective Supply-source uses were checked for adjacency, ownership/control, and per-turn uniqueness.

See `experiments/issue-39/README.md` for frozen definitions, output inventory,
and reproduction commands.
