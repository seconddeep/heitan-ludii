#!/usr/bin/env python3
"""Outcome-blind budget gates and post-production full scoring validation."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import tempfile

import protocol
import run_experiments


def gate_path(budget: int) -> Path:
    return protocol.validation_gate_path(budget)


def all_production_tasks_terminal(config: dict, manifest: dict) -> bool:
    tasks = protocol.tasks_from_config(config, "production")
    return all(manifest["tasks"][task.task_id]["state"] in {"completed", "failed", "corrupt"} for task in tasks)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--namespace", choices=("pilot", "production"), required=True)
    parser.add_argument("--budget", type=int, choices=(10000, 30000, 100000))
    parser.add_argument("--full-scoring", action="store_true")
    parser.add_argument("--ludii-jar", default=os.environ.get("LUDII_JAR", ""))
    args = parser.parse_args()
    if args.namespace == "production" and not args.full_scoring and args.budget is None:
        parser.error("an outcome-blind production gate requires --budget")
    if args.full_scoring and args.namespace != "production":
        parser.error("full scoring validation is only defined after production")
    jar = Path(args.ludii_jar).expanduser().resolve()
    if not jar.is_file():
        parser.error("pass --ludii-jar or set LUDII_JAR")
    config = protocol.load_config()
    tasks = protocol.tasks_from_config(config, args.namespace)
    manifest = protocol.reconcile_manifest(args.namespace, tasks, protocol.sha256(protocol.CONFIG_PATH))
    if args.full_scoring and not all_production_tasks_terminal(config, manifest):
        raise ValueError("full score/winner validation is forbidden until all production tasks are terminal")
    selected = [task for task in tasks if args.budget is None or task.iteration_limit == args.budget]
    game = protocol.REPO_ROOT / config["game"]
    failures: list[dict[str, object]] = []
    validated = 0
    for task in selected:
        row = manifest["tasks"][task.task_id]
        if row["state"] != "completed":
            continue
        artifact_problem = protocol.artifact_error(row)
        if artifact_problem:
            failures.append({"task_id": task.task_id, "failure_kind": "artifact_integrity", "error": artifact_problem})
            continue
        task_dir = (protocol.REPO_ROOT / row["artifacts"]["validation"]).parent
        try:
            with tempfile.TemporaryDirectory(prefix="heitan-112-replay-") as directory:
                result = run_experiments.validate_generated(task, task_dir, jar, game, config, full_scoring=args.full_scoring, replay_root=Path(directory))
            if result["normalized_trial_sha256"] != row["artifacts"]["trial_sha256"]:
                raise ValueError("normalized trial hash differs from manifest")
            validated += 1
        except Exception as error:
            failures.append({"task_id": task.task_id, "failure_kind": run_experiments.failure_kind(error), "error": protocol.sanitize_error(error)})
    states = dict(sorted(Counter(manifest["tasks"][task.task_id]["state"] for task in selected).items()))
    output = {
        "schema_version": 1,
        "validation_scope": "full-score-and-winner" if args.full_scoring else "operational-only-outcome-blind",
        "namespace": args.namespace,
        "budget": args.budget,
        "checked_at_utc": protocol.utc_now(),
        "selected_tasks": len(selected),
        "validated_completed_tasks": validated,
        "states": states,
        "manifest_sha256": protocol.sha256(protocol.manifest_path(args.namespace)),
        "budget_rows_sha256": protocol.budget_rows_sha256(manifest, int(args.budget)) if args.budget is not None else None,
        "checks": ["legal_replay", "natural_completeness", "artifact_hashes", "manifest_identity", "failure_visibility", "resume_integrity"] if not args.full_scoring else ["independent_corrected_score", "winner", "final_board", "runner_metrics"],
        "aggregate_outcomes_inspected": args.full_scoring,
        "failures": failures,
    }
    if args.namespace == "production" and not args.full_scoring:
        protocol.atomic_write_json(gate_path(int(args.budget)), output)
        print(json.dumps({"budget": args.budget, "validation_scope": output["validation_scope"], "selected_tasks": len(selected), "validated_completed_tasks": validated, "states": states, "failure_count": len(failures)}, sort_keys=True))
    elif args.full_scoring:
        protocol.atomic_write_json(protocol.RESULTS_ROOT / "production" / "full-scoring-validation.json", output)
        print(json.dumps({"validation_scope": output["validation_scope"], "selected_tasks": len(selected), "validated_completed_tasks": validated, "failure_count": len(failures)}, sort_keys=True))
    else:
        print(json.dumps({"namespace": args.namespace, "validation_scope": output["validation_scope"], "selected_tasks": len(selected), "validated_completed_tasks": validated, "states": states, "failure_count": len(failures)}, sort_keys=True))
    if failures:
        raise SystemExit("revalidation failures detected")


if __name__ == "__main__":
    main()
