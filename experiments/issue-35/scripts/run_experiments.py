#!/usr/bin/env python3
"""Run repeated one-turn UCT searches for Issue #35 positions."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time


SCRIPT = Path(__file__).resolve()
ISSUE_ROOT = SCRIPT.parent.parent
REPO_ROOT = ISSUE_ROOT.parent.parent
DEFAULT_CONFIG = ISSUE_ROOT / "config.json"
DEFAULT_POSITIONS = ISSUE_ROOT / "positions.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_batch(task: dict[str, object]) -> dict[str, object]:
    command = [
        "java", "-cp", str(task["jar"]), str(task["runner"]),
        str(task["game"]), str(task["source"]), str(task["prefix"]),
        str(task["position_id"]), str(task["mover"]), str(task["budget"]),
        str(task["repetitions"]), str(task["seed"]), str(task["max_seconds"]),
        str(task["raw"]), str(task["trials"]), str(task["offset"]),
        str(task["source_hash"]), str(task["prefix_hash"]),
    ]
    started = time.monotonic()
    completed = subprocess.run(command, cwd=REPO_ROOT, check=False)
    elapsed = time.monotonic() - started
    if completed.returncode:
        raise RuntimeError(
            f"batch failed: {task['position_id']} budget={task['budget']} "
            f"offset={task['offset']} exit={completed.returncode}"
        )
    return {
        "position_id": task["position_id"],
        "iteration_budget": task["budget"],
        "repetitions": task["repetitions"],
        "worker_seconds": elapsed,
    }


def parse_int_list(value: str) -> list[int]:
    try:
        result = [int(item) for item in value.split(",") if item]
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected comma-separated integers") from error
    if not result or any(item <= 0 for item in result):
        raise argparse.ArgumentTypeError("budgets must be positive")
    return result


def parse_str_list(value: str) -> list[str]:
    result = [item for item in value.split(",") if item]
    if not result:
        raise argparse.ArgumentTypeError("expected comma-separated position IDs")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ludii-jar", default=os.environ.get("LUDII_JAR", ""))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--positions-file", type=Path, default=DEFAULT_POSITIONS)
    parser.add_argument("--parallelism", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--repetitions-override", type=int)
    parser.add_argument("--budgets", type=parse_int_list)
    parser.add_argument("--positions", type=parse_str_list)
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--metadata-only", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.parallelism <= 64:
        parser.error("--parallelism must be between 1 and 64")
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    if args.repetitions_override is not None and args.repetitions_override < 1:
        parser.error("--repetitions-override must be positive")

    jar = Path(args.ludii_jar).expanduser().resolve()
    if not jar.is_file():
        parser.error("pass --ludii-jar or set LUDII_JAR to an existing file")
    config_path = args.config.resolve()
    positions_path = args.positions_file.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    position_document = json.loads(positions_path.read_text(encoding="utf-8"))
    if config["ludii_version"] != "1.3.14":
        raise ValueError("this workflow is validated against Ludii 1.3.14")
    if config["plan_signature"]["version"] != 1:
        raise ValueError("unsupported frozen plan_signature version")

    selected_positions = position_document["positions"]
    if args.positions:
        wanted = set(args.positions)
        selected_positions = [item for item in selected_positions if item["position_id"] in wanted]
        missing = wanted.difference(item["position_id"] for item in selected_positions)
        if missing:
            parser.error(f"unknown position IDs: {', '.join(sorted(missing))}")
    budgets = args.budgets or [int(value) for value in config["required_iteration_budgets"]]
    allowed = set(int(value) for value in config["required_iteration_budgets"])
    allowed.add(int(config["optional_iteration_budget"]))
    if not set(budgets).issubset(allowed):
        parser.error(f"budgets must be configured values: {sorted(allowed)}")

    game = REPO_ROOT / config["game"]
    runner = SCRIPT.parent / "HeitanPositionSearch.java"
    analyzer = SCRIPT.parent / "analyze_results.py"
    results = ISSUE_ROOT / "results"
    raw_dir = results / "raw"
    trials_dir = results / "trials"
    raw_dir.mkdir(parents=True, exist_ok=True)
    trials_dir.mkdir(parents=True, exist_ok=True)
    if not args.append and not args.metadata_only:
        for path in raw_dir.glob("*.csv"):
            path.unlink()
        if trials_dir.exists():
            shutil.rmtree(trials_dir)
            trials_dir.mkdir(parents=True)

    repetitions = int(args.repetitions_override or config["repetitions"])
    started_at = time.time()
    batch_results: list[dict[str, object]] = []
    if not args.metadata_only:
        tasks: list[dict[str, object]] = []
        for position_index, position in enumerate(selected_positions):
            source = REPO_ROOT / position["source_trl_path"]
            if sha256(source) != position["source_trial_hash"]:
                raise ValueError(f"source trial hash mismatch: {source}")
            for budget in budgets:
                output_trials = trials_dir / position["position_id"] / f"uct-{budget}"
                output_trials.mkdir(parents=True, exist_ok=True)
                for offset in range(0, repetitions, args.batch_size):
                    count = min(args.batch_size, repetitions - offset)
                    batch = offset // args.batch_size + 1
                    raw_path = raw_dir / (
                        f"{position['position_id']}-uct-{budget}-batch-{batch:03d}.csv"
                    )
                    if args.append and raw_path.exists():
                        raise FileExistsError(f"append would overwrite {raw_path}")
                    tasks.append({
                        "jar": jar, "runner": runner, "game": game, "source": source,
                        "prefix": position["prefix_placement_count"],
                        "position_id": position["position_id"], "mover": position["mover"],
                        "budget": budget, "repetitions": count,
                        "seed": int(config["base_seed"]) + position_index * 10_000_000
                                + budget * 10 + offset,
                        "max_seconds": config["max_seconds_per_move"], "raw": raw_path,
                        "trials": output_trials, "offset": offset,
                        "source_hash": position["source_trial_hash"],
                        "prefix_hash": position["prefix_hash"],
                    })

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallelism) as pool:
            futures = [pool.submit(run_batch, task) for task in tasks]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                batch_results.append(result)
                print(
                    f"completed {result['position_id']} at {result['iteration_budget']} "
                    f"iterations ({result['repetitions']} repetitions)", flush=True,
                )

        timing_path = results / "timings.csv"
        existing: list[dict[str, str]] = []
        if args.append and timing_path.is_file():
            with timing_path.open(newline="", encoding="utf-8") as handle:
                existing = list(csv.DictReader(handle))
        timing_rows: list[dict[str, object]] = list(existing)
        for position in selected_positions:
            for budget in budgets:
                group = [item for item in batch_results
                         if item["position_id"] == position["position_id"]
                         and item["iteration_budget"] == budget]
                seconds = sum(float(item["worker_seconds"]) for item in group)
                timing_rows.append({
                    "position_id": position["position_id"],
                    "iteration_budget": budget,
                    "repetitions": repetitions,
                    "worker_seconds": round(seconds, 3),
                    "average_worker_seconds_per_turn": round(seconds / repetitions, 3),
                    "batches": len(group),
                })
        with timing_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=list(timing_rows[0]), lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(timing_rows)

    java_version = subprocess.run(
        ["java", "--version"], text=True, capture_output=True, check=True
    ).stdout.splitlines()[0]
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
        text=True, capture_output=True, check=True,
    ).stdout.strip()
    environment_path = results / "environment.json"
    previous_runs: list[dict[str, object]] = []
    if (args.append or args.metadata_only) and environment_path.is_file():
        previous_runs = json.loads(environment_path.read_text(encoding="utf-8")).get("runs", [])
    run_record = {
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": round(time.time() - started_at, 3),
        "budgets": budgets,
        "positions": [item["position_id"] for item in selected_positions],
        "repetitions": repetitions,
        "parallelism": args.parallelism,
        "batch_size": args.batch_size,
        "append": args.append,
        "metadata_only": args.metadata_only,
    }
    environment = {
        "schema_version": 1,
        "config": config_path.relative_to(REPO_ROOT).as_posix(),
        "config_sha256": sha256(config_path),
        "positions": positions_path.relative_to(REPO_ROOT).as_posix(),
        "positions_sha256": sha256(positions_path),
        "runner": runner.relative_to(REPO_ROOT).as_posix(),
        "runner_sha256": sha256(runner),
        "run_script_sha256": sha256(SCRIPT),
        "analysis_script_sha256": sha256(analyzer),
        "game": config["game"], "game_sha256": sha256(game),
        "git_commit": commit, "ludii_version": config["ludii_version"],
        "ludii_jar_sha256": sha256(jar), "java": java_version,
        "python": platform.python_version(), "os": platform.platform(),
        "machine": platform.machine(), "runs": previous_runs + [run_record],
    }
    environment_path.write_text(json.dumps(environment, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
