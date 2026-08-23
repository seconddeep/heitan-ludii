#!/usr/bin/env python3
"""Freeze the existing source samples before Issue #83 aggregation."""

from __future__ import annotations

import math
from pathlib import Path
import platform
import sys
import time

import common


FOUNDATIONAL = [
    "experiments/issue-32/config.json",
    "experiments/issue-47/config.json",
    "experiments/issue-47/protocol-lock.json",
    "experiments/issue-47/results/production/finalization.json",
    "experiments/issue-47/results/production/manifest.json",
    "experiments/issue-47/results/final/analysis.json",
    "experiments/issue-47/results/final/balance-by-depth.csv",
    "experiments/issue-82/config.json",
    "experiments/issue-82/protocol-lock.json",
    "experiments/issue-82/results/production/finalization.json",
    "experiments/issue-82/results/production/manifest.json",
    "experiments/issue-82/results/final/analysis.json",
    "experiments/issue-82/results/final/balance-by-depth.csv",
]


def pin(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise ValueError(f"source file is missing: {path}")
    return {
        "path": path.relative_to(common.REPO_ROOT).as_posix(),
        "sha256": common.sha256(path),
        "bytes": path.stat().st_size,
    }


def turn_path(board: str, validation: Path) -> Path:
    name = "turn-states.csv" if board == "3x3" else "objective-turn-states.csv"
    return validation.parent / "validation-raw" / name


def production_games(board: str, issue: int) -> list[dict[str, object]]:
    root = common.REPO_ROOT / f"experiments/issue-{issue}"
    manifest = common.load_json(root / "results/production/manifest.json")
    finalization = common.load_json(root / "results/production/finalization.json")
    excluded = {
        row["task_id"]
        for row in finalization.get("excluded_tasks", finalization.get("failed_tasks", []))
    }
    games = []
    for task_id, entry in sorted(manifest["tasks"].items()):
        if task_id in excluded:
            if entry["state"] != "failed":
                raise ValueError(f"excluded task is not failed: {task_id}")
            continue
        if entry["state"] != "completed":
            raise ValueError(f"non-terminal source task: {task_id}")
        artifacts = entry["artifacts"]
        validation = common.REPO_ROOT / artifacts["validation"]
        record = {
            "board": board,
            "budget": int(entry["iteration_limit"]),
            "game_index": int(entry["game_index"]),
            "key": task_id,
            "result": pin(common.REPO_ROOT / artifacts["result"]),
            "trial": pin(common.REPO_ROOT / artifacts["trial"]),
            "validation": pin(validation),
            "turn_states": pin(turn_path(board, validation)),
        }
        expected_trial = artifacts.get("trial_sha256")
        if expected_trial and record["trial"]["sha256"] != expected_trial:
            raise ValueError(f"manifest trial hash mismatch: {task_id}")
        games.append(record)
    return games


def baseline_games() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    raw = common.REPO_ROOT / "experiments/issue-32/results/raw"
    turn_states = common.REPO_ROOT / "experiments/issue-37/results/raw/objective-turn-states.csv"
    turn_pin = pin(turn_states)
    games = []
    batches = []
    seen: set[int] = set()
    for path in sorted(raw.glob("uct-10000-self-play-batch-*.csv")):
        batches.append(pin(path))
        for row in common.read_csv(path):
            if row["experiment_id"] != "uct-10000-self-play":
                continue
            index = int(row["game_index"])
            if index in seen:
                raise ValueError(f"duplicate 4x4 10k game: {index}")
            seen.add(index)
            trial = common.REPO_ROOT / row["trial_file"]
            games.append({
                "board": "4x4", "budget": 10000, "game_index": index,
                "key": f"issue-32-uct-10000-g{index:04d}",
                "result_batch": pin(path), "trial": pin(trial),
                "turn_states": turn_pin,
            })
    if len(games) != 100:
        raise ValueError(f"expected 100 4x4 10k games, found {len(games)}")
    return sorted(games, key=lambda row: int(row["game_index"])), batches


def validate_config(config: dict) -> None:
    if config["analysis"]["practical_equivalence_margin"] != 0.05:
        raise ValueError("practical-equivalence margin must remain 0.05")
    expected = ["unresolved-invalid", "non-monotonic", "consistent", "search-dependent", "unresolved"]
    if config["classification"]["internal_precedence"] != expected:
        raise ValueError("classification precedence changed")
    for board, spec in config["boards"].items():
        for checkpoint in config["secondary"]["checkpoints"]:
            expected_turn = {("3x3", 0.75): 14, ("3x3", 0.9): 17, ("4x4", 0.75): 18, ("4x4", 0.9): 22}[(board, checkpoint)]
            if math.ceil(int(spec["total_turns"]) * checkpoint) != expected_turn:
                raise ValueError("checkpoint mapping changed")


def main() -> None:
    if common.PROTOCOL_LOCK.exists() or common.SOURCE_LOCK.exists():
        raise ValueError("Issue #83 inputs are already frozen")
    config = common.load_json(common.CONFIG_PATH)
    validate_config(config)
    baseline, batches = baseline_games()
    games = production_games("3x3", 82) + baseline + production_games("4x4", 47)
    observed: dict[str, dict[str, int]] = {"3x3": {}, "4x4": {}}
    for board in observed:
        for budget in config["primary_budgets"]:
            observed[board][str(budget)] = sum(
                row["board"] == board and row["budget"] == budget for row in games
            )
    if observed != config["source_samples"]:
        raise ValueError(f"source counts differ from frozen config: {observed}")
    source_lock = {
        "schema_version": 1,
        "source_issues": [32, 47, 82],
        "foundational_files": [pin(common.REPO_ROOT / path) for path in FOUNDATIONAL],
        "baseline_batch_files": batches,
        "games": games,
        "observed_games": observed,
        "excluded_4x4_100k": [
            {"game_index": 61, "seed": 571000060},
            {"game_index": 78, "seed": 571000077},
            {"game_index": 93, "seed": 571000092},
        ],
        "new_self_play_included": False,
    }
    common.atomic_json(common.SOURCE_LOCK, source_lock)
    protocol = {
        "schema_version": 1,
        "frozen_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "config_sha256": common.sha256(common.CONFIG_PATH),
        "source_lock_sha256": common.sha256(common.SOURCE_LOCK),
        "analysis_script_hashes": {
            path.name: common.sha256(path)
            for path in sorted(common.SCRIPT.parent.glob("*.py"))
        },
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }
    common.atomic_json(common.PROTOCOL_LOCK, protocol)
    print(f"froze {len(games)} source games")


if __name__ == "__main__":
    main()
