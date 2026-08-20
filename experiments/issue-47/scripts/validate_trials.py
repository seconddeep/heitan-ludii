#!/usr/bin/env python3
"""Revalidate completed Issue #47 trials and detect post-completion corruption."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import protocol
import run_experiments
import run_analysis


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--namespace", choices=("pilot", "production"), required=True)
    parser.add_argument("--budget", type=int, choices=(30000, 100000))
    parser.add_argument("--ludii-jar", default=os.environ.get("LUDII_JAR", ""))
    parser.add_argument(
        "--finalized-sample", action="store_true",
        help="accept only the explicitly recorded terminal exclusions while validating every completed game",
    )
    args = parser.parse_args()
    jar = Path(args.ludii_jar).expanduser().resolve()
    if not jar.is_file():
        parser.error("pass --ludii-jar or set LUDII_JAR to an existing file")
    config = protocol.load_config()
    tasks = protocol.tasks_from_config(config, args.namespace)
    config_hash = protocol.sha256(protocol.CONFIG_PATH)
    manifest = protocol.reconcile_manifest(args.namespace, tasks, config_hash)
    finalized_exclusions: set[str] = set()
    if args.finalized_sample:
        if args.namespace != "production":
            parser.error("--finalized-sample is valid only for production")
        finalization = run_analysis.load_finalization(config, manifest)
        finalized_exclusions = {row["task_id"] for row in finalization["excluded_tasks"]}
    game = protocol.REPO_ROOT / config["game"]
    failures = 0
    for task in tasks:
        if args.budget is not None and task.iteration_limit != args.budget:
            continue
        row = manifest["tasks"][task.task_id]
        if row["state"] != "completed":
            if task.task_id in finalized_exclusions:
                print(f"{task.task_id}: finalized exclusion ({row['state']})")
                continue
            failures += 1
            print(f"{task.task_id}: not completed ({row['state']})")
            continue
        final_dir = protocol.RESULTS_ROOT / args.namespace / "tasks" / task.task_id
        try:
            validation = run_experiments.validate_generated(task, final_dir, jar, game)
            if validation["trial_sha256"] != row["artifacts"]["trial_sha256"]:
                raise ValueError("trial hash differs from completed manifest")
            print(f"{task.task_id}: valid")
        except Exception as error:
            failures += 1
            protocol.update_task(args.namespace, tasks, config_hash, task.task_id, "corrupt", error=str(error))
            print(f"{task.task_id}: corrupt: {error}")
    if failures:
        raise SystemExit(f"{failures} task(s) are incomplete or corrupt")


if __name__ == "__main__":
    main()
