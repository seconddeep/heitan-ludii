#!/usr/bin/env python3
"""Freeze the terminal Issue #108 production manifest and artifact hashes."""

from __future__ import annotations

from collections import Counter
import json

import protocol


def main() -> None:
    config=protocol.load_config();tasks=protocol.tasks_from_config(config,"production")
    if protocol.PRODUCTION_BLOCK_PATH.exists():raise ValueError("production remains globally blocked")
    if protocol.FINALIZATION_PATH.exists():raise ValueError("production is already finalized")
    manifest=protocol.reconcile_manifest("production",tasks,protocol.sha256(protocol.CONFIG_PATH))
    transient=[row["task_id"] for row in manifest["tasks"].values() if row["state"] in protocol.TRANSIENT_STATES]
    if transient:raise ValueError(f"transient tasks remain: {transient[:3]}")
    retryable=[row["task_id"] for row in manifest["tasks"].values() if row["state"] in {"pending","interrupted"} or (row["state"] in {"failed","corrupt"} and int(row["attempts"])<int(config["operational_parameters"]["max_attempts"]))]
    if retryable:raise ValueError(f"tasks still have permitted attempts: {retryable[:3]}")
    counts={};completed={};artifacts=[]
    for budget in config["primary_budgets"]:
        rows=[manifest["tasks"][task.task_id] for task in tasks if task.iteration_limit==budget]
        counts[str(budget)]=dict(Counter(row["state"] for row in rows));completed[str(budget)]=sum(row["state"]=="completed" for row in rows)
        for row in rows:
            if row["state"]=="completed":artifacts.append({"task_id":row["task_id"],**row["artifacts"]})
    value={"schema_version":1,"finalized_at_utc":protocol.utc_now(),"manifest":protocol.manifest_path("production").relative_to(protocol.REPO_ROOT).as_posix(),"manifest_sha256":protocol.sha256(protocol.manifest_path("production")),"planned_games_by_budget":{str(value):100 for value in config["primary_budgets"]},"completed_games_by_budget":completed,"states_by_budget":counts,"artifacts":artifacts,"missing_not_at_random_limitation":any(value<100 for value in completed.values())}
    protocol.atomic_write_json(protocol.FINALIZATION_PATH,value);print(json.dumps({"completed_games_by_budget":completed},sort_keys=True))


if __name__=="__main__":main()
