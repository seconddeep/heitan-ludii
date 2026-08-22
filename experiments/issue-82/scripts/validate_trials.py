#!/usr/bin/env python3
"""Re-run legal replay and invariant validation for completed Issue #82 tasks."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import protocol
import run_experiments


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--namespace", choices=("pilot", "production"), required=True)
    parser.add_argument("--budget", type=int, choices=(10000, 30000, 100000, 300000))
    parser.add_argument("--ludii-jar", default=os.environ.get("LUDII_JAR", ""))
    args = parser.parse_args()
    config = protocol.load_config()
    tasks = protocol.tasks_from_config(config, args.namespace)
    manifest_path = protocol.manifest_path(args.namespace)
    if not manifest_path.is_file():
        raise ValueError("manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    jar = Path(args.ludii_jar).expanduser().resolve()
    if not jar.is_file():
        parser.error("pass --ludii-jar or set LUDII_JAR to an existing file")
    game = protocol.REPO_ROOT / config["game"]
    count = 0
    for task in tasks:
        if args.budget is not None and task.iteration_limit != args.budget:
            continue
        row = manifest["tasks"][task.task_id]
        if row["state"] != "completed":
            continue
        directory = (protocol.REPO_ROOT / row["artifacts"]["validation"]).parent
        validation = run_experiments.validate_generated(task, directory, jar, game)
        if validation["trial_sha256"] != row["artifacts"]["trial_sha256"]:
            raise ValueError(f"trial hash changed: {task.task_id}")
        count += 1
    print(f"revalidated {count} completed {args.namespace} game(s)")


if __name__ == "__main__":
    main()
