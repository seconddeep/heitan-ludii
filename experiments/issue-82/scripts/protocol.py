#!/usr/bin/env python3
"""Task identity, protocol lock, and resilient manifest helpers for Issue #82."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
from typing import Iterator


SCRIPT = Path(__file__).resolve()
ISSUE_ROOT = SCRIPT.parent.parent
REPO_ROOT = ISSUE_ROOT.parent.parent
CONFIG_PATH = ISSUE_ROOT / "config.json"
RESULTS_ROOT = ISSUE_ROOT / "results"
LOCK_PATH = ISSUE_ROOT / "protocol-lock.json"
FINALIZATION_PATH = RESULTS_ROOT / "production" / "finalization.json"
TRANSIENT_STATES = {"running", "generated", "validating"}
VALID_STATES = {"pending", "running", "generated", "validating", "completed", "interrupted", "failed", "corrupt"}


@dataclass(frozen=True)
class Task:
    task_id: str
    experiment_version: str
    namespace: str
    experiment_id: str
    iteration_limit: int
    game_index: int
    seed: int
    optional_budget: bool = False


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_config(path: Path = CONFIG_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _specs(config: dict, namespace: str) -> list[dict]:
    if namespace == "pilot":
        return list(config["pilot"]["tasks"])
    if namespace != "production":
        raise ValueError(f"unknown namespace: {namespace}")
    specs = list(config["production"]["primary_tasks"])
    optional = config["optional_budget"]
    if optional["adoption_status"] == "included":
        specs.append({**optional, "optional_budget": True})
    return specs


def tasks_from_config(config: dict, namespace: str, budget: int | None = None) -> list[Task]:
    version = str(config["experiment_version"])
    tasks: list[Task] = []
    for spec in _specs(config, namespace):
        iterations = int(spec["iteration_limit"])
        if budget is not None and iterations != budget:
            continue
        count = int(spec["games"] if namespace == "pilot" else spec["target_games"])
        if namespace == "pilot":
            seed_first = int(spec["seed_first"])
        else:
            seed_first = int(config["production"]["base_seed"]) + int(spec["budget_seed_offset"])
        optional = bool(spec.get("optional_budget_smoke") or spec.get("optional_budget"))
        for zero_index in range(count):
            game_index = zero_index + 1
            task_id = f"{version}-{namespace}-uct-{iterations:06d}-g{game_index:04d}"
            tasks.append(Task(task_id, version, namespace, str(spec["id"]), iterations, game_index, seed_first + zero_index, optional))
    validate_unique_tasks(tasks)
    return tasks


def validate_unique_tasks(tasks: list[Task]) -> None:
    checks = {
        "task ID": [task.task_id for task in tasks],
        "game identity": [(task.namespace, task.iteration_limit, task.game_index) for task in tasks],
        "seed": [task.seed for task in tasks],
    }
    for label, values in checks.items():
        if len(values) != len(set(values)):
            raise ValueError(f"duplicate {label}")


def validate_all_namespaces(config: dict) -> None:
    tasks = tasks_from_config(config, "pilot") + tasks_from_config(config, "production")
    validate_unique_tasks(tasks)
    primary = [int(spec["iteration_limit"]) for spec in config["production"]["primary_tasks"]]
    if primary != [int(value) for value in config["primary_budgets"]]:
        raise ValueError("primary budget declarations differ")
    if int(config["optional_budget"]["iteration_limit"]) in primary:
        raise ValueError("optional budget must remain separate from primary budgets")


def manifest_path(namespace: str) -> Path:
    return RESULTS_ROOT / namespace / "manifest.json"


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


def empty_manifest(namespace: str, tasks: list[Task], config_hash: str) -> dict:
    now = utc_now()
    return {
        "schema_version": 1,
        "namespace": namespace,
        "config_sha256_at_creation": config_hash,
        "created_at_utc": now,
        "updated_at_utc": now,
        "tasks": {
            task.task_id: {
                **asdict(task), "state": "pending", "attempts": 0, "error": None,
                "run_owner": None, "artifacts": {}, "validation": None,
                "elapsed_seconds": None, "peak_rss_bytes": None,
                "events": [{"at_utc": now, "state": "pending"}], "updated_at_utc": now,
            }
            for task in tasks
        },
    }


@contextmanager
def locked_manifest(namespace: str, tasks: list[Task], config_hash: str) -> Iterator[dict]:
    path = manifest_path(namespace)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if path.exists():
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if set(manifest["tasks"]) != {task.task_id for task in tasks}:
                raise ValueError("manifest task set differs from configuration")
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
        row.setdefault("events", []).append({"at_utc": row["updated_at_utc"], "state": state, "error": updates.get("error")})


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False


def pid_matches(pid: int, marker: str | None) -> bool:
    if not process_alive(pid):
        return False
    if not marker:
        return True
    try:
        completed = subprocess.run(
            ["ps", "-o", "command=", "-p", str(pid)], text=True, capture_output=True, check=False,
        )
    except OSError:
        # A restricted environment may permit the PID liveness check but deny
        # process-table inspection. Conservatively treat it as active.
        return True
    return completed.returncode == 0 and marker in completed.stdout


def process_owner_active(owner: dict) -> bool:
    if owner.get("host") != socket.gethostname():
        return False
    runner_active = pid_matches(int(owner.get("pid", -1)), owner.get("command_marker"))
    java_active = pid_matches(int(owner.get("java_pid", -1)), owner.get("java_command_marker"))
    return runner_active or java_active
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def artifact_error(row: dict) -> str | None:
    artifacts = row.get("artifacts") or {}
    for name in ("trial", "result", "validation"):
        relative = artifacts.get(name)
        expected = artifacts.get(f"{name}_sha256")
        if not relative or not expected:
            return f"completed entry lacks {name} path or SHA-256"
        path = REPO_ROOT / relative
        if not path.is_file():
            return f"completed {name} is missing"
        if sha256(path) != expected:
            return f"completed {name} SHA-256 mismatch"
    return None


def reconcile_manifest(namespace: str, tasks: list[Task], config_hash: str) -> dict:
    host = socket.gethostname()
    with locked_manifest(namespace, tasks, config_hash) as manifest:
        for row in manifest["tasks"].values():
            if row["state"] in TRANSIENT_STATES:
                owner = row.get("run_owner") or {}
                active = owner.get("host") == host and process_owner_active(owner)
                if not active:
                    previous = row["state"]
                    row["state"] = "interrupted"
                    row["error"] = f"stale {previous}: owner process is not active on recorded host"
                    row["run_owner"] = None
                    row["updated_at_utc"] = utc_now()
                    row.setdefault("events", []).append({"at_utc": row["updated_at_utc"], "state": "interrupted", "from_state": previous, "error": row["error"]})
            elif row["state"] == "completed":
                error = artifact_error(row)
                if error:
                    row["state"] = "corrupt"
                    row["error"] = error
                    row["updated_at_utc"] = utc_now()
                    row.setdefault("events", []).append({"at_utc": row["updated_at_utc"], "state": "corrupt", "error": error})
        return json.loads(json.dumps(manifest))
