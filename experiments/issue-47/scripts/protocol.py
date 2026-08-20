#!/usr/bin/env python3
"""Frozen task identity and atomic manifest helpers for Issue #47."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, asdict
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Iterator


SCRIPT = Path(__file__).resolve()
ISSUE_ROOT = SCRIPT.parent.parent
REPO_ROOT = ISSUE_ROOT.parent.parent
CONFIG_PATH = ISSUE_ROOT / "config.json"
RESULTS_ROOT = ISSUE_ROOT / "results"
VALID_STATES = {"pending", "running", "generated", "validating", "completed", "failed", "corrupt"}


@dataclass(frozen=True)
class Task:
    task_id: str
    experiment_version: str
    namespace: str
    experiment_id: str
    iteration_limit: int
    game_index: int
    seed: int


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_config(path: Path = CONFIG_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def tasks_from_config(config: dict, namespace: str, budget: int | None = None) -> list[Task]:
    version = str(config["experiment_version"])
    tasks: list[Task] = []
    if namespace == "pilot":
        section = config["pilot"]
        base_seed = int(section["base_seed"])
        specs = section["tasks"]
        for spec in specs:
            iterations = int(spec["iteration_limit"])
            if budget is not None and iterations != budget:
                continue
            for zero_index in range(int(spec["games"])):
                game_index = zero_index + 1
                seed = base_seed + iterations + zero_index
                task_id = f"{version}-pilot-uct-{iterations:06d}-g{game_index:04d}"
                tasks.append(Task(task_id, version, namespace, spec["id"], iterations, game_index, seed))
    elif namespace == "production":
        section = config["production"]
        base_seed = int(section["base_seed"])
        for spec in section["tasks"]:
            iterations = int(spec["iteration_limit"])
            if budget is not None and iterations != budget:
                continue
            if spec["target_games"] is None:
                raise ValueError(f"production count is not frozen for UCT {iterations}")
            for zero_index in range(int(spec["target_games"])):
                game_index = zero_index + 1
                seed = base_seed + int(spec["budget_seed_offset"]) + zero_index
                task_id = f"{version}-production-uct-{iterations:06d}-g{game_index:04d}"
                tasks.append(Task(task_id, version, namespace, spec["id"], iterations, game_index, seed))
    else:
        raise ValueError(f"unknown namespace: {namespace}")
    validate_unique_tasks(tasks)
    return tasks


def validate_unique_tasks(tasks: list[Task]) -> None:
    fields = {
        "task ID": [task.task_id for task in tasks],
        "identity": [(task.namespace, task.iteration_limit, task.game_index) for task in tasks],
        "seed identity": [(task.namespace, task.seed) for task in tasks],
    }
    for name, values in fields.items():
        if len(values) != len(set(values)):
            raise ValueError(f"duplicate {name}")


def validate_all_namespaces(config: dict) -> None:
    pilot = tasks_from_config(config, "pilot")
    production_specs = config["production"]["tasks"]
    if any(spec["target_games"] is None for spec in production_specs):
        production = []
        for spec in production_specs:
            if spec["target_games"] is not None:
                production.extend(tasks_from_config(config, "production", int(spec["iteration_limit"])))
    else:
        production = tasks_from_config(config, "production")
    validate_unique_tasks(pilot + production)
    if {task.task_id for task in pilot} & {task.task_id for task in production}:
        raise ValueError("pilot and production task IDs collide")


def manifest_path(namespace: str) -> Path:
    return RESULTS_ROOT / namespace / "manifest.json"


def empty_manifest(namespace: str, tasks: list[Task], config_sha256: str) -> dict:
    now = utc_now()
    return {
        "schema_version": 1,
        "namespace": namespace,
        "config_sha256_at_creation": config_sha256,
        "created_at_utc": now,
        "updated_at_utc": now,
        "tasks": {
            task.task_id: {
                **asdict(task),
                "state": "pending",
                "attempts": 0,
                "updated_at_utc": now,
                "error": None,
                "artifacts": {},
                "validation": None,
            }
            for task in tasks
        },
    }


def atomic_write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


@contextmanager
def locked_manifest(namespace: str, tasks: list[Task], config_hash: str) -> Iterator[dict]:
    path = manifest_path(namespace)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(".lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if path.exists():
            manifest = json.loads(path.read_text(encoding="utf-8"))
            expected = {task.task_id for task in tasks}
            actual = set(manifest["tasks"])
            if expected != actual:
                raise ValueError("manifest task set differs from frozen configuration")
        else:
            manifest = empty_manifest(namespace, tasks, config_hash)
        yield manifest
        manifest["updated_at_utc"] = utc_now()
        atomic_write_json(path, manifest)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def update_task(namespace: str, tasks: list[Task], config_hash: str, task_id: str, state: str, **updates: object) -> None:
    if state not in VALID_STATES:
        raise ValueError(f"invalid manifest state: {state}")
    with locked_manifest(namespace, tasks, config_hash) as manifest:
        row = manifest["tasks"][task_id]
        row["state"] = state
        row["updated_at_utc"] = utc_now()
        row.update(updates)


def reconcile_manifest(namespace: str, tasks: list[Task], config_hash: str) -> dict:
    with locked_manifest(namespace, tasks, config_hash) as manifest:
        for row in manifest["tasks"].values():
            state = row["state"]
            if state == "running" or state == "validating" or state == "generated":
                row["state"] = "failed"
                row["error"] = f"recovered interrupted task from {state}"
                row["updated_at_utc"] = utc_now()
            elif state == "completed":
                trial_text = row.get("artifacts", {}).get("trial")
                expected_hash = row.get("artifacts", {}).get("trial_sha256")
                if not trial_text or not expected_hash:
                    row["state"] = "corrupt"
                    row["error"] = "completed entry lacks trial path or SHA-256"
                else:
                    trial = REPO_ROOT / trial_text
                    if not trial.is_file():
                        row["state"] = "corrupt"
                        row["error"] = "completed trial is missing"
                    elif sha256(trial) != expected_hash:
                        row["state"] = "corrupt"
                        row["error"] = "completed trial SHA-256 mismatch"
        return json.loads(json.dumps(manifest))


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
