#!/usr/bin/env python3
"""Run Issue #32 iteration-limited UCT self-play experiments."""

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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_batch(task: dict[str, object]) -> dict[str, object]:
    started = time.monotonic()
    command = [
        "java", "-cp", str(task["jar"]), str(task["runner"]),
        str(task["game"]), str(task["id"]), "UCT", "UCT",
        str(task["games"]), str(task["seed"]), str(task["iterations"]),
        str(task["max_seconds"]), str(task["raw"]), str(task["trials"]),
        str(task["offset"]),
    ]
    completed = subprocess.run(command, cwd=REPO_ROOT, check=False)
    elapsed = time.monotonic() - started
    if completed.returncode:
        raise RuntimeError(
            f"batch failed: {task['id']} offset={task['offset']} "
            f"exit={completed.returncode}"
        )
    return {
        "experiment_id": task["id"],
        "games": task["games"],
        "iteration_limit": task["iterations"],
        "elapsed_seconds": elapsed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ludii-jar", default=os.environ.get("LUDII_JAR", ""))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--parallelism", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--games-override", type=int)
    parser.add_argument("--metadata-only", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.parallelism <= 64:
        parser.error("--parallelism must be between 1 and 64")
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    if args.games_override is not None and args.games_override < 1:
        parser.error("--games-override must be positive")

    jar = Path(args.ludii_jar).expanduser().resolve()
    config_path = args.config.resolve()
    if not jar.is_file():
        parser.error("pass --ludii-jar or set LUDII_JAR to an existing file")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config["ludii_version"] != "1.3.14":
        raise ValueError("this workflow is validated against Ludii 1.3.14")

    game = REPO_ROOT / config["game"]
    runner = REPO_ROOT / "experiments/issue-11/scripts/HeitanExperiment.java"
    analyzer = SCRIPT.parent / "analyze_results.py"
    results = ISSUE_ROOT / "results"
    raw_dir = results / "raw"
    trials_dir = results / "trials"
    raw_dir.mkdir(parents=True, exist_ok=True)
    trials_dir.mkdir(parents=True, exist_ok=True)
    started_at = time.time()

    batch_results: list[dict[str, object]] = []
    effective_counts: dict[str, int] = {}
    if not args.metadata_only:
        for path in raw_dir.glob("*.csv"):
            path.unlink()
        for path in trials_dir.glob("**/*.trl"):
            path.unlink()

        tasks: list[dict[str, object]] = []
        experiment_offset = 0
        for experiment in config["experiments"]:
            if experiment["black_agent"] != "UCT" or experiment["white_agent"] != "UCT":
                raise ValueError(f"{experiment['id']} is not UCT self-play")
            count = args.games_override or int(experiment["games"])
            effective_counts[experiment["id"]] = count
            experiment_trials = trials_dir / experiment["id"]
            experiment_trials.mkdir(parents=True, exist_ok=True)
            batch_size = count if args.parallelism == 1 else args.batch_size
            for offset in range(0, count, batch_size):
                games = min(batch_size, count - offset)
                batch_number = offset // batch_size + 1
                tasks.append({
                    "jar": jar, "runner": runner, "game": game,
                    "id": experiment["id"], "games": games,
                    "seed": int(config["base_seed"]) + experiment_offset + offset,
                    "iterations": int(experiment["iteration_limit"]),
                    "max_seconds": float(experiment["max_seconds_per_move"]),
                    "raw": raw_dir / f"{experiment['id']}-batch-{batch_number:03d}.csv",
                    "trials": experiment_trials, "offset": offset,
                })
            experiment_offset += count

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallelism) as pool:
            futures = [pool.submit(run_batch, task) for task in tasks]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                batch_results.append(result)
                print(
                    f"completed {result['experiment_id']}: {result['games']} games, "
                    f"{result['iteration_limit']} iterations",
                    flush=True,
                )

        with (results / "timings.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "experiment_id", "games", "iteration_limit", "worker_seconds",
                "average_worker_seconds_per_game", "batches",
            ])
            writer.writeheader()
            for experiment in config["experiments"]:
                group = [r for r in batch_results if r["experiment_id"] == experiment["id"]]
                seconds = sum(float(r["elapsed_seconds"]) for r in group)
                count = effective_counts[experiment["id"]]
                writer.writerow({
                    "experiment_id": experiment["id"], "games": count,
                    "iteration_limit": experiment["iteration_limit"],
                    "worker_seconds": round(seconds, 3),
                    "average_worker_seconds_per_game": round(seconds / count, 3),
                    "batches": len(group),
                })

    java_version = subprocess.run(
        ["java", "--version"], text=True, capture_output=True, check=True
    ).stdout.splitlines()[0]
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
        text=True, capture_output=True, check=True,
    ).stdout.strip()
    elapsed_seconds = round(time.time() - started_at, 3)
    if args.metadata_only and (results / "environment.json").is_file():
        previous_environment = json.loads(
            (results / "environment.json").read_text(encoding="utf-8")
        )
        elapsed_seconds = previous_environment.get("elapsed_seconds", elapsed_seconds)
    environment = {
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": elapsed_seconds,
        "config": "experiments/issue-32/config.json",
        "config_sha256": sha256(config_path),
        "runner": "experiments/issue-11/scripts/HeitanExperiment.java",
        "runner_sha256": sha256(runner),
        "run_script_sha256": sha256(SCRIPT),
        "analysis_script_sha256": sha256(analyzer),
        "game": config["game"], "game_sha256": sha256(game),
        "git_commit": commit, "ludii_version": config["ludii_version"],
        "ludii_jar_sha256": sha256(jar), "java": java_version,
        "os": platform.platform(), "machine": platform.machine(),
        "parallelism": args.parallelism, "batch_size": args.batch_size,
        "games_override": args.games_override,
    }
    (results / "environment.json").write_text(
        json.dumps(environment, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
