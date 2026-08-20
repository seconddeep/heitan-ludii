# Issue 77: 7x7 piece-count sensitivity results

## Conclusion

The preregistered classification is **mixed**. At UCT 1000, 96 pieces per
player sustain more simultaneous active fronts and resolve or settle more of
them than 72 pieces, while selective abandonment falls. However, dormant
fronts and backlog also increase. The additional resources therefore improve
completion without removing overextension. The 84-piece condition is mostly
indistinguishable from 72 pieces and does not establish a clear intermediate
recovery.

This is not pure board-size saturation because 96 pieces produce measurable
changes in active-front breadth and resolution. It is not a simple
resource-limited result because backlog grows rather than contracts, and it is
not pure overextension because normalized resolution efficiency improves and
selective abandonment falls.

## Design and validation

The primary analysis compares 50 UCT 1000 games at each of 72, 84, and 96
pieces per player. The 72-piece games are reused from Issue 73; only the 84-
and 96-piece games are newly generated. Seeded Random (100 games per budget),
UCT 100 (50), and UCT 500 (50) are sensitivity series. All intervals below are
preregistered game-level 95% percentile bootstrap intervals with 2,000
replicates. Contrast directions are fixed as 84 - 72, 96 - 72, and 96 - 84.

All 750 trials replayed legally. The validation covered 126,000 placements and
42,000 turns, with exactly three placements per turn, the expected 48/56/64
turn NaturalEnd, correct per-player budgets, matching reconstructed scores and
winners, and the unchanged 113-site nine-region mapping.

The committed Issue 73 manifest contains a pre-existing provenance
inconsistency: its recorded SHA-256 differs from the committed trial for all
250 reused trials. This was discovered and documented before aggregate results
were inspected. Issue 77 preserves those source hashes and pins the current
trial bytes with an LF-normalized SHA-256. All 250 trials then replayed legally;
their 250 game summaries and all 36,000 placements match separately pinned
Issue 73 raw outputs exactly.

## Primary results

### 1. Spatial breadth

Four-turn spatial breadth does not clearly recover relative to 72 pieces.
Normalized entropy changes by -0.0032 [-0.0112, 0.0050] at 84 pieces and
+0.0054 [-0.0034, 0.0144] at 96 pieces. Region coverage changes by -0.0052
[-0.0152, 0.0052] and +0.0059 [-0.0063, 0.0183], respectively. Only the
96 - 84 auxiliary contrast is positive for entropy (+0.0086 [0.0000, 0.0166])
and coverage (+0.0110 [0.0006, 0.0217]); this is weak and does not establish
recovery beyond the 72-piece baseline.

Active-front breadth tells a different story. Mean active regions rise from
5.066 at 72 pieces to 5.166 at 84 and 5.459 at 96. The 96 - 72 difference is
+0.393 [0.226, 0.564], while 84 - 72 is inconclusive (+0.099 [-0.090,
0.287]). Opportunity-adjusted activity shows the same pattern, so the
96-piece effect is not explained only by a larger legal-move set.

### 2. Backlog and selective abandonment

The wider 96-piece active front is accompanied by more backlog, not less.
Mean backlog rises from 2.948 at 72 pieces to 3.003 at 84 and 3.233 at 96;
96 - 72 is +0.284 [0.171, 0.402]. Mean dormant active fronts similarly rise by
+0.174 [0.103, 0.251] for 96 - 72. The 84 - 72 differences are inconclusive.

Despite that accumulation, selective abandonment falls at 96 pieces. Its rate
drops from 0.209 at 72 to 0.136 at 96, a difference of -0.0728 [-0.1123,
-0.0334]. The 96 - 84 contrast is also lower (-0.0486 [-0.0934, -0.0015]).
Thus extra pieces keep more fronts in play and ultimately abandon fewer, but
they do not reduce the number waiting for attention during play.

### 3. Revisit and resolution

Observed revisit rates are already near one (0.991--0.994) and do not differ
reliably across budgets. Normalized revisit lag becomes shorter as games grow,
but the raw lag and four-turn revisit rate do not change clearly. This does not
support a claim that the added budget causes more frequent revisits.

There is stronger evidence that the longer game improves what happens after a
front is left. Later revisit of unresolved focus carryover rises by +0.087
[0.009, 0.178] for 84 - 72 and +0.077 [0.002, 0.164] for 96 - 72. More
importantly, the resolved-or-settled rate rises from 0.619 at 72 to 0.739 at
96: +0.120 [0.070, 0.169]. The 96 - 84 difference is +0.087 [0.032, 0.145].
The result is therefore better described as improved eventual resolution than
as increased revisit incidence.

### 4. Resolution efficiency beyond game length

Raw secured Objectives increase by 4.04 [3.18, 4.86] for 84 - 72 and 8.36
[7.50, 9.24] for 96 - 72. After division by total placements, the 84 - 72
difference is inconclusive (+0.0026 [-0.0027, 0.0076]), whereas 96 - 72
retains a small positive difference (+0.0060 [0.0003, 0.0113]). Secured Supply
Points per placement also improve for 84 - 72 (+0.0054 [0.0023, 0.0086]) and
96 - 72 (+0.0075 [0.0050, 0.0103]).

Accordingly, most of the raw gain is mechanical exposure to more placements,
but the 96-piece condition shows modest efficiency improvement beyond game
length. The 96 - 84 Objective-efficiency contrast remains inconclusive.

### 5. Mechanical late tail

Late Objective placements rise in raw count by 2.98 [1.52, 4.44] at 84 pieces
and 7.66 [5.86, 9.38] at 96, but their share of all placements does not rise:
-0.0088 [-0.0182, 0.0008] and -0.0066 [-0.0169, 0.0034]. No condition records
fronts classified as mechanically closed in this analysis.

At 96 pieces, a larger share of late Objective placements target regions whose
outcome was already fixed (+0.0518 [0.0118, 0.0930] versus 72). At the same
time, contribution to securing rises by +0.0712 [0.0305, 0.1131], and neither
global-outcome mutability nor global-comparison changes show a clear shift.
The late tail therefore contains more already-settled regional play, but it is
not merely dead play and does not expand as a fraction of the game.

## Sensitivity analysis

The directional structure is broadly stable across Seeded Random, UCT 100,
UCT 500, and UCT 1000. Mean active regions and mean backlog increase from 72
to 84 to 96 in every sensitivity series. Secured Objectives per placement is
also monotone in all four series, although the 84-to-96 increment is small at
UCT 500 and UCT 1000. Four-turn entropy and coverage are nearly flat in the
weaker-agent series; the UCT 1000 dip at 84 followed by recovery at 96 is not a
general monotone spatial-breadth effect.

## Interpretation

The 72-piece game is partly resource constrained: 96 pieces let play sustain
more fronts and finish or settle more of them, with a modest normalized
conversion gain. But the same condition increases unattended unresolved work.
The board has not simply saturated, and the added budget has not cleanly
eliminated fragmentation. The strongest supported reading is a mixed regime:
**96 pieces improve eventual resolution while extending the period in which
players carry a larger backlog; 84 pieces are insufficient to produce a clear
change from 72.**

Machine-readable validation and estimates are in
`experiments/issue-77/results/analysis.json` and
`experiments/issue-77/results/primary-contrast.csv`.
