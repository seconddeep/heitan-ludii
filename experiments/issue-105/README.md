# Issue 105: corrected Objective-piece tiebreak impact audit

This directory performs a read-only audit of existing validated Heitan games.
It does not modify the game, rules, source trials, or existing artifacts, and it
does not generate self-play.

The previous third tiebreak counts all of a player's pieces on all Objectives.
The corrected tiebreak counts only the player's own pieces on Objectives where
that player has Advantage. Pieces on own-Secured, opponent-Secured,
opponent-Advantage, and neutral Objectives are reported separately.

Own-Secured pieces are not dead pieces. When the third tiebreak is reached,
Secured Objective counts are tied and every own-Secured Objective contributes
exactly three pieces. Both players therefore contribute the same
`3 × Secured Objective count`, which cannot affect the third-tiebreak margin.

## Reproduce

Run from the repository root with Python 3.9 or later:

```sh
python3 experiments/issue-105/scripts/freeze_inputs.py
python3 -m unittest discover -s experiments/issue-105/scripts -p 'test_*.py'
python3 experiments/issue-105/scripts/run_analysis.py --verify-deterministic
```

`freeze_inputs.py` refuses to overwrite an existing source or protocol lock.
Ordinary reruns verify the locks and execute only the tests and analysis.

The minimum audit gate requires the previous winner to be reconstructed for all
597 games frozen by Issue #83. Any game that cannot reproduce its recorded
winner is marked unresolved; corrected comparisons are not accepted unless the
gate reaches 597/597.

After that gate passes, the same audit is extended to 1,940 non-duplicate
retained completed games from Issues #11, #30, #32 (3k only; the 10k set is
already in the minimum sample), #56, #58, #60, #62, #73, and #77. The combined
audit therefore contains 2,537 games. Results remain separated by source issue,
experiment ID, board, and search budget or AI condition.
