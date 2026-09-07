#!/usr/bin/env python3
"""Identity, source gates, manifests, and safety helpers for Issue #116."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
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
PRODUCTION_HEAD_LOCK_PATH = RESULTS_ROOT / "measured" / "production-head-lock.json"
BOARDS = ("6x6", "7x7", "8x8")
BUDGETS = (1000, 3000, 10000, 30000)
TERMINAL_STATES = {"completed", "failed", "not_attempted"}


@dataclass(frozen=True)
class Task:
    task_id: str
    namespace: str
    board: str
    iteration_limit: int
    game_index: int
    seed: int


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value: object) -> None:
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_config() -> dict:
    return load_json(CONFIG_PATH)


def tasks(config: dict, namespace: str) -> list[Task]:
    result: list[Task] = []
    if namespace == "pilot":
        budget = int(config["pilot"]["iteration_limit"])
        for board in config["boards"]:
            result.append(Task(f"issue-116-v1-pilot-{board}-uct-{budget:05d}", namespace, board, budget, 1, int(config["pilot"]["seed_first_by_board"][board])))
    elif namespace == "measured":
        base = int(config["measured"]["base_seed"])
        count = int(config["measured_games_per_condition"])
        for board in config["boards"]:
            size = int(board.split("x")[0])
            for budget in config["uct_budgets"]:
                for zero_index in range(count):
                    index = zero_index + 1
                    seed = base + size * 1_000_000 + int(budget) * 10 + zero_index
                    result.append(Task(f"issue-116-v1-measured-{board}-uct-{int(budget):05d}-g{index:02d}", namespace, board, int(budget), index, seed))
    else:
        raise ValueError(f"unknown namespace: {namespace}")
    identities = [task.task_id for task in result]
    seeds = [task.seed for task in result]
    if len(identities) != len(set(identities)) or len(seeds) != len(set(seeds)):
        raise ValueError("task IDs and seeds must be unique")
    return result


def validate_prepilot_config(config: dict) -> None:
    if tuple(config["boards"]) != BOARDS or tuple(config["uct_budgets"]) != BUDGETS:
        raise ValueError("board/UCT matrix differs from preregistration")
    if int(config["measured_games_per_condition"]) != 3 or int(config["primary_worker_count"]) != 1:
        raise ValueError("measured count or worker count differs from preregistration")
    if config["constraints"]["failed_seed_replacement_allowed"] is not False:
        raise ValueError("failed-seed replacement must be forbidden")
    if config["classification"]["manual_override_allowed"] is not False:
        raise ValueError("classification override must be forbidden")
    tasks(config, "pilot")
    tasks(config, "measured")


def extract_board_values(game_path: Path, expected: dict) -> dict[str, dict[str, int]]:
    text = game_path.read_text(encoding="utf-8")
    result: dict[str, dict[str, int]] = {}
    for board in BOARDS:
        marker = f'(item "{board}"'
        starts = [match.start() for match in re.finditer(re.escape(marker), text)]
        if len(starts) != 1:
            raise ValueError(f"Board/{board} must occur exactly once")
        later = [text.find(f'(item "{other}"', starts[0] + 1) for other in BOARDS if text.find(f'(item "{other}"', starts[0] + 1) >= 0]
        end = min(later) if later else text.find("//------------------------------------------------------------------------------\n// Shared Heitan mechanics", starts[0])
        if end < 0:
            raise ValueError(f"cannot isolate Board/{board}")
        positional = [int(value) for value in re.findall(r"<\s*(\d+)\s*>", text[starts[0]:end])]
        if len(positional) != 4:
            raise ValueError(f"Board/{board} positional values are ambiguous: {positional}")
        size = int(board.split("x")[0])
        values = {
            "pieces_per_player": positional[0], "total_placements": positional[1],
            "turns": positional[1] // 3, "advantage_weight": positional[2],
            "secured_weight": positional[3], "supply_points": (size + 1) ** 2,
            "objectives": size ** 2, "sites": (size + 1) ** 2 + size ** 2,
        }
        if positional[1] % 3 or values != {key: int(value) for key, value in expected[board].items()}:
            raise ValueError(f"source-derived Board/{board} values differ from expected values: {values}")
        result[board] = values
    return result


def manifest_path(namespace: str) -> Path:
    return RESULTS_ROOT / namespace / "manifest.json"


def empty_manifest(namespace: str, all_tasks: list[Task], config_hash: str) -> dict:
    now = utc_now()
    return {"schema_version": 1, "namespace": namespace, "config_sha256_at_creation": config_hash, "created_at_utc": now, "updated_at_utc": now,
            "tasks": {task.task_id: {**asdict(task), "state": "pending", "attempts": 0, "start_utc": None, "end_utc": None,
                                           "elapsed_seconds": None, "exit_code": None, "failure_classification": None,
                                           "peak_rss_bytes": None, "physical_ram_bytes": None, "jvm_xmx": None,
                                           "gc_log_status": None, "gc_pause_count": None, "gc_pause_seconds": None,
                                           "trial_status": None, "trial_sha256": None, "replay_validation_status": None,
                                           "artifacts": {}, "error": None} for task in all_tasks}}


@contextmanager
def locked_manifest(namespace: str, all_tasks: list[Task], config_hash: str) -> Iterator[dict]:
    path = manifest_path(namespace)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        manifest = load_json(path) if path.exists() else empty_manifest(namespace, all_tasks, config_hash)
        if set(manifest["tasks"]) != {task.task_id for task in all_tasks}:
            raise ValueError("manifest task set differs from frozen identities")
        yield manifest
        manifest["updated_at_utc"] = utc_now()
        atomic_json(path, manifest)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def sanitize(value: object) -> str:
    text = str(value)
    for original, replacement in ((str(REPO_ROOT), "$REPO_ROOT"), (str(Path.home()), "$USER_HOME"), (tempfile.gettempdir(), "$TMPDIR")):
        text = text.replace(original, replacement)
    return text


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, text=True, capture_output=True, check=True).stdout.strip()


def verify_source_lock(lock: dict) -> None:
    if lock["source_lock_sha256"] != sha256(SOURCE_LOCK_PATH):
        raise ValueError("source lock hash differs")
    for entry in load_json(SOURCE_LOCK_PATH)["files"]:
        path = REPO_ROOT / entry["path"]
        if not path.is_file() or path.stat().st_size != int(entry["bytes"]) or sha256(path) != entry["sha256"]:
            raise ValueError(f"source-locked file differs: {entry['path']}")


def measured_gate(config: dict) -> dict:
    if config["protocol_status"] != "postpilot-locked" or not LOCK_PATH.is_file() or not SOURCE_LOCK_PATH.is_file():
        raise ValueError("measured benchmark requires the post-pilot locks")
    lock = load_json(LOCK_PATH)
    if sha256(CONFIG_PATH) != lock["config_sha256"] or sha256(REPO_ROOT / config["game"]) != lock["game_sha256"]:
        raise ValueError("locked config or game differs")
    verify_source_lock(lock)
    derived = extract_board_values(REPO_ROOT / config["game"], config["expected_board_values"])
    if derived != lock["source_derived_board_values"]:
        raise ValueError("source-derived board gate differs from lock")
    for args in (("diff", "--quiet"), ("diff", "--cached", "--quiet")):
        if subprocess.run(["git", *args], cwd=REPO_ROOT, check=False).returncode:
            raise ValueError("tracked worktree must be clean")
    unexpected = [line for line in git("status", "--porcelain", "--untracked-files=all").splitlines() if line and not line[3:].startswith("experiments/issue-116/results/")]
    if unexpected:
        raise ValueError(f"unexpected worktree entries: {unexpected}")
    head = git("rev-parse", "HEAD")
    if PRODUCTION_HEAD_LOCK_PATH.exists():
        if load_json(PRODUCTION_HEAD_LOCK_PATH)["production_head_commit"] != head:
            raise ValueError("HEAD differs from production head lock")
    else:
        atomic_json(PRODUCTION_HEAD_LOCK_PATH, {"schema_version": 1, "production_head_commit": head, "locked_at_utc": utc_now(), "protocol_lock_sha256": sha256(LOCK_PATH)})
    return lock


def source_entry(path: Path) -> dict:
    return {"path": path.resolve().relative_to(REPO_ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}
