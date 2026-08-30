#!/usr/bin/env python3
"""Freeze Issue #112 protocol and the minimal historical comparison inputs."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess

import protocol


def source_entry(path: Path) -> dict[str, object]:
    resolved = path.resolve()
    return {"path": resolved.relative_to(protocol.REPO_ROOT).as_posix(), "bytes": resolved.stat().st_size, "sha256": protocol.sha256(resolved)}


def executable_sources() -> list[Path]:
    names = [
        "README.md", "config.json", "scripts/protocol.py", "scripts/freeze_protocol.py",
        "scripts/run_experiments.py", "scripts/validate_trials.py", "scripts/finalize_production.py",
        "scripts/run_analysis.py", "scripts/status.py", "scripts/public_safety_audit.py",
        "scripts/Heitan4x4CorrectedExperiment.java", "scripts/Heitan4x4CorrectedReplay.java",
    ]
    return [protocol.ISSUE_ROOT / name for name in names]


def referenced_paths(value: object) -> list[Path]:
    paths: list[Path] = []
    if isinstance(value, dict):
        if {"path", "bytes", "sha256"} <= set(value):
            path = protocol.REPO_ROOT / str(value["path"])
            if not path.is_file() or path.stat().st_size != int(value["bytes"]) or protocol.sha256(path) != value["sha256"]:
                raise ValueError(f"nested source-lock entry differs: {value['path']}")
            paths.append(path)
        else:
            for nested in value.values():
                paths.extend(referenced_paths(nested))
    elif isinstance(value, list):
        for nested in value:
            paths.extend(referenced_paths(nested))
    return paths


def comparison_sources(config: dict) -> list[Path]:
    declared = config["historical_sources"]
    paths = [protocol.REPO_ROOT / value for value in declared.values()]
    issue_83 = protocol.load_json(protocol.REPO_ROOT / declared["issue_83_source_lock"])
    paths.extend(referenced_paths(issue_83.get("baseline_batch_files", [])))
    paths.extend(referenced_paths(issue_83.get("foundational_files", [])))
    paths.extend(referenced_paths([row for row in issue_83["games"] if row["board"] == "4x4"]))
    manifest_108 = protocol.load_json(protocol.REPO_ROOT / declared["issue_108_manifest"])
    for row in manifest_108["tasks"].values():
        if row["state"] != "completed" or int(row["iteration_limit"]) not in config["primary_budgets"]:
            continue
        for name in ("trial", "result", "validation"):
            paths.append(protocol.REPO_ROOT / row["artifacts"][name])
    unique = sorted({path.resolve() for path in paths})
    missing = [path for path in unique if not path.is_file()]
    if missing:
        raise ValueError(f"historical comparison inputs are missing: {missing[:3]}")
    return unique


def game_definition_gate(config: dict) -> dict[str, object]:
    path = protocol.REPO_ROOT / config["game"]
    text = path.read_text(encoding="utf-8")
    start = text.find('(item "4x4"')
    end = text.find('(item "5x5"', start)
    if start < 0 or end < 0:
        raise ValueError("cannot isolate the Board/4x4 option in Heitan.lud")
    values = [int(value) for value in re.findall(r"<\s*(\d+)\s*>", text[start:end])]
    if values != [36, 72, 37, 629]:
        raise ValueError(f"source-locked Board/4x4 positional values differ from [36, 72, 37, 629]: {values}")
    board = config["board"]
    if values[2] != int(board["advantage_weight"]) or values[3] != int(board["secured_weight"]):
        raise ValueError("config scoring weights differ from source-locked Heitan.lud")
    return {
        "source": config["game"],
        "source_sha256": protocol.sha256(path),
        "board_option": config["board_option"],
        "pieces_per_player": values[0],
        "total_placements": values[1],
        "advantage_weight": values[2],
        "secured_weight": values[3],
        "status": "passed",
    }


def pilot_gate(config: dict) -> dict:
    path = protocol.manifest_path("pilot")
    if not path.is_file():
        raise ValueError("pilot manifest is missing")
    manifest = protocol.load_json(path)
    tasks = protocol.tasks_from_config(config, "pilot")
    rows = [manifest["tasks"][task.task_id] for task in tasks]
    if any(row["state"] != "completed" or not (row.get("validation") or {}).get("validated") for row in rows):
        raise ValueError("every preregistered pilot task must complete and validate")
    return {
        "games": len(rows), "manifest_sha256": protocol.sha256(path),
        "maximum_elapsed_seconds": max(float(row["elapsed_seconds"]) for row in rows),
        "peak_memory_observed": all(row["peak_rss_bytes"] is not None for row in rows),
        "maximum_peak_rss_bytes": max((int(row["peak_rss_bytes"]) for row in rows if row["peak_rss_bytes"] is not None), default=None),
        "outcomes_inspected": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ludii-jar", default=os.environ.get("LUDII_JAR", ""))
    parser.add_argument("--workers-10k", type=int, default=2)
    parser.add_argument("--workers-30k", type=int, default=2)
    parser.add_argument("--workers-100k", type=int, default=1)
    parser.add_argument("--heap-10k", default="4g")
    parser.add_argument("--heap-30k", default="4g")
    parser.add_argument("--heap-100k", default="8g")
    parser.add_argument("--timeout-seconds", type=int, default=0)
    parser.add_argument("--max-attempts", type=int, default=3)
    args = parser.parse_args()
    jar = Path(args.ludii_jar).expanduser().resolve()
    if not jar.is_file():
        parser.error("pass --ludii-jar or set LUDII_JAR to an existing file")
    if not shutil.which("tmux") or not shutil.which("caffeinate"):
        raise ValueError("tmux and caffeinate are required")
    config = protocol.load_config()
    if config["protocol_status"] == "locked" or protocol.LOCK_PATH.exists() or protocol.SOURCE_LOCK_PATH.exists():
        raise ValueError("protocol is already locked")
    evidence = pilot_gate(config)
    workers = {"10000": args.workers_10k, "30000": args.workers_30k, "100000": args.workers_100k}
    heaps = {"10000": args.heap_10k, "30000": args.heap_30k, "100000": args.heap_100k}
    if any(value < 1 for value in workers.values()) or args.max_attempts < 1 or args.timeout_seconds < 0:
        parser.error("worker/attempt counts must be positive and timeout nonnegative")
    comparison = comparison_sources(config)
    scoring_gate = game_definition_gate(config)
    config["operational_parameters"].update(status="frozen", worker_count_by_budget=workers, jvm_max_heap_by_budget=heaps, timeout_seconds_per_game=args.timeout_seconds, max_attempts=args.max_attempts)
    config["protocol_status"] = "locked"
    config["protocol_locked_at_utc"] = protocol.utc_now()
    protocol.validate_config(config)
    protocol.atomic_write_json(protocol.CONFIG_PATH, config)
    source_lock = {
        "schema_version": 1,
        "locked_before_production": True,
        "outcomes_inspected_during_lock": False,
        "purpose": "#47/#83 historical 4x4, #105 terminal-rescore, and #108 corrected-3x3 artifacts and per-game evidence used by Issue #112",
        "files": [source_entry(path) for path in comparison],
    }
    protocol.atomic_write_json(protocol.SOURCE_LOCK_PATH, source_lock)
    sources = executable_sources()
    missing = [path for path in sources if not path.is_file()]
    if missing:
        raise ValueError(f"required executable sources are missing: {missing}")
    java = subprocess.run(["java", "--version"], text=True, capture_output=True, check=True)
    java_version = (java.stdout or java.stderr).splitlines()[0]
    game_commit = subprocess.run(["git", "log", "-1", "--format=%H", "--", config["game"]], cwd=protocol.REPO_ROOT, text=True, capture_output=True, check=True).stdout.strip()
    lock = {
        "schema_version": 1,
        "experiment_version": config["experiment_version"],
        "protocol_locked_at_utc": config["protocol_locked_at_utc"],
        "config": protocol.CONFIG_PATH.relative_to(protocol.REPO_ROOT).as_posix(),
        "config_sha256": protocol.sha256(protocol.CONFIG_PATH),
        "source_lock": protocol.SOURCE_LOCK_PATH.relative_to(protocol.REPO_ROOT).as_posix(),
        "source_lock_sha256": protocol.sha256(protocol.SOURCE_LOCK_PATH),
        "game": config["game"], "game_sha256": protocol.sha256(protocol.REPO_ROOT / config["game"]), "game_definition_commit": game_commit,
        "game_definition_gate": scoring_gate,
        "ludii_version": config["ludii_version"], "ludii_jar_sha256": protocol.sha256(jar),
        "primary_budgets": config["primary_budgets"], "fixed_tasks_per_budget": 100,
        "seed_generation_rule": config["production"]["seed_generation_rule"],
        "analysis": config["analysis"], "stability_classification": config["stability_classification"],
        "supply_diagnostics": config["supply_diagnostics"], "trial_normalization": config["trial_normalization"],
        "operational_parameters": config["operational_parameters"], "pilot_operational_evidence": evidence,
        "hashed_executable_sources": [source_entry(path) for path in sources],
        "production_head_lock_policy": "on first production start after the locked implementation is committed, record exact clean HEAD in results/production/production-head-lock.json; every start/resume must match it",
        "environment": {"java": java_version, "python": platform.python_version(), "os": platform.system(), "architecture": platform.machine(), "tmux_available": True, "caffeinate_available": True},
        "rerun_command_templates": [
            "tmux new-session -d -s heitan-112-10k \"cd '$REPO_ROOT' && caffeinate -i env HEITAN112_CAFFEINATE=1 HEITAN112_RUNNER_ID='$HEITAN112_RUNNER_ID' LUDII_JAR='$LUDII_JAR' python3 experiments/issue-112/scripts/run_experiments.py production --budget 10000\"",
            "python3 experiments/issue-112/scripts/validate_trials.py --namespace production --budget 10000",
            "python3 experiments/issue-112/scripts/validate_trials.py --namespace production --full-scoring",
            "python3 experiments/issue-112/scripts/finalize_production.py",
            "python3 experiments/issue-112/scripts/run_analysis.py --verify-deterministic"
        ],
    }
    protocol.atomic_write_json(protocol.LOCK_PATH, lock)
    print(f"locked Issue #112 protocol: {lock['config_sha256']}")


if __name__ == "__main__":
    main()
