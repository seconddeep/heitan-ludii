# Issue 47 deeper-UCT strategic convergence

This directory implements the reproducible workflow for GitHub Issue #47.
It generates new complete-game UCT self-play at 30,000 and 100,000 iterations
per placement and compares it with the existing 10,000-iteration baseline.
It does not change Heitan, either rule specification, or game mechanics.

## Pilot/freeze boundary

The pilot is excluded from every production aggregate. It may be used only to
measure runtime and operational stability. After the pilot, only the 100,000
target game count, worker count, JVM heap, timeout/retry policy, and scheduling may be
changed before the protocol is locked.

The pilot must not change the 30,000/100,000 budgets, deterministic seed or
game-index rules, frozen Issue #37/#39/#41/#43/#44 definitions, important
Supply sites, Issue #43 thresholds, Issue #44 features/L2/model policy,
convergence metrics or label rules, schemas, or interpretation categories.

The required order is:

```text
excluded pilot -> inspect operations -> finalize permitted settings
-> freeze protocol -> run 30k -> validate 30k -> run 100k
-> validate 100k -> analyze
```

The 30,000 sample is independently frozen at 100 production games. The
100,000 count is finalized after the pilot. A reduction is recorded in the
locked config and reports, with 100,000 uncertainty stated separately.

## Task identity, manifest, and atomic completion

A task identity is the frozen experiment version, namespace, search budget,
one-based game index, and deterministic seed. Retries preserve this identity.
Pilot and production namespaces cannot collide.

Manifest states are `pending`, `running`, `generated`, `validating`,
`completed`, `failed`, and `corrupt`. Resume skips only `completed`. A task is
completed only after its trial parses, legally replays, ends by `NaturalEnd`,
contains exactly 72 placements and 24 turns with 36 placements per player,
uses valid adjacent Controlled/Secured Supply sources without per-turn reuse,
reconstructs all 41 sites and the lexicographic winner, and records SHA-256.

Each game is generated in a temporary task directory. After validation and
hashing, the directory is atomically renamed to its final path and the
manifest is atomically marked completed. Invalid artifacts are quarantined;
failed/corrupt tasks can be retried with the same identity. Re-running a
production command never deletes valid completed games.

## Commands

All commands run from the repository root. Set the Ludii path once:

```sh
export LUDII_JAR=/path/to/Ludii-1.3.14.jar
```

Run tests, then the excluded pilot:

```sh
python3 -m unittest discover -s experiments/issue-47/scripts -p 'test_*.py'
python3 experiments/issue-47/scripts/run_experiments.py pilot --ludii-jar "$LUDII_JAR"
```

Inspect pilot/runtime and task status:

```sh
python3 experiments/issue-47/scripts/status.py --namespace pilot
python3 experiments/issue-47/scripts/status.py --namespace production
```

After editing only permitted post-pilot fields, freeze the protocol:

```sh
python3 experiments/issue-47/scripts/freeze_protocol.py --ludii-jar "$LUDII_JAR" \
  --games-100k 100 --workers-30k 2 --workers-100k 2
```

If `--games-100k` is less than 100, also pass a factual
`--reduction-reason`. The freeze command refuses to run until every pilot task
is validated and completed.

Start or resume production in the required order:

```sh
python3 experiments/issue-47/scripts/run_experiments.py production \
  --budget 30000 --ludii-jar "$LUDII_JAR"
python3 experiments/issue-47/scripts/validate_trials.py --namespace production \
  --budget 30000 --ludii-jar "$LUDII_JAR"
python3 experiments/issue-47/scripts/run_experiments.py production \
  --budget 100000 --ludii-jar "$LUDII_JAR"
python3 experiments/issue-47/scripts/validate_trials.py --namespace production \
  --budget 100000 --ludii-jar "$LUDII_JAR"
```

Running either production command again resumes the same deterministic task
set. Production refuses to start without a matching protocol lock.

Run downstream analysis and deterministic regeneration:

```sh
python3 experiments/issue-47/scripts/run_analysis.py --ludii-jar "$LUDII_JAR"
python3 experiments/issue-47/scripts/run_analysis.py --ludii-jar "$LUDII_JAR" \
  --verify-deterministic
```

For execution that survives VS Code Remote-SSH disconnection:

```sh
tmux new-session -d -s heitan-47 \
  "cd '$PWD' && caffeinate -i python3 experiments/issue-47/scripts/run_experiments.py production --budget 30000 --ludii-jar '$LUDII_JAR'"
tmux attach -t heitan-47
```

Use a new named session for 100,000 after 30,000 validation succeeds.

## Finalized 100k sample

The locked production plan targeted 100 UCT-100k games. Production was
terminated with 97 validated games after games 61, 78, and 93 each failed two
attempts during memory-intensive MCTS search. These identities were not
replaced, and no diagnostic output is admitted to production. The original
100-task manifest and locked target remain intact; the terminal decision and
the exact three exclusions are recorded separately in
`results/production/finalization.json`.

An excluded 10GB diagnostic for game 61 failed after approximately 57 minutes.
Full GC retained about 10,234 MiB, indicating that the live MCTS search tree,
not reclaimable temporary objects, filled the heap. A roughly 15GB heap dump
was captured. This analysis does not change search-tree retention, raise the
production heap, move the failed games to a larger-memory host, or substitute
new seeds.

Revalidate the finalized sample and generate the final 97-game 100k analysis:

```sh
python3 experiments/issue-47/scripts/validate_trials.py --namespace production \
  --budget 100000 --finalized-sample --ludii-jar "$LUDII_JAR"
python3 experiments/issue-47/scripts/run_analysis.py --ludii-jar "$LUDII_JAR" \
  --verify-deterministic
```

Reports must call this a 97-game UCT-100k result, not a completed 100-game
sample. The missing games may be non-random because memory-intensive search
trajectories are more likely to fail.

## Frozen analytical policy

Issue #47 reuses the exact definitions and thresholds in Issues #37, #39,
#41, #43, and #44. Path/schema adapters must be behavior-preserving. The
primary important-site set remains S23, S21, S12, S13, and S22. Production
data is an evaluation sample and must not retune old definitions or models.

The five convergence labels and their precedence rules are frozen in
`config.json` before production. Manual narrative overrides are forbidden;
every classification retains its underlying numeric evidence. These are
descriptive robustness labels, never proof of mathematical convergence.
