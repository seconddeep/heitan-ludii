#!/usr/bin/env python3
"""Finalize permitted operational choices and lock Issue #47 production."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess

import protocol


LOCK_PATH = protocol.ISSUE_ROOT / "protocol-lock.json"


def hashed_sources(config: dict) -> list[dict[str, str]]:
    paths = [
        protocol.ISSUE_ROOT / "README.md",
        protocol.SCRIPT,
        Path(__file__).resolve(),
        protocol.SCRIPT.parent / "run_experiments.py",
        protocol.SCRIPT.parent / "validate_trials.py",
        protocol.REPO_ROOT / "experiments/issue-11/scripts/HeitanExperiment.java",
        protocol.REPO_ROOT / "experiments/issue-37/scripts/HeitanSupplyReplay.java",
    ]
    paths.extend(protocol.REPO_ROOT / value for value in config["frozen_analysis_sources"].values())
    optional = [
        protocol.SCRIPT.parent / "run_analysis.py",
        protocol.SCRIPT.parent / "test_protocol.py",
    ]
    paths.extend(path for path in optional if path.is_file())
    unique = sorted(set(path.resolve() for path in paths))
    return [
        {"path": path.relative_to(protocol.REPO_ROOT).as_posix(), "sha256": protocol.sha256(path)}
        for path in unique
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ludii-jar", default=os.environ.get("LUDII_JAR", ""))
    parser.add_argument("--games-100k", type=int, required=True)
    parser.add_argument("--workers-30k", type=int, required=True)
    parser.add_argument("--workers-100k", type=int, required=True)
    parser.add_argument("--heap-30k", default="4g")
    parser.add_argument("--heap-100k", default="8g")
    parser.add_argument("--timeout-seconds", type=int, default=0)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--reduction-reason")
    args = parser.parse_args()
    if args.games_100k < 25:
        parser.error("--games-100k must be at least 25 under the frozen evidence rule")
    if args.workers_30k < 1 or args.workers_100k < 1:
        parser.error("worker counts must be positive")
    if args.timeout_seconds < 0 or args.max_attempts < 1:
        parser.error("timeout must be nonnegative and max attempts positive")
    if args.games_100k < 100 and not args.reduction_reason:
        parser.error("a reduced 100k sample requires --reduction-reason")
    jar = Path(args.ludii_jar).expanduser().resolve()
    if not jar.is_file():
        parser.error("pass --ludii-jar or set LUDII_JAR to an existing file")
    pilot_path = protocol.manifest_path("pilot")
    if not pilot_path.is_file():
        raise ValueError("excluded pilot has not run")
    pilot = json.loads(pilot_path.read_text(encoding="utf-8"))
    if not pilot["tasks"] or any(row["state"] != "completed" for row in pilot["tasks"].values()):
        raise ValueError("every excluded pilot task must validate before protocol freeze")

    config = protocol.load_config()
    if config["protocol_status"] == "locked" or LOCK_PATH.exists():
        raise ValueError("protocol is already locked")
    for spec in config["production"]["tasks"]:
        if int(spec["iteration_limit"]) == 100000:
            spec["target_games"] = args.games_100k
            spec["count_status"] = "frozen_after_excluded_pilot"
            if args.games_100k < 100:
                spec["reduction_reason"] = args.reduction_reason
        elif int(spec["iteration_limit"]) == 30000:
            if int(spec["target_games"]) != 100:
                raise ValueError("the independently frozen 30k count must remain 100")
    config["operational_parameters"]["worker_count_by_budget"] = {
        "30000": args.workers_30k, "100000": args.workers_100k,
    }
    config["operational_parameters"]["jvm_max_heap_by_budget"] = {
        "30000": args.heap_30k, "100000": args.heap_100k,
    }
    config["operational_parameters"]["timeout_seconds_per_game"] = args.timeout_seconds
    config["operational_parameters"]["max_attempts"] = args.max_attempts
    config["operational_parameters"]["status"] = "frozen"
    config["protocol_status"] = "locked"
    config["protocol_frozen_at_utc"] = protocol.utc_now()
    protocol.validate_all_namespaces(config)
    protocol.atomic_write_json(protocol.CONFIG_PATH, config)

    java = subprocess.run(["java", "--version"], text=True, capture_output=True, check=True).stdout.splitlines()[0]
    game = protocol.REPO_ROOT / config["game"]
    lock = {
        "schema_version": 1,
        "experiment_version": config["experiment_version"],
        "protocol_frozen_at_utc": config["protocol_frozen_at_utc"],
        "config": protocol.CONFIG_PATH.relative_to(protocol.REPO_ROOT).as_posix(),
        "config_sha256": protocol.sha256(protocol.CONFIG_PATH),
        "game": config["game"],
        "game_sha256": protocol.sha256(game),
        "ludii_version": config["ludii_version"],
        "ludii_jar_sha256": protocol.sha256(jar),
        "production_game_counts": {str(spec["iteration_limit"]): spec["target_games"] for spec in config["production"]["tasks"]},
        "search_budgets": [30000, 100000],
        "seed_generation_rule": config["production"]["seed_generation_rule"],
        "game_index_generation_rule": config["production"]["game_index_generation_rule"],
        "worker_count_by_budget": config["operational_parameters"]["worker_count_by_budget"],
        "jvm_max_heap_by_budget": config["operational_parameters"]["jvm_max_heap_by_budget"],
        "timeout_seconds_per_game": args.timeout_seconds,
        "max_attempts": args.max_attempts,
        "retry_states": config["operational_parameters"]["retry_states"],
        "pilot_manifest": pilot_path.relative_to(protocol.REPO_ROOT).as_posix(),
        "pilot_manifest_sha256": protocol.sha256(pilot_path),
        "pilot_excluded_from_analysis": True,
        "hashed_protocol_and_analysis_sources": hashed_sources(config),
        "environment": {
            "java": java,
            "python": platform.python_version(),
            "os": platform.platform(),
            "machine": platform.machine(),
        },
    }
    protocol.atomic_write_json(LOCK_PATH, lock)
    print(f"locked Issue #47 protocol: {lock['config_sha256']}")


if __name__ == "__main__":
    main()
