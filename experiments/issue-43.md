# Issue 43: Reversal mechanisms in Heitan

## Summary

This analysis compares checkpoint reversals with preserved leads in the 100-game UCT 10,000 primary sample and reports the 100-game UCT 3,000 sample separately as sensitivity evidence. It reuses validated Issues #37, #39, and #41 records and generates no new self-play.

Across both search strengths and all four checkpoints, 321 checkpoint-game rows are reversals; 150 are in the primary sample. Results are descriptive temporal associations, not causal estimates.

## Timing and scoring layers

Global strict persistence and post-checkpoint takeover are stored separately. Reversal-aligned Turn 0 is always the post-checkpoint strict permanent takeover; preserved leads are not assigned an artificial takeover.

In the primary reversal rows, takeover and final decisive layers agree in 137 of 150 cases (91.3%). The full cross-tabulation is in `results/objective-reversal-summary.csv`.

At Turn 20, 36 leaders were reversed, 45 preserved their lead, 10 led games drew, and 9 games were tied. Permanent takeover followed after a mean 2.69 turns; 25.0% completed in one turn, so the sample contains both sudden and multi-turn reversals. Takeover was decided by Secured Objectives in 22 cases, Advantage Objectives in 11, and Objective Pieces in 3.

## Supply mechanisms

Supply degradation and reinvestment use pre-frozen four-turn baseline and lookback windows and require at least two configured indicators. The usable-support measure counts every controlled-or-secured Supply Point × adjacent live Objective pair, including separate edges to a shared Objective. See `results/supply-reversal-summary.csv` and the supporting raw cohort columns.

For primary Turn-20 reversals, 52.8% meet the pre-frozen degradation rule and 44.4% meet the reinvestment rule. A primary important-site gain or loss occurs in 38.9%. These are sequence associations, not evidence that Supply changes caused the later Objective result.

The UCT 3,000 Turn-20 sensitivity cohort has 42 reversals; degradation and reinvestment flags occur in 59.5% and 64.3%, respectively. Differences between search strengths are reported descriptively rather than pooled.

## Outputs and integrity

- 200 complete games and 4800 game-turns were reused.
- All configured checkpoint cells reconcile with Issue #41.
- Raw P1/P2, checkpoint-leader-relative, and eventual-winner-relative values are retained separately.
- Source paths and SHA-256 hashes are recorded.

See `experiments/issue-43/README.md` for frozen definitions and reproduction commands.
