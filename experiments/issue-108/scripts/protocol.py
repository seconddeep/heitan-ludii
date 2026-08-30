#!/usr/bin/env python3
"""Frozen identities, integrity gates, and resilient manifests for Issue #108."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Iterator


SCRIPT = Path(__file__).resolve()
ISSUE_ROOT = SCRIPT.parent.parent
REPO_ROOT = ISSUE_ROOT.parent.parent
CONFIG_PATH = ISSUE_ROOT / "config.json"
LOCK_PATH = ISSUE_ROOT / "protocol-lock.json"
SOURCE_LOCK_PATH = ISSUE_ROOT / "source-lock.json"
RESULTS_ROOT = ISSUE_ROOT / "results"
FINALIZATION_PATH = RESULTS_ROOT / "production" / "finalization.json"
PRODUCTION_BLOCK_PATH = RESULTS_ROOT / "production" / "PRODUCTION_BLOCKED.json"
PRODUCTION_HEAD_LOCK_PATH = RESULTS_ROOT / "production" / "production-head-lock.json"
TRANSIENT_STATES = {"running", "generated", "normalizing", "validating"}
VALID_STATES = {"pending", "running", "generated", "normalizing", "validating", "completed", "interrupted", "failed", "corrupt"}


@dataclass(frozen=True)
class Task:
    task_id: str
    experiment_version: str
    namespace: str
    experiment_id: str
    iteration_limit: int
    game_index: int
    seed: int


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_config() -> dict:
    return load_json(CONFIG_PATH)


def tasks_from_config(config: dict, namespace: str, budget: int | None = None) -> list[Task]:
    if namespace == "pilot":
        specs = config["pilot"]["tasks"]
    elif namespace == "production":
        specs = config["production"]["primary_tasks"]
    else:
        raise ValueError(f"unknown namespace: {namespace}")
    tasks: list[Task] = []
    for spec in specs:
        iterations = int(spec["iteration_limit"])
        if budget is not None and iterations != budget:
            continue
        count = int(spec["games"] if namespace == "pilot" else spec["target_games"])
        seed_first = int(spec["seed_first"]) if namespace == "pilot" else int(config["production"]["base_seed"]) + int(spec["budget_seed_offset"])
        for zero_index in range(count):
            game_index = zero_index + 1
            task_id = f"{config['experiment_version']}-{namespace}-uct-{iterations:06d}-g{game_index:04d}"
            tasks.append(Task(task_id, config["experiment_version"], namespace, spec["id"], iterations, game_index, seed_first + zero_index))
    validate_unique_tasks(tasks)
    return tasks


def validate_unique_tasks(tasks: list[Task]) -> None:
    for label, values in {
        "task ID": [task.task_id for task in tasks],
        "game identity": [(task.namespace, task.iteration_limit, task.game_index) for task in tasks],
        "seed": [task.seed for task in tasks],
    }.items():
        if len(values) != len(set(values)):
            raise ValueError(f"duplicate {label}")


def validate_config(config: dict) -> None:
    pilot = tasks_from_config(config, "pilot")
    production = tasks_from_config(config, "production")
    validate_unique_tasks(pilot + production)
    budgets = [int(spec["iteration_limit"]) for spec in config["production"]["primary_tasks"]]
    if budgets != config["primary_budgets"] or budgets != [10000, 30000, 100000]:
        raise ValueError("primary budget declarations differ")
    if any(int(spec["target_games"]) != 100 for spec in config["production"]["primary_tasks"]):
        raise ValueError("production requires exactly 100 fixed tasks per budget")
    policy = config["stability_classification"]
    if policy["manual_override_allowed"] is not False or len(policy["rules_in_precedence_order"]) != 5:
        raise ValueError("classification precedence/manual-override policy is incomplete")
    diagnostics = config["central_supply_diagnostics"]
    if diagnostics["observation_unit"] != "Heitan-turn end only" or diagnostics["p1_early_turns"] != [1, 3, 5]:
        raise ValueError("central-Supply observation policy differs from the preregistration")


def atomic_write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def manifest_path(namespace: str) -> Path:
    return RESULTS_ROOT / namespace / "manifest.json"


def opaque_runner_id() -> str:
    value = os.environ.get("HEITAN108_RUNNER_ID", "local-runner")
    if not value or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in value):
        raise ValueError("HEITAN108_RUNNER_ID must be an opaque alphanumeric, dash, or underscore identifier")
    return value


def sanitize_error(value: object) -> str:
    text = str(value)
    replacements = [
        (str(REPO_ROOT), "$REPO_ROOT"),
        (str(Path.home()), "$USER_HOME"),
        (tempfile.gettempdir(), "$TMPDIR"),
    ]
    for original, replacement in replacements:
        if original:
            text = text.replace(original, replacement)
    return text


def empty_manifest(namespace: str, tasks: list[Task], config_hash: str) -> dict:
    now = utc_now()
    return {
        "schema_version": 1,
        "namespace": namespace,
        "config_sha256_at_creation": config_hash,
        "created_at_utc": now,
        "production_started_at_utc": now if namespace == "production" else None,
        "updated_at_utc": now,
        "tasks": {
            task.task_id: {
                **asdict(task), "state": "pending", "attempts": 0, "error": None,
                "failure_kind": None, "run_owner": None, "artifacts": {}, "validation": None,
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
        manifest = load_json(path) if path.exists() else empty_manifest(namespace, tasks, config_hash)
        if set(manifest["tasks"]) != {task.task_id for task in tasks}:
            raise ValueError("manifest task set differs from frozen configuration")
        yield manifest
        manifest["updated_at_utc"] = utc_now()
        atomic_write_json(path, manifest)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def update_task(namespace: str, tasks: list[Task], config_hash: str, task_id: str, state: str, **updates: object) -> None:
    if state not in VALID_STATES:
        raise ValueError(f"invalid state: {state}")
    with locked_manifest(namespace, tasks, config_hash) as manifest:
        row = manifest["tasks"][task_id]
        row.update(updates)
        row["state"] = state
        row["updated_at_utc"] = utc_now()
        row.setdefault("events", []).append({"at_utc": row["updated_at_utc"], "state": state, "error": updates.get("error")})


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def process_matches(pid: int, marker: str | None) -> bool:
    if not process_alive(pid):
        return False
    if not marker:
        return True
    completed = subprocess.run(["ps", "-o", "command=", "-p", str(pid)], text=True, capture_output=True, check=False)
    return completed.returncode == 0 and marker in completed.stdout


def process_owner_active(owner: dict) -> bool:
    if owner.get("runner_id") != opaque_runner_id():
        return False
    return process_matches(int(owner.get("pid", -1)), owner.get("command_marker")) or process_matches(int(owner.get("java_pid", -1)), owner.get("java_command_marker"))


def artifact_error(row: dict) -> str | None:
    for name in ("trial", "result", "validation"):
        relative = (row.get("artifacts") or {}).get(name)
        expected = (row.get("artifacts") or {}).get(f"{name}_sha256")
        if not relative or not expected:
            return f"completed entry lacks {name} path or hash"
        path = REPO_ROOT / relative
        if not path.is_file() or sha256(path) != expected:
            return f"completed {name} is missing or changed"
    return None


def reconcile_manifest(namespace: str, tasks: list[Task], config_hash: str) -> dict:
    with locked_manifest(namespace, tasks, config_hash) as manifest:
        for row in manifest["tasks"].values():
            if row["state"] in TRANSIENT_STATES and not process_owner_active(row.get("run_owner") or {}):
                previous = row["state"]
                row.update(state="interrupted", error=f"stale {previous}: recorded process is not active", run_owner=None, updated_at_utc=utc_now())
                row.setdefault("events", []).append({"at_utc": row["updated_at_utc"], "state": "interrupted", "from_state": previous, "error": row["error"]})
            elif row["state"] == "completed":
                error = artifact_error(row)
                if error:
                    row.update(state="corrupt", error=error, updated_at_utc=utc_now())
                    row.setdefault("events", []).append({"at_utc": row["updated_at_utc"], "state": "corrupt", "error": error})
        return json.loads(json.dumps(manifest))


def git(*args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=REPO_ROOT, text=True, capture_output=True, check=True)
    return completed.stdout.strip()


def worktree_gate(lock: dict) -> None:
    current_head = git("rev-parse", "HEAD")
    for args in (("diff", "--quiet"), ("diff", "--cached", "--quiet")):
        completed = subprocess.run(["git", *args], cwd=REPO_ROOT, check=False)
        if completed.returncode:
            raise ValueError("tracked files differ from HEAD")
    status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=REPO_ROOT, text=True, capture_output=True, check=True).stdout.splitlines()
    unexpected = []
    for line in status:
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if not path.startswith("experiments/issue-108/results/"):
            unexpected.append(line)
    if unexpected:
        raise ValueError(f"unexpected worktree entries: {unexpected}")
    for entry in lock["hashed_executable_sources"]:
        path = REPO_ROOT / entry["path"]
        if not path.is_file() or sha256(path) != entry["sha256"]:
            raise ValueError(f"locked source differs: {entry['path']}")
    if PRODUCTION_HEAD_LOCK_PATH.exists():
        head_lock = load_json(PRODUCTION_HEAD_LOCK_PATH)
        if head_lock["production_head_commit"] != current_head:
            raise ValueError("HEAD differs from the production head lock")
    else:
        atomic_write_json(PRODUCTION_HEAD_LOCK_PATH, {
            "schema_version": 1,
            "production_head_commit": current_head,
            "locked_at_utc": utc_now(),
            "protocol_lock_sha256": sha256(LOCK_PATH),
            "policy": lock["production_head_lock_policy"],
        })


def require_production_gate(config: dict, budget: int) -> dict:
    if config["protocol_status"] != "locked" or not LOCK_PATH.is_file() or not SOURCE_LOCK_PATH.is_file():
        raise ValueError("production is forbidden until both locks exist")
    if FINALIZATION_PATH.exists():
        raise ValueError("production has already been finalized")
    if PRODUCTION_BLOCK_PATH.exists():
        raise ValueError("production is blocked by an unresolved score/winner mismatch")
    lock = load_json(LOCK_PATH)
    if lock["config_sha256"] != sha256(CONFIG_PATH):
        raise ValueError("config differs from protocol lock")
    if lock["game_sha256"] != sha256(REPO_ROOT / config["game"]):
        raise ValueError("game differs from protocol lock")
    worktree_gate(lock)
    manifest = manifest_path("production")
    if manifest.exists():
        data = load_json(manifest)
        earlier = [value for value in config["primary_budgets"] if value < budget]
        for previous in earlier:
            rows = [row for row in data["tasks"].values() if int(row["iteration_limit"]) == previous]
            if len(rows) != 100 or any(row["state"] not in {"completed", "failed", "corrupt"} for row in rows):
                raise ValueError(f"earlier budget {previous} has not reached terminal task states")
            if any(row["state"] != "completed" and int(row["attempts"]) < int(config["operational_parameters"]["max_attempts"]) for row in rows):
                raise ValueError(f"earlier budget {previous} still has permitted retries")
    return lock


def block_production(task: Task, message: str) -> None:
    atomic_write_json(PRODUCTION_BLOCK_PATH, {
        "schema_version": 1, "blocked_at_utc": utc_now(), "task_id": task.task_id,
        "iteration_limit": task.iteration_limit, "game_index": task.game_index,
        "reason": "score_or_winner_reconstruction_mismatch", "message": sanitize_error(message),
        "resolution": "investigate and remove this gate only through a reviewed corrective change before any production resumes",
    })
