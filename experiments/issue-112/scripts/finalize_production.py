#!/usr/bin/env python3
"""Freeze the terminal Issue #112 production manifest and artifact hashes."""

from __future__ import annotations

from collections import Counter
import json

import protocol


def main() -> None:
    config=protocol.load_config();tasks=protocol.tasks_from_config(config,"production")
    if protocol.PRODUCTION_BLOCK_PATH.exists():raise ValueError("production remains globally blocked")
    if protocol.FINALIZATION_PATH.exists():raise ValueError("production is already finalized")
    # Validation has already reconciled the terminal manifest.  Loading it here
    # must be read-only: reconcile_manifest() refreshes the manifest's root
    # updated_at_utc even when no task changes, which invalidates the hash
    # recorded by the immediately preceding full-scoring validation.
    manifest=protocol.load_json(protocol.manifest_path("production"))
    transient=[row["task_id"] for row in manifest["tasks"].values() if row["state"] in protocol.TRANSIENT_STATES]
    if transient:raise ValueError(f"transient tasks remain: {transient[:3]}")
    retryable=[row["task_id"] for row in manifest["tasks"].values() if row["state"] in {"pending","interrupted"} or (row["state"] in {"failed","corrupt"} and int(row["attempts"])<int(config["operational_parameters"]["max_attempts"]))]
    if retryable:raise ValueError(f"tasks still have permitted attempts: {retryable[:3]}")
    for budget in config["primary_budgets"]:
        gate_path=protocol.validation_gate_path(budget)
        if not gate_path.is_file():raise ValueError(f"budget {budget} lacks its validation-only gate")
        gate=protocol.load_json(gate_path)
        if gate.get("validation_scope")!="operational-only-outcome-blind" or gate.get("aggregate_outcomes_inspected") is not False or gate.get("failures"):
            raise ValueError(f"budget {budget} validation-only gate is invalid")
        if gate.get("budget_rows_sha256")!=protocol.budget_rows_sha256(manifest,budget):raise ValueError(f"budget {budget} changed after validation-only gate")
    if not protocol.FULL_SCORING_VALIDATION_PATH.is_file():raise ValueError("post-production full score/winner validation is missing")
    scoring=protocol.load_json(protocol.FULL_SCORING_VALIDATION_PATH)
    if scoring.get("validation_scope")!="full-score-and-winner" or scoring.get("aggregate_outcomes_inspected") is not True or scoring.get("failures"):
        raise ValueError("post-production full score/winner validation is invalid")
    if scoring.get("manifest_sha256")!=protocol.sha256(protocol.manifest_path("production")):raise ValueError("manifest changed after full score/winner validation")
    counts={};completed={};artifacts=[]
    for budget in config["primary_budgets"]:
        rows=[manifest["tasks"][task.task_id] for task in tasks if task.iteration_limit==budget]
        counts[str(budget)]=dict(Counter(row["state"] for row in rows));completed[str(budget)]=sum(row["state"]=="completed" for row in rows)
        for row in rows:
            if row["state"]=="completed":artifacts.append({"task_id":row["task_id"],**row["artifacts"]})
    value={"schema_version":1,"finalized_at_utc":protocol.utc_now(),"manifest":protocol.manifest_path("production").relative_to(protocol.REPO_ROOT).as_posix(),"manifest_sha256":protocol.sha256(protocol.manifest_path("production")),"validation_only_gates":{str(budget):protocol.sha256(protocol.validation_gate_path(budget)) for budget in config["primary_budgets"]},"full_scoring_validation":protocol.FULL_SCORING_VALIDATION_PATH.relative_to(protocol.REPO_ROOT).as_posix(),"full_scoring_validation_sha256":protocol.sha256(protocol.FULL_SCORING_VALIDATION_PATH),"planned_games_by_budget":{str(value):100 for value in config["primary_budgets"]},"completed_games_by_budget":completed,"states_by_budget":counts,"artifacts":artifacts,"missing_not_at_random_limitation":any(value<100 for value in completed.values())}
    protocol.atomic_write_json(protocol.FINALIZATION_PATH,value);print(json.dumps({"completed_games_by_budget":completed},sort_keys=True))


if __name__=="__main__":main()
