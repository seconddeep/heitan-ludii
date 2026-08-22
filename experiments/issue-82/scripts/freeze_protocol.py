#!/usr/bin/env python3
"""Freeze Issue #82 operational settings and optional-budget decision."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

import protocol


def hashed_sources() -> list[dict[str, str]]:
    paths = [
        protocol.ISSUE_ROOT / "README.md", protocol.CONFIG_PATH, protocol.SCRIPT,
        Path(__file__).resolve(), protocol.SCRIPT.parent / "run_experiments.py",
        protocol.SCRIPT.parent / "finalize_production.py", protocol.SCRIPT.parent / "run_analysis.py",
        protocol.REPO_ROOT / "experiments/issue-62/scripts/Heitan3x3Experiment.java",
        protocol.REPO_ROOT / "experiments/issue-62/scripts/HeitanScaleReplay.java",
    ]
    return [
        {"path": path.relative_to(protocol.REPO_ROOT).as_posix(), "sha256": protocol.sha256(path)}
        for path in sorted(path.resolve() for path in paths if path.is_file())
    ]


def optional_smoke_decision(config: dict, workers: int) -> dict:
    manifest_path = protocol.manifest_path("pilot")
    if not manifest_path.is_file():
        raise ValueError("pilot manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = [row for row in manifest["tasks"].values() if int(row["iteration_limit"]) == 300000]
    criteria = config["optional_budget"]["smoke"]["criteria"]
    expected = int(config["optional_budget"]["smoke"]["games"])
    if len(rows) != expected or any(row["state"] != "completed" for row in rows):
        raise ValueError("optional 300k smoke did not complete and validate every preregistered game")
    elapsed = [float(row["elapsed_seconds"]) for row in rows]
    rss = [row.get("peak_rss_bytes") for row in rows]
    if any(value is None for value in rss):
        raise ValueError("optional 300k smoke lacks peak-memory observations")
    projected = max(elapsed) * int(config["optional_budget"]["target_games"]) / workers
    checks = {
        "all_games_complete_and_replayable": True,
        "maximum_elapsed_seconds_per_game": max(elapsed) <= float(criteria["maximum_elapsed_seconds_per_game"]),
        "maximum_peak_rss_bytes": max(int(value) for value in rss) <= int(criteria["maximum_peak_rss_bytes"]),
        "maximum_projected_wall_seconds_for_target": projected <= float(criteria["maximum_projected_wall_seconds_for_target"]),
    }
    if not all(checks.values()):
        raise ValueError(f"optional 300k smoke failed preregistered operational criteria: {checks}")
    return {
        "games": len(rows), "maximum_elapsed_seconds": max(elapsed),
        "maximum_peak_rss_bytes": max(int(value) for value in rss),
        "projected_wall_seconds": projected, "criteria_checks": checks,
        "outcomes_inspected": False, "manifest_sha256": protocol.sha256(manifest_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ludii-jar", default=os.environ.get("LUDII_JAR", ""))
    parser.add_argument("--workers-10k", type=int, required=True)
    parser.add_argument("--workers-30k", type=int, required=True)
    parser.add_argument("--workers-100k", type=int, required=True)
    parser.add_argument("--workers-300k", type=int, default=1)
    parser.add_argument("--heap-10k", required=True)
    parser.add_argument("--heap-30k", required=True)
    parser.add_argument("--heap-100k", required=True)
    parser.add_argument("--heap-300k", default="10g")
    parser.add_argument("--timeout-seconds", type=int, default=0)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--optional-300k", choices=("include", "exclude"), required=True)
    args = parser.parse_args()
    workers = {"10000": args.workers_10k, "30000": args.workers_30k, "100000": args.workers_100k, "300000": args.workers_300k}
    heaps = {"10000": args.heap_10k, "30000": args.heap_30k, "100000": args.heap_100k, "300000": args.heap_300k}
    if any(value < 1 for value in workers.values()):
        parser.error("worker counts must be positive")
    if args.timeout_seconds < 0 or args.max_attempts < 1:
        parser.error("timeout must be nonnegative and max attempts positive")
    jar = Path(args.ludii_jar).expanduser().resolve()
    if not jar.is_file():
        parser.error("pass --ludii-jar or set LUDII_JAR to an existing file")
    if not shutil.which("tmux") or not shutil.which("caffeinate"):
        raise ValueError("tmux and caffeinate are required before locking production")
    config = protocol.load_config()
    if config["protocol_status"] == "locked" or protocol.LOCK_PATH.exists():
        raise ValueError("protocol is already locked")
    optional_evidence = None
    if args.optional_300k == "include":
        optional_evidence = optional_smoke_decision(config, args.workers_300k)
        config["optional_budget"]["adoption_status"] = "included"
    else:
        config["optional_budget"]["adoption_status"] = "excluded"
    config["optional_budget"]["decision_basis"] = "preregistered operational criteria only"
    config["optional_budget"]["smoke_evidence"] = optional_evidence
    config["operational_parameters"].update({
        "status": "frozen", "worker_count_by_budget": workers,
        "jvm_max_heap_by_budget": heaps, "timeout_seconds_per_game": args.timeout_seconds,
        "max_attempts": args.max_attempts,
    })
    config["protocol_status"] = "locked"
    config["protocol_frozen_at_utc"] = protocol.utc_now()
    protocol.validate_all_namespaces(config)
    protocol.atomic_write_json(protocol.CONFIG_PATH, config)
    version = subprocess.run(["java", "--version"], text=True, capture_output=True, check=True)
    java_version = (version.stdout or version.stderr).splitlines()[0]
    lock = {
        "schema_version": 1, "experiment_version": config["experiment_version"],
        "protocol_frozen_at_utc": config["protocol_frozen_at_utc"],
        "config": protocol.CONFIG_PATH.relative_to(protocol.REPO_ROOT).as_posix(),
        "config_sha256": protocol.sha256(protocol.CONFIG_PATH),
        "game": config["game"], "game_sha256": protocol.sha256(protocol.REPO_ROOT / config["game"]),
        "ludii_version": config["ludii_version"], "ludii_jar_sha256": protocol.sha256(jar),
        "primary_budgets": config["primary_budgets"],
        "primary_target_games": {str(spec["iteration_limit"]): spec["target_games"] for spec in config["production"]["primary_tasks"]},
        "optional_budget": {"iteration_limit": 300000, "adoption_status": config["optional_budget"]["adoption_status"], "smoke_evidence": optional_evidence},
        "operational_parameters": config["operational_parameters"],
        "seed_generation_rule": config["production"]["seed_generation_rule"],
        "stability_classification": config["stability_classification"],
        "hashed_protocol_and_analysis_sources": hashed_sources(),
        "persistent_execution": {"tmux": shutil.which("tmux"), "caffeinate": shutil.which("caffeinate")},
        "environment": {"java": java_version, "python": platform.python_version(), "os": platform.platform(), "machine": platform.machine()},
    }
    protocol.atomic_write_json(protocol.LOCK_PATH, lock)
    print(f"locked Issue #82 protocol: {lock['config_sha256']}")


if __name__ == "__main__":
    main()
