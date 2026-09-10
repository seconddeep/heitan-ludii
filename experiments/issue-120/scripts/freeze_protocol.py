#!/usr/bin/env python3
"""Freeze Issue 120 protocol and the minimal historical comparison inputs."""

from __future__ import annotations

import argparse
import hashlib
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
        "scripts/lock_production_head.py",
        "scripts/Heitan7x7CorrectedExperiment.java", "scripts/Heitan7x7CorrectedReplay.java",
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
    for key, budget, expected in (
        ("issue_108_manifest", 30000, 100),
        ("issue_112_manifest", 30000, 100),
        ("issue_118_manifest", 10000, 30),
    ):
        manifest = protocol.load_json(protocol.REPO_ROOT / declared[key])
        selected = [row for row in manifest["tasks"].values() if row["state"] == "completed" and int(row["iteration_limit"]) == budget]
        if len(selected) != expected:
            raise ValueError(f"{key} must expose {expected} completed corrected-rule UCT {budget} games")
        for row in selected:
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
    starts = [match.start() for match in re.finditer(re.escape('(item "7x7"'), text)]
    start = starts[0] if len(starts) == 1 else -1
    end = text.find('(item "8x8"', start)
    if start < 0 or end < 0:
        raise ValueError("cannot isolate the Board/7x7 option in Heitan.lud")
    values = [int(value) for value in re.findall(r"<\s*(\d+)\s*>", text[start:end])]
    if values != [72, 144, 73, 3650]:
        raise ValueError(f"source-locked Board/7x7 positional values differ from [72, 144, 73, 3650]: {values}")
    board = config["board"]
    if values[2] != int(board["advantage_weight"]) or values[3] != int(board["secured_weight"]):
        raise ValueError("config scoring weights differ from source-locked Heitan.lud")
    scoring_start = text.find('(define "ScoringPiecesOnObjectives"')
    scoring_end = text.find('(define "ObjectiveScore"', scoring_start)
    scoring = text[scoring_start:scoring_end]
    required = ('(count Stack Vertex to:(sites "Objectives")', '(= #1 (who Vertex at:(to) level:(level)))', '(= ("PointState" (to)) #1)')
    if scoring_start < 0 or scoring_end < 0 or not all(fragment in scoring for fragment in required):
        raise ValueError("corrected Objective-piece semantics are absent or differ")
    return {
        "source": config["game"],
        "source_sha256": protocol.sha256(path),
        "board_option": config["board_option"],
        "pieces_per_player": values[0],
        "total_placements": values[1],
        "advantage_weight": values[2],
        "secured_weight": values[3],
        "supply_points": int(board["supply_points"]),
        "objectives": int(board["objectives"]),
        "sites": int(board["sites"]),
        "heitan_turns": int(board["heitan_turns"]),
        "corrected_objective_piece_semantics": "own Pieces on own-Advantage Objectives only",
        "scoring_source_sha256": hashlib.sha256(scoring.encode("utf-8")).hexdigest(),
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
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--heap", default="8g")
    parser.add_argument("--timeout-seconds", type=int, default=28800)
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
    if args.workers != 1 or args.max_attempts < 1 or args.timeout_seconds <= 0:
        parser.error("worker/attempt counts must be positive and timeout nonnegative")
    comparison = comparison_sources(config)
    scoring_gate = game_definition_gate(config)
    config["operational_parameters"].update(status="frozen", worker_count=args.workers, jvm_max_heap=args.heap, timeout_seconds_per_game=args.timeout_seconds, max_attempts=args.max_attempts)
    config["protocol_status"] = "locked"
    config["protocol_locked_at_utc"] = protocol.utc_now()
    protocol.validate_config(config)
    protocol.atomic_write_json(protocol.CONFIG_PATH, config)
    source_lock = {
        "schema_version": 1,
        "locked_before_production": True,
        "outcomes_inspected_during_lock": False,
        "purpose": "frozen Issue 118 7x7 UCT 10k comparison evidence and corrected-rule Issue 108 3x3 / Issue 112 4x4 UCT 30k context used by Issue 120",
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
        "primary_budgets": config["primary_budgets"], "fixed_tasks": 30,
        "seed_generation_rule": config["production"]["seed_generation_rule"],
        "analysis": config["analysis"], "corrected_objective_piece_semantics": config["corrected_objective_piece_semantics"],
        "terminal_diagnostics": config["terminal_diagnostics"], "trial_normalization": config["trial_normalization"],
        "operational_parameters": config["operational_parameters"], "pilot_operational_evidence": evidence,
        "hashed_executable_sources": [source_entry(path) for path in sources],
        "production_head_lock_policy": "after committing the frozen implementation, verify a clean worktree and explicitly record that existing commit with lock_production_head.py before production; every start/resume must match it",
        "environment": {"java": java_version, "python": platform.python_version(), "os": platform.system(), "architecture": platform.machine(), "tmux_available": True, "caffeinate_available": True},
        "rerun_command_templates": [
            "python3 experiments/issue-120/scripts/lock_production_head.py",
            "tmux new-session -d -s heitan-120-30k \"cd '$REPO_ROOT' && caffeinate -i env HEITAN120_CAFFEINATE=1 HEITAN120_RUNNER_ID='$HEITAN120_RUNNER_ID' LUDII_JAR='$LUDII_JAR' python3 experiments/issue-120/scripts/run_experiments.py production\"",
            "python3 experiments/issue-120/scripts/validate_trials.py --namespace production --budget 30000",
            "python3 experiments/issue-120/scripts/validate_trials.py --namespace production --full-scoring",
            "python3 experiments/issue-120/scripts/finalize_production.py",
            "python3 experiments/issue-120/scripts/run_analysis.py --verify-deterministic"
        ],
    }
    protocol.atomic_write_json(protocol.LOCK_PATH, lock)
    print(f"locked Issue 120 protocol: {lock['config_sha256']}")


if __name__ == "__main__":
    main()
