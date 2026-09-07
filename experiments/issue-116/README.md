# Issue 116: larger-board UCT execution benchmark

This directory implements GitHub Issue #116. It measures execution cost for
Board/6x6, Board/7x7, and Board/8x8 at UCT 1k, 3k, 10k, and 30k. It does not
measure game balance, strategy, search convergence, or game quality, and it
does not modify the game definition or rules.

The repository-wide [safety and experiment integrity principles](../../docs/repository-principles.md)
apply. Runtime artifacts use repository-relative paths and an opaque runner ID.
Usernames, hostnames, serial numbers, hardware UUIDs, absolute local paths,
secrets, and game-outcome aggregates are forbidden in public artifacts.

## Two-stage freeze

`config.json` preregisters, before the pilot, the complete board-by-UCT matrix,
three measured games per condition, deterministic task identities and seeds,
single-worker primary execution, measurement fields, classification categories,
and failed-seed non-replacement. The pilot is excluded and exposes only
operational timing, memory, process, artifact, and replay-validation fields.

After that outcome-blind pilot, `freeze_protocol.py` fixes the production
`-Xmx`, hard timeout, soft runtime threshold, machine-memory thresholds, and GC
logging details. Measured tasks cannot start before this second lock is
committed at a clean HEAD.

## Source-derived board gate

The board values in `config.json` are expected values only. Production is
allowed only when each Board option can be isolated exactly once from the
source-locked `games/Heitan.lud`, its four positional values can be extracted
unambiguously, and all source-derived values agree with the expected values.
Runner constants, this README, and config declarations are never sufficient
evidence on their own. A mismatch is a prerequisite defect and blocks the
benchmark.

## Memory evidence

Peak RSS and physical RAM are machine-safety evidence. Their ratio is used for
the soft and hard machine-memory gates. `-Xmx` is a separate configured Java
heap ceiling. GC logs are separate diagnostic evidence for heap pressure and
are not treated as a substitute for RSS. RSS and `-Xmx` are never divided by
each other to create a feasibility threshold.

Live process-group RSS sampling is used when the execution environment permits
process-table access. If it does not, the limitation is recorded and the
platform `time` utility supplies post-process peak RSS; OOM/fatal-JVM handling,
the fixed heap ceiling, and board-local stopping remain active.

## Mechanical classification

- **feasible**: 3/3 validated completions and all soft limits satisfied;
- **borderline**: 3/3 validated completions, but at least one soft limit exceeded;
- **infeasible in current environment**: fewer than 3/3 validated completions
  or any hard safety condition;
- **not attempted**: a lower-depth stopping gate prevented execution.

No manual override is permitted. An infeasible condition stops all deeper
conditions for that board. Failed measured seeds are not replaced.

## Intended execution

```sh
python3 -m unittest discover -s experiments/issue-116/scripts -p 'test_*.py'
LUDII_JAR=/path/to/Ludii-1.3.14.jar \
  python3 experiments/issue-116/scripts/run_benchmark.py pilot
LUDII_JAR=/path/to/Ludii-1.3.14.jar \
  python3 experiments/issue-116/scripts/freeze_protocol.py [frozen limits]
```

Commit the post-pilot lock, then run each measured condition in board-local,
low-to-high UCT order inside `tmux` under `caffeinate -i`. `summarize.py`
creates only timing, memory, completion, failure, scaling, and recommended
ceiling outputs. Trial outcomes may exist inside Ludii trial evidence but are
never read or reported by the benchmark scripts.
