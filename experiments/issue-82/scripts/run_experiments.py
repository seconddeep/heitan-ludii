#!/usr/bin/env python3
"""Run resumable, per-game validation-gated Issue #82 self-play."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import time

import protocol


RUNNER = protocol.REPO_ROOT / "experiments/issue-62/scripts/Heitan3x3Experiment.java"
REPLAYER = protocol.REPO_ROOT / "experiments/issue-62/scripts/HeitanScaleReplay.java"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def read_one_csv(path: Path) -> dict[str, str]:
    rows = read_csv(path)
    if len(rows) != 1:
        raise ValueError(f"expected exactly one row in {path}, found {len(rows)}")
    return rows[0]


def write_one_csv(path: Path, row: dict[str, str]) -> None:
    temporary = path.with_suffix(".csv.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def normalize_trial_path(result_csv: Path, trial: Path) -> None:
    row = read_one_csv(result_csv)
    row["trial_file"] = trial.relative_to(protocol.REPO_ROOT).as_posix()
    write_one_csv(result_csv, row)


def expected_sites() -> set[str]:
    supplies = {f"S{row}{column}" for row in range(4) for column in range(4)}
    objectives = {f"O{row}{column}" for row in range(3) for column in range(3)}
    return supplies | objectives


def reconstruct_final_board(final_board: str) -> tuple[int, dict[str, int]]:
    encoded = final_board.split("|")
    if len(encoded) != 25:
        raise ValueError(f"final board has {len(encoded)} sites instead of Supply 16 + Objective 9 = 25")
    seen: set[str] = set()
    metrics = {
        "p1_secured_objectives": 0, "p2_secured_objectives": 0,
        "p1_advantage_objectives": 0, "p2_advantage_objectives": 0,
        "p1_objective_pieces": 0, "p2_objective_pieces": 0,
        "p1_total_pieces": 0, "p2_total_pieces": 0,
    }
    for value in encoded:
        name, state_text, p1_text, p2_text = value.split(":")
        if name in seen:
            raise ValueError(f"duplicate final-board site: {name}")
        seen.add(name)
        state, p1, p2 = int(state_text), int(p1_text), int(p2_text)
        metrics["p1_total_pieces"] += p1
        metrics["p2_total_pieces"] += p2
        if name.startswith("O"):
            metrics["p1_objective_pieces"] += p1
            metrics["p2_objective_pieces"] += p2
            if state == 3:
                metrics["p1_secured_objectives"] += 1
            elif state == 4:
                metrics["p2_secured_objectives"] += 1
            elif state == 1:
                metrics["p1_advantage_objectives"] += 1
            elif state == 2:
                metrics["p2_advantage_objectives"] += 1
    if seen != expected_sites():
        raise ValueError(f"final-board site set differs: missing={sorted(expected_sites() - seen)}, extra={sorted(seen - expected_sites())}")
    score1 = 280 * metrics["p1_secured_objectives"] + 28 * metrics["p1_advantage_objectives"] + metrics["p1_objective_pieces"]
    score2 = 280 * metrics["p2_secured_objectives"] + 28 * metrics["p2_advantage_objectives"] + metrics["p2_objective_pieces"]
    metrics["p1_score"] = score1
    metrics["p2_score"] = score2
    winner = 1 if score1 > score2 else 2 if score2 > score1 else 0
    return winner, metrics


def parse_peak_rss(stderr: str) -> int | None:
    mac = re.search(r"(\d+)\s+maximum resident set size", stderr, re.IGNORECASE)
    if mac:
        return int(mac.group(1))
    linux = re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", stderr, re.IGNORECASE)
    return int(linux.group(1)) * 1024 if linux else None


def process_rss_bytes(pid: int) -> int | None:
    try:
        completed = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(pid)], text=True, capture_output=True, check=False,
        )
    except OSError:
        return None
    if completed.returncode or not completed.stdout.strip():
        return None
    return int(completed.stdout.strip().splitlines()[0]) * 1024


def timed_java(command: list[str], timeout: int, on_start=None) -> tuple[subprocess.CompletedProcess[str], int | None]:
    process = subprocess.Popen(
        command, cwd=protocol.REPO_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if on_start is not None:
        on_start(process.pid)
    started = time.monotonic()
    peak_rss: int | None = None
    while process.poll() is None:
        rss = process_rss_bytes(process.pid)
        if rss is not None:
            peak_rss = rss if peak_rss is None else max(peak_rss, rss)
        if timeout and time.monotonic() - started > timeout:
            process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
            raise subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr)
        time.sleep(0.5)
    stdout, stderr = process.communicate()
    rss = process_rss_bytes(process.pid)
    if rss is not None:
        peak_rss = rss if peak_rss is None else max(peak_rss, rss)
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr), peak_rss


def validate_generated(task: protocol.Task, task_dir: Path, jar: Path, game: Path) -> dict:
    trial = task_dir / f"{task.experiment_id}-{task.game_index:04d}.trl"
    result_csv = task_dir / "result.csv"
    if not trial.is_file():
        raise FileNotFoundError("expected trial output is missing")
    if not result_csv.is_file():
        raise FileNotFoundError("expected result metadata is missing")
    result = read_one_csv(result_csv)
    required = {
        "experiment_id", "game_index", "seed", "iteration_limit", "completed", "end_type",
        "winner", "moves", "turns", "p1_score", "p2_score", "p1_total_pieces",
        "p2_total_pieces", "final_board", "deciding_criterion",
    }
    if not required.issubset(result):
        raise ValueError("malformed metadata: required columns are missing")
    identity = result["experiment_id"], int(result["game_index"]), int(result["seed"]), int(result["iteration_limit"])
    if identity != (task.experiment_id, task.game_index, task.seed, task.iteration_limit):
        raise ValueError("result metadata identity differs from frozen task")
    if result["completed"].lower() != "true" or result["end_type"] != "NaturalEnd":
        raise ValueError("game did not finish by NaturalEnd")
    if (int(result["moves"]), int(result["turns"])) != (54, 18):
        raise ValueError("game is not exactly 54 placements / 18 turns")
    if (int(result["p1_total_pieces"]), int(result["p2_total_pieces"])) != (27, 27):
        raise ValueError("each player did not place exactly 27 Pieces")

    raw = task_dir / "validation-raw"
    command = [
        "java", "-cp", str(jar), str(REPLAYER), str(game), "3x3", task.experiment_id,
        str(task.iteration_limit), str(task_dir), str(raw / "games.csv"),
        str(raw / "placements.csv"), str(raw / "turn-states.csv"), "false",
    ]
    replay = subprocess.run(command, cwd=protocol.REPO_ROOT, text=True, capture_output=True, check=False)
    if replay.returncode:
        raise ValueError(f"trial parse/legal replay failed: {replay.stderr.strip() or replay.stdout.strip()}")
    game_row = read_one_csv(raw / "games.csv")
    placements = read_csv(raw / "placements.csv")
    states = read_csv(raw / "turn-states.csv")
    if (int(game_row["moves"]), int(game_row["turns"]), game_row["end_type"]) != (54, 18, "NaturalEnd"):
        raise ValueError("replayed dimensions or ending differ")
    if len(placements) != 54 or len(states) != 18 * 25:
        raise ValueError("replay tables have unexpected row counts")
    mover_counts = {1: 0, 2: 0}
    turn_counts: dict[tuple[int, int], int] = {}
    for row in placements:
        mover, turn = int(row["mover"]), int(row["turn_number"])
        mover_counts[mover] += 1
        turn_counts[(turn, mover)] = turn_counts.get((turn, mover), 0) + 1
    if mover_counts != {1: 27, 2: 27}:
        raise ValueError(f"replayed per-player Pieces differ from 27/27: {mover_counts}")
    if len(turn_counts) != 18 or any(count != 3 for count in turn_counts.values()):
        raise ValueError("not every Heitan turn contains exactly three placements")
    for turn in range(1, 19):
        sites = {row["point"] for row in states if int(row["turn_number"]) == turn}
        if sites != expected_sites():
            raise ValueError(f"turn {turn} does not contain Supply 16 + Objective 9 = 25 sites")

    winner, metrics = reconstruct_final_board(result["final_board"])
    if metrics["p1_total_pieces"] != 27 or metrics["p2_total_pieces"] != 27:
        raise ValueError("final-board Piece totals differ from 27/27")
    reported_scores = int(result["p1_score"]), int(result["p2_score"])
    replay_scores = int(game_row["final_p1_score"]), int(game_row["final_p2_score"])
    if reported_scores != (metrics["p1_score"], metrics["p2_score"]) or replay_scores != reported_scores:
        raise ValueError("reconstructed lexicographic score differs from Ludii")
    if winner != int(result["winner"]) or winner != int(game_row["winner"]):
        raise ValueError("reconstructed winner differs from Ludii")
    return {
        "schema_version": 1, "validated": True, "legal_move_replay": True,
        "natural_end": True, "moves": 54, "turns": 18,
        "all_turns_have_three_placements": True, "p1_placements": 27, "p2_placements": 27,
        "supply_sites": 16, "objective_sites": 9, "total_sites": 25,
        "winner_reconstructed": True, "score_reconstructed": True,
        "winner": winner, "metrics": metrics, "trial_sha256": protocol.sha256(trial),
        "result_sha256": protocol.sha256(result_csv),
    }


def recover_final_if_valid(task: protocol.Task, final_dir: Path, jar: Path, game: Path) -> dict | None:
    if not final_dir.is_dir():
        return None
    try:
        return validate_generated(task, final_dir, jar, game)
    except Exception:
        return None


def failure_kind(error: BaseException, stderr: str = "") -> str:
    text = f"{error} {stderr}".lower()
    if "outofmemory" in text or "out of memory" in text or "oom" in text:
        return "oom"
    if isinstance(error, subprocess.TimeoutExpired):
        return "timeout"
    if isinstance(error, (ValueError, FileNotFoundError)):
        return "validation_failure"
    return "abnormal_exit"


def run_task(task: protocol.Task, all_tasks: list[protocol.Task], config_hash: str, jar: Path, game: Path, max_attempts: int, timeout: int, heap: str) -> str:
    started = time.monotonic()
    final_dir = protocol.RESULTS_ROOT / task.namespace / "tasks" / task.task_id
    recovered = recover_final_if_valid(task, final_dir, jar, game)
    if recovered is not None:
        validation_path = final_dir / "validation.json"
        protocol.atomic_write_json(validation_path, recovered)
        artifacts = artifact_manifest(final_dir, task, recovered)
        protocol.update_task(task.namespace, all_tasks, config_hash, task.task_id, "completed", error=None, failure_kind=None, run_owner=None, validation=recovered, artifacts=artifacts)
        return "recovered"

    with protocol.locked_manifest(task.namespace, all_tasks, config_hash) as manifest:
        row = manifest["tasks"][task.task_id]
        if row["state"] == "completed" or row["state"] in protocol.TRANSIENT_STATES:
            return "skipped"
        if int(row["attempts"]) >= max_attempts:
            return "attempts-exhausted"
        row["attempts"] = int(row["attempts"]) + 1
        row["state"] = "running"
        row["error"] = None
        row["run_owner"] = {
            "pid": os.getpid(), "host": socket.gethostname(), "started_at_utc": protocol.utc_now(),
            "command_marker": "experiments/issue-82/scripts/run_experiments.py",
        }
        row["updated_at_utc"] = protocol.utc_now()
        row.setdefault("events", []).append({"at_utc": row["updated_at_utc"], "state": "running", "attempt": row["attempts"], "run_owner": row["run_owner"]})

    temporary_parent = protocol.RESULTS_ROOT / task.namespace / ".tmp"
    temporary_parent.mkdir(parents=True, exist_ok=True)
    for stale in temporary_parent.glob(f"{task.task_id}-*"):
        quarantine(stale, task.namespace, f"{task.task_id}-interrupted")
    task_dir = Path(tempfile.mkdtemp(prefix=f"{task.task_id}-", dir=temporary_parent))
    stderr = ""
    peak_rss: int | None = None
    try:
        command = [
            "java", f"-Xmx{heap}", "-cp", str(jar), str(RUNNER), str(game), task.experiment_id,
            "UCT", "1", str(task.seed), str(task.iteration_limit), str(task_dir / "result.csv"),
            str(task_dir), str(protocol.REPO_ROOT), str(task.game_index - 1),
        ]
        def record_java_pid(java_pid: int) -> None:
            owner = {
                "pid": os.getpid(), "host": socket.gethostname(), "started_at_utc": protocol.utc_now(),
                "command_marker": "experiments/issue-82/scripts/run_experiments.py",
                "java_pid": java_pid, "java_command_marker": "Heitan3x3Experiment.java",
            }
            protocol.update_task(task.namespace, all_tasks, config_hash, task.task_id, "running", run_owner=owner)

        completed, peak_rss = timed_java(command, timeout, record_java_pid)
        stderr = completed.stderr
        if completed.returncode:
            raise RuntimeError(f"Java exit {completed.returncode}: {stderr.strip() or completed.stdout.strip()}")
        trial = task_dir / f"{task.experiment_id}-{task.game_index:04d}.trl"
        normalize_trial_path(task_dir / "result.csv", final_dir / trial.name)
        protocol.update_task(task.namespace, all_tasks, config_hash, task.task_id, "generated", peak_rss_bytes=peak_rss)
        protocol.update_task(task.namespace, all_tasks, config_hash, task.task_id, "validating")
        validation = validate_generated(task, task_dir, jar, game)
        validation_path = task_dir / "validation.json"
        protocol.atomic_write_json(validation_path, validation)
        final_dir.parent.mkdir(parents=True, exist_ok=True)
        if final_dir.exists():
            quarantine(final_dir, task.namespace, task.task_id)
        os.replace(task_dir, final_dir)
        artifacts = artifact_manifest(final_dir, task, validation)
        protocol.update_task(
            task.namespace, all_tasks, config_hash, task.task_id, "completed", error=None,
            failure_kind=None, run_owner=None, completed_at_utc=protocol.utc_now(),
            elapsed_seconds=round(time.monotonic() - started, 3), peak_rss_bytes=peak_rss,
            validation=validation, artifacts=artifacts,
        )
        return "completed"
    except Exception as error:
        kind = failure_kind(error, stderr)
        if task_dir.exists():
            quarantine(task_dir, task.namespace, f"{task.task_id}-attempt")
        protocol.update_task(
            task.namespace, all_tasks, config_hash, task.task_id,
            "corrupt" if kind == "validation_failure" else "failed",
            error=str(error), failure_kind=kind, run_owner=None,
            elapsed_seconds=round(time.monotonic() - started, 3), peak_rss_bytes=peak_rss,
        )
        return kind


def quarantine(path: Path, namespace: str, prefix: str) -> None:
    root = protocol.RESULTS_ROOT / namespace / "quarantine"
    root.mkdir(parents=True, exist_ok=True)
    os.replace(path, root / f"{prefix}-{time.time_ns()}")


def artifact_manifest(final_dir: Path, task: protocol.Task, validation: dict) -> dict[str, str]:
    trial = final_dir / f"{task.experiment_id}-{task.game_index:04d}.trl"
    result = final_dir / "result.csv"
    validation_path = final_dir / "validation.json"
    return {
        "trial": trial.relative_to(protocol.REPO_ROOT).as_posix(), "trial_sha256": validation["trial_sha256"],
        "result": result.relative_to(protocol.REPO_ROOT).as_posix(), "result_sha256": protocol.sha256(result),
        "validation": validation_path.relative_to(protocol.REPO_ROOT).as_posix(), "validation_sha256": protocol.sha256(validation_path),
    }


def require_lock(config: dict) -> None:
    if config["protocol_status"] != "locked" or not protocol.LOCK_PATH.is_file():
        raise ValueError("production is forbidden until the protocol is locked")
    lock = json.loads(protocol.LOCK_PATH.read_text(encoding="utf-8"))
    if lock["config_sha256"] != protocol.sha256(protocol.CONFIG_PATH):
        raise ValueError("config differs from protocol-lock.json")
    if protocol.FINALIZATION_PATH.exists():
        raise ValueError("production is finalized; further execution is forbidden")


def require_persistent_execution() -> None:
    if not os.environ.get("TMUX"):
        raise ValueError("production must run inside a persistent tmux session")
    if os.environ.get("HEITAN82_CAFFEINATE") != "1":
        raise ValueError("production runner must execute under caffeinate -i with HEITAN82_CAFFEINATE=1")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("namespace", choices=("pilot", "production"))
    parser.add_argument("--budget", type=int, choices=(10000, 30000, 100000, 300000))
    parser.add_argument("--ludii-jar", default=os.environ.get("LUDII_JAR", ""))
    parser.add_argument("--workers", type=int)
    args = parser.parse_args()
    config = protocol.load_config()
    protocol.validate_all_namespaces(config)
    if args.namespace == "production":
        require_lock(config)
        require_persistent_execution()
        if args.budget is None:
            parser.error("production requires --budget")
        if args.budget == 300000 and config["optional_budget"]["adoption_status"] != "included":
            parser.error("optional UCT 300k is not included by the locked protocol")
    all_tasks = protocol.tasks_from_config(config, args.namespace)
    tasks = [task for task in all_tasks if args.budget is None or task.iteration_limit == args.budget]
    if not tasks:
        parser.error("no tasks match this namespace and budget")
    config_hash = protocol.sha256(protocol.CONFIG_PATH)
    manifest = protocol.reconcile_manifest(args.namespace, all_tasks, config_hash)
    retry_states = set(config["operational_parameters"]["retry_states"])
    candidates = [task for task in tasks if manifest["tasks"][task.task_id]["state"] in retry_states]
    jar = Path(args.ludii_jar).expanduser().resolve()
    if not jar.is_file():
        parser.error("pass --ludii-jar or set LUDII_JAR to an existing file")
    game = protocol.REPO_ROOT / config["game"]
    budget_key = str(args.budget or tasks[0].iteration_limit)
    workers = args.workers or int(config["operational_parameters"]["worker_count_by_budget"][budget_key])
    if workers < 1:
        parser.error("workers must be positive")
    max_attempts = int(config["operational_parameters"]["max_attempts"])
    timeout = int(config["operational_parameters"]["timeout_seconds_per_game"])
    heap = str(config["operational_parameters"]["jvm_max_heap_by_budget"][budget_key])
    results: dict[str, str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run_task, task, all_tasks, config_hash, jar, game, max_attempts, timeout, heap): task for task in candidates}
        for future in concurrent.futures.as_completed(futures):
            task = futures[future]
            try:
                results[task.task_id] = future.result()
            except Exception as error:
                protocol.update_task(task.namespace, all_tasks, config_hash, task.task_id, "failed", error=f"runner worker exception: {error}", failure_kind="runner_worker_exception", run_owner=None)
                results[task.task_id] = "runner-worker-exception"
            print(f"{task.task_id}: {results[task.task_id]}", flush=True)
    final = json.loads(protocol.manifest_path(args.namespace).read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    for task in tasks:
        state = final["tasks"][task.task_id]["state"]
        counts[state] = counts.get(state, 0) + 1
    print(json.dumps({"budget": args.budget, "states": counts}, sort_keys=True), flush=True)
    if any(state != "completed" for state in (final["tasks"][task.task_id]["state"] for task in tasks)):
        raise SystemExit("some tasks remain incomplete; rerun the same command to resume")


if __name__ == "__main__":
    main()
