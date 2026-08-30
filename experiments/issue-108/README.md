# Issue 108: corrected-rule 3x3 deep UCT

This directory preregisters and implements GitHub Issue #108. It regenerates
three independent, fixed 100-task self-play samples under the corrected
Objective-piece tiebreak. It does not modify the game, rules, board, or prior
experiment artifacts.

The repository-wide [safety and experiment integrity principles](../../docs/repository-principles.md)
apply to this work. This README records the issue-specific protocol, evidence,
provenance, and resume requirements used to apply those principles.

## Frozen scientific scope

The primary budgets are UCT 10,000, 30,000, and 100,000. Each budget has 100
task identities and seeds fixed before production; a failed task is never
replaced by another seed. The primary outcome is unconditional P1 win rate.
Draws stay in the denominator.

The primary 100k-drop contrast is corrected 100k minus corrected 30k. Corrected
100k minus corrected 10k is secondary. Point estimates and 95% game-bootstrap
intervals are primary; labels are secondary. No `material change` label is
used because no defensible numerical threshold was preregistered.

The empirical depth classification reuses the Issue #47/#82 thresholds in
`config.json`, in listed precedence order, without manual override. It is not a
claim of convergence or optimal play.

The auxiliary drop label is also mechanical and exclusive. After the
insufficient-data gate, a corrected-versus-original 100k-minus-30k
difference-in-differences interval wholly above zero is `weakens`; otherwise a
corrected primary-contrast interval wholly below zero is `persists`, one wholly
at or above zero is `disappears`, and all remaining cases are `unresolved`.

## Corrected scoring and validation gate

The score is `280 * Secured Objectives + 28 * Advantage Objectives + own
Pieces on own-Advantage Objectives`. The runner and replay validator reconstruct
that score independently. A legal completed game's score or winner mismatch is
a global production-blocking failure: the active budget stops and no later
budget may start until the cause is resolved.

Every included game must replay legally and end naturally after 54 placements
and 18 Heitan turns. Every turn has exactly three placements and each player
places exactly 27 Pieces.

## Structural definitions

Central Supply means `S11`, `S12`, `S21`, and `S22`. State-based central
metrics are observed only after complete Heitan turns. The early window is
global turns 1 through 6; P1's early turns are 1, 3, and 5. Occupation means at
least one P1 Piece anywhere in the group. Contest means that at least one
central Supply point contains Pieces from both players. A game with no P1
central placement has a null first-commitment turn.

Full-lexicographic leaders use corrected scoring at turn end. The first
persistent lead is the first turn after which the eventual non-draw winner is
the leader at every remaining turn; an intervening tie breaks persistence.
Draws have no persistent lead. The 75% and 90% late-reversal checkpoints are
turns 14 and 17. Only games with a non-tied checkpoint leader and a non-draw
winner enter the late-reversal denominator.

## Trial portability

Raw trials are immutable generation evidence and are hashed before a derived
normalized UTF-8/LF trial is created. Its `game=` field is
`games/Heitan.lud`, relative to the repository root. Both versions must replay
to identical moves, terminal board, score, and winner. Raw trials are not
published; their hashes are generation-time evidence only, so third-party
revalidation depends on the published normalized trials.

## Execution stages

1. Run unit tests and the excluded operational pilot.
2. Freeze `config.json`, selected #82/#105 inputs, executable source hashes,
   game commit/hash, Ludii JAR hash, and environment into the lock files.
3. Commit the locked implementation with a clean tracked worktree.
4. Run 10k, then 30k, then 100k in separate persistent `tmux` sessions under
   `caffeinate -i`, with a non-identifying `HEITAN108_RUNNER_ID` supplied.
5. Finalize, analyze, deterministically regenerate outputs, and run the public
   safety audit.

At every production start and resume, the gate requires the locked HEAD,
unchanged tracked files, matching locked source hashes, and no unexpected
untracked files outside `experiments/issue-108/results/`. Runtime results and
lock files use repository-relative paths and opaque runner IDs rather than a
raw hostname.

The concrete commands will be recorded here by the locking step after the
pilot establishes the local worker, heap, and timeout settings.

The initial sandboxed pilot could not query the process table, so its manifest
records peak RSS as unavailable rather than inventing a value. The production
runner additionally uses the platform `time` utility when available to capture
child-process peak RSS without requiring process-table access; this limitation
is retained explicitly in the protocol evidence.
