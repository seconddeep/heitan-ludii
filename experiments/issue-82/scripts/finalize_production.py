#!/usr/bin/env python3
"""Record the terminal Issue #82 production sample without replacement seeds."""

from __future__ import annotations

from collections import Counter
import json

import protocol


def main() -> None:
    if protocol.FINALIZATION_PATH.exists():
        raise ValueError("production is already finalized")
    config = protocol.load_config()
    if config["protocol_status"] != "locked" or not protocol.LOCK_PATH.is_file():
        raise ValueError("protocol must be locked before finalization")
    tasks = protocol.tasks_from_config(config, "production")
    manifest_path = protocol.manifest_path("production")
    if not manifest_path.is_file():
        raise ValueError("production manifest is missing")
    manifest = protocol.reconcile_manifest("production", tasks, protocol.sha256(protocol.CONFIG_PATH))
    max_attempts = int(config["operational_parameters"]["max_attempts"])
    completed: Counter[int] = Counter()
    failed: list[dict] = []
    for task in tasks:
        row = manifest["tasks"][task.task_id]
        if row["state"] == "completed":
            completed[task.iteration_limit] += 1
            continue
        if row["state"] in protocol.TRANSIENT_STATES or row["state"] == "pending" or int(row["attempts"]) < max_attempts:
            raise ValueError(f"task is not terminal and must be resumed: {task.task_id} ({row['state']}, attempts={row['attempts']})")
        failed.append({
            "task_id": task.task_id, "experiment_id": task.experiment_id,
            "iteration_limit": task.iteration_limit, "game_index": task.game_index,
            "seed": task.seed, "state": row["state"], "attempts": row["attempts"],
            "failure_kind": row.get("failure_kind"), "error": row.get("error"),
        })
    value = {
        "schema_version": 1, "finalized_at_utc": protocol.utc_now(),
        "protocol_lock_sha256": protocol.sha256(protocol.LOCK_PATH),
        "manifest": manifest_path.relative_to(protocol.REPO_ROOT).as_posix(),
        "manifest_sha256": protocol.sha256(manifest_path),
        "planned_games_by_budget": dict(Counter(task.iteration_limit for task in tasks)),
        "completed_games_by_budget": dict(completed), "failed_tasks": failed,
        "replacement_seeds_used": False, "additional_production_execution_forbidden": True,
        "missing_may_be_non_random": bool(failed),
    }
    protocol.atomic_write_json(protocol.FINALIZATION_PATH, value)
    print(json.dumps(value, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
