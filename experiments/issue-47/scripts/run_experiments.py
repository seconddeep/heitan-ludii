#!/usr/bin/env python3
"""Run resumable, validation-gated Issue #47 self-play tasks."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

import protocol


RUNNER = protocol.REPO_ROOT / "experiments/issue-11/scripts/HeitanExperiment.java"
REPLAYER = protocol.REPO_ROOT / "experiments/issue-37/scripts/HeitanSupplyReplay.java"


def read_one_csv(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 1:
        raise ValueError(f"expected exactly one row in {path}, found {len(rows)}")
    return rows[0]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def rewrite_trial_path(result_csv: Path, trial_relative_path: str) -> None:
    with result_csv.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = reader.fieldnames
    if fields is None or len(rows) != 1 or "trial_file" not in fields:
        raise ValueError("cannot normalize trial path in generated metadata")
    rows[0]["trial_file"] = trial_relative_path
    temporary = result_csv.with_suffix(".csv.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, result_csv)


def reconstruct_winner(final_board: str) -> tuple[int, dict[str, int]]:
    sites = final_board.split("|")
    if len(sites) != 41:
        raise ValueError(f"final board has {len(sites)} sites instead of 41")
    metrics = {
        "p1_secured_objectives": 0, "p2_secured_objectives": 0,
        "p1_advantage_objectives": 0, "p2_advantage_objectives": 0,
        "p1_objective_pieces": 0, "p2_objective_pieces": 0,
    }
    for encoded in sites:
        name, state_text, p1_text, p2_text = encoded.split(":")
        state, p1, p2 = int(state_text), int(p1_text), int(p2_text)
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
    p1_key = (metrics["p1_secured_objectives"], metrics["p1_advantage_objectives"], metrics["p1_objective_pieces"])
    p2_key = (metrics["p2_secured_objectives"], metrics["p2_advantage_objectives"], metrics["p2_objective_pieces"])
    return (1 if p1_key > p2_key else 2 if p2_key > p1_key else 0), metrics


def adjacent(objective: str, supply: str) -> bool:
    orow, ocol = int(objective[1]), int(objective[2])
    srow, scol = int(supply[1]), int(supply[2])
    return srow in (orow, orow + 1) and scol in (ocol, ocol + 1)


def validate_generated(task: protocol.Task, task_dir: Path, jar: Path, game: Path) -> dict:
    trial = task_dir / f"{task.experiment_id}-{task.game_index:04d}.trl"
    result_csv = task_dir / "result.csv"
    if not trial.is_file():
        raise FileNotFoundError("expected trial output is missing")
    if not result_csv.is_file():
        raise FileNotFoundError("expected game metadata is missing")
    result = read_one_csv(result_csv)
    required_metadata = {
        "experiment_id", "game_index", "seed", "iteration_limit", "completed",
        "end_type", "winner", "moves", "turns", "final_board",
    }
    if not required_metadata.issubset(result):
        raise ValueError("malformed metadata: required columns are missing")
    if result["experiment_id"] != task.experiment_id or int(result["game_index"]) != task.game_index:
        raise ValueError("metadata game identity mismatch")
    if int(result["seed"]) != task.seed or int(result["iteration_limit"]) != task.iteration_limit:
        raise ValueError("metadata seed or budget mismatch")

    replay_root = task_dir / "replay-input"
    replay_trials = replay_root / task.experiment_id
    replay_trials.mkdir(parents=True, exist_ok=True)
    replay_trial = replay_trials / trial.name
    shutil.copy2(trial, replay_trial)
    validation_raw = task_dir / "validation-raw"
    validation_raw.mkdir(parents=True, exist_ok=True)
    command = [
        "java", "-cp", str(jar), str(REPLAYER), str(game), str(replay_root), task.experiment_id,
        str(validation_raw / "replay-summary.csv"), str(validation_raw / "placements.csv"),
        str(validation_raw / "supply-turn-states.csv"), str(validation_raw / "objective-turn-states.csv"),
    ]
    completed = subprocess.run(command, cwd=protocol.REPO_ROOT, text=True, capture_output=True, check=False)
    if completed.returncode:
        raise ValueError(f"trial parse/legal replay failed: {completed.stderr.strip() or completed.stdout.strip()}")
    replay = read_one_csv(validation_raw / "replay-summary.csv")
    placements = read_csv(validation_raw / "placements.csv")
    if result["completed"].lower() != "true" or replay["end_type"] != "NaturalEnd":
        raise ValueError("game did not finish by NaturalEnd")
    if int(replay["moves"]) != 72 or int(replay["turns"]) != 24 or len(placements) != 72:
        raise ValueError("game does not contain exactly 72 placements and 24 turns")
    mover_counts = {1: 0, 2: 0}
    turn_counts: dict[tuple[int, int], int] = {}
    used_supply: set[tuple[int, int, str]] = set()
    for row in placements:
        mover = int(row["mover"])
        turn = int(row["turn_number"])
        mover_counts[mover] += 1
        turn_counts[(turn, mover)] = turn_counts.get((turn, mover), 0) + 1
        if row["target_type"] == "objective":
            source = row["supply_source"]
            if not source or not adjacent(row["target"], source):
                raise ValueError("Objective Supply source is missing or non-adjacent")
            key = (turn, mover, source)
            if key in used_supply:
                raise ValueError("Supply Point was used twice within one turn")
            used_supply.add(key)
    if mover_counts != {1: 36, 2: 36}:
        raise ValueError(f"placements per player are not 36/36: {mover_counts}")
    if sorted(turn_counts.values()) != [3] * 24:
        raise ValueError("not every complete Heitan turn has exactly three placements")
    if replay["final_board"] != result["final_board"]:
        raise ValueError("replayed and generated final boards differ")
    winner, metrics = reconstruct_winner(replay["final_board"])
    if winner != int(replay["winner"]) or winner != int(result["winner"]):
        raise ValueError("winner is not reproducible from the lexicographic criteria")
    return {
        "schema_version": 1,
        "validated": True,
        "natural_end": True,
        "trial_parsed": True,
        "legal_move_replay": True,
        "moves": 72,
        "turns": 24,
        "p1_placements": 36,
        "p2_placements": 36,
        "objective_supply_sources_legal": True,
        "supply_source_adjacency_verified": True,
        "supply_source_control_verified_by_legal_replay": True,
        "no_duplicate_supply_source_per_turn": True,
        "final_board_sites": 41,
        "winner": winner,
        "winner_reconstructed": True,
        "final_metrics": metrics,
        "trial_sha256": protocol.sha256(trial),
        "result_sha256": protocol.sha256(result_csv),
    }


def recover_final_if_valid(task: protocol.Task, final_dir: Path, jar: Path, game: Path) -> dict | None:
    if not final_dir.is_dir():
        return None
    try:
        return validate_generated(task, final_dir, jar, game)
    except Exception:
        return None


def run_task(task: protocol.Task, all_tasks: list[protocol.Task], config_hash: str, jar: Path, game: Path, max_attempts: int, timeout: int, jvm_max_heap: str) -> str:
    started_monotonic = time.monotonic()
    started_at = protocol.utc_now()
    final_dir = protocol.RESULTS_ROOT / task.namespace / "tasks" / task.task_id
    recovered = recover_final_if_valid(task, final_dir, jar, game)
    if recovered is not None:
        validation_path = final_dir / "validation.json"
        protocol.atomic_write_json(validation_path, recovered)
        protocol.update_task(
            task.namespace, all_tasks, config_hash, task.task_id, "completed", error=None,
            validation=recovered,
            artifacts={
                "trial": (final_dir / f"{task.experiment_id}-{task.game_index:04d}.trl").relative_to(protocol.REPO_ROOT).as_posix(),
                "trial_sha256": recovered["trial_sha256"],
                "result": (final_dir / "result.csv").relative_to(protocol.REPO_ROOT).as_posix(),
                "validation": validation_path.relative_to(protocol.REPO_ROOT).as_posix(),
            },
        )
        return "recovered"
    if final_dir.exists():
        quarantine = protocol.RESULTS_ROOT / task.namespace / "quarantine"
        quarantine.mkdir(parents=True, exist_ok=True)
        os.replace(final_dir, quarantine / f"{task.task_id}-{int(time.time())}")

    with protocol.locked_manifest(task.namespace, all_tasks, config_hash) as manifest:
        row = manifest["tasks"][task.task_id]
        if row["state"] == "completed":
            return "skipped"
        if int(row["attempts"]) >= max_attempts:
            return "attempts-exhausted"
        row["attempts"] = int(row["attempts"]) + 1
        row["state"] = "running"
        row["error"] = None
        row["started_at_utc"] = started_at
        row["updated_at_utc"] = protocol.utc_now()

    temporary_parent = protocol.RESULTS_ROOT / task.namespace / ".tmp"
    temporary_parent.mkdir(parents=True, exist_ok=True)
    task_dir = Path(tempfile.mkdtemp(prefix=f"{task.task_id}-", dir=temporary_parent))
    try:
        command = [
            "java", f"-Xmx{jvm_max_heap}", "-cp", str(jar), str(RUNNER), str(game), task.experiment_id,
            "UCT", "UCT", "1", str(task.seed), str(task.iteration_limit), "-1.0",
            str(task_dir / "result.csv"), str(task_dir), str(task.game_index - 1),
        ]
        completed = subprocess.run(
            command, cwd=protocol.REPO_ROOT, text=True, capture_output=True,
            timeout=None if timeout == 0 else timeout, check=False,
        )
        if completed.returncode:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "generation failed")
        rewrite_trial_path(
            task_dir / "result.csv",
            (final_dir / f"{task.experiment_id}-{task.game_index:04d}.trl")
            .relative_to(protocol.REPO_ROOT).as_posix(),
        )
        protocol.update_task(task.namespace, all_tasks, config_hash, task.task_id, "generated")
        protocol.update_task(task.namespace, all_tasks, config_hash, task.task_id, "validating")
        validation = validate_generated(task, task_dir, jar, game)
        protocol.atomic_write_json(task_dir / "validation.json", validation)
        shutil.rmtree(task_dir / "replay-input")
        final_dir.parent.mkdir(parents=True, exist_ok=True)
        os.replace(task_dir, final_dir)
        protocol.update_task(
            task.namespace, all_tasks, config_hash, task.task_id, "completed", error=None,
            completed_at_utc=protocol.utc_now(), elapsed_seconds=round(time.monotonic() - started_monotonic, 3),
            validation=validation,
            artifacts={
                "trial": (final_dir / f"{task.experiment_id}-{task.game_index:04d}.trl").relative_to(protocol.REPO_ROOT).as_posix(),
                "trial_sha256": validation["trial_sha256"],
                "result": (final_dir / "result.csv").relative_to(protocol.REPO_ROOT).as_posix(),
                "validation": (final_dir / "validation.json").relative_to(protocol.REPO_ROOT).as_posix(),
            },
        )
        return "completed"
    except subprocess.TimeoutExpired as error:
        protocol.update_task(task.namespace, all_tasks, config_hash, task.task_id, "failed", error=f"timeout: {error}")
        return "failed"
    except Exception as error:
        quarantine = protocol.RESULTS_ROOT / task.namespace / "quarantine"
        quarantine.mkdir(parents=True, exist_ok=True)
        if task_dir.exists():
            os.replace(task_dir, quarantine / f"{task.task_id}-attempt-{int(time.time())}")
        state = "corrupt" if isinstance(error, (ValueError, FileNotFoundError)) else "failed"
        protocol.update_task(task.namespace, all_tasks, config_hash, task.task_id, state, error=str(error))
        return state


def require_protocol_lock(config: dict) -> None:
    lock_path = protocol.ISSUE_ROOT / "protocol-lock.json"
    if config.get("protocol_status") != "locked" or not lock_path.is_file():
        raise ValueError("production is forbidden until the post-pilot protocol is locked")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("config_sha256") != protocol.sha256(protocol.CONFIG_PATH):
        raise ValueError("config no longer matches protocol-lock.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("namespace", choices=("pilot", "production"))
    parser.add_argument("--budget", type=int, choices=(30000, 100000))
    parser.add_argument("--ludii-jar", default=os.environ.get("LUDII_JAR", ""))
    parser.add_argument("--workers", type=int)
    args = parser.parse_args()
    config = protocol.load_config()
    protocol.validate_all_namespaces(config)
    if args.namespace == "production":
        require_protocol_lock(config)
        if args.budget is None:
            parser.error("production requires --budget")
        if args.budget == 100000:
            manifest_30k = protocol.manifest_path("production")
            if not manifest_30k.is_file():
                raise ValueError("30k production must complete before 100k starts")
            rows = json.loads(manifest_30k.read_text(encoding="utf-8"))["tasks"].values()
            thirty = [row for row in rows if int(row["iteration_limit"]) == 30000]
            if len(thirty) != 100 or any(row["state"] != "completed" for row in thirty):
                raise ValueError("all 100 UCT-30k games must validate before 100k starts")
    all_tasks = protocol.tasks_from_config(config, args.namespace)
    tasks = [task for task in all_tasks if args.budget is None or task.iteration_limit == args.budget]
    config_hash = protocol.sha256(protocol.CONFIG_PATH)
    manifest = protocol.reconcile_manifest(args.namespace, all_tasks, config_hash)
    pending = [task for task in tasks if manifest["tasks"][task.task_id]["state"] != "completed"]
    jar = Path(args.ludii_jar).expanduser().resolve()
    if not jar.is_file():
        parser.error("pass --ludii-jar or set LUDII_JAR to an existing file")
    game = protocol.REPO_ROOT / config["game"]
    workers = args.workers or int(config["operational_parameters"]["worker_count_by_budget"][str(args.budget or 30000)])
    max_attempts = int(config["operational_parameters"]["max_attempts"])
    timeout = int(config["operational_parameters"]["timeout_seconds_per_game"])
    jvm_max_heap = str(config["operational_parameters"]["jvm_max_heap_by_budget"][str(args.budget or 30000)])
    if workers < 1:
        parser.error("workers must be positive")
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(run_task, task, all_tasks, config_hash, jar, game, max_attempts, timeout, jvm_max_heap): task
            for task in pending
        }
        for future in concurrent.futures.as_completed(futures):
            task = futures[future]
            print(f"{task.task_id}: {future.result()}", flush=True)
    final_manifest = json.loads(protocol.manifest_path(args.namespace).read_text(encoding="utf-8"))
    incomplete = [task.task_id for task in tasks if final_manifest["tasks"][task.task_id]["state"] != "completed"]
    if incomplete:
        raise SystemExit(f"{len(incomplete)} task(s) remain incomplete")


if __name__ == "__main__":
    main()
