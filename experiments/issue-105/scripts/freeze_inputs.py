#!/usr/bin/env python3
"""Freeze the minimum 597-game source set for Issue #105."""

from __future__ import annotations

import argparse
from pathlib import Path
import platform
import sys
import time

import common


MINIMUM_SOURCE = common.REPO_ROOT / "experiments/issue-83/source-lock.json"
FOUNDATIONAL = [
    "experiments/issue-32/config.json",
    "experiments/issue-47/config.json",
    "experiments/issue-47/protocol-lock.json",
    "experiments/issue-47/results/production/finalization.json",
    "experiments/issue-47/results/production/manifest.json",
    "experiments/issue-82/config.json",
    "experiments/issue-82/protocol-lock.json",
    "experiments/issue-82/results/production/finalization.json",
    "experiments/issue-82/results/production/manifest.json",
    "experiments/issue-83/config.json",
    "experiments/issue-83/protocol-lock.json",
    "experiments/issue-83/results/final/analysis.json",
    "experiments/issue-83/results/final/balance-by-board-depth.csv",
    "experiments/issue-83/results/final/secondary-scoring.csv",
]
for extension_issue in (11, 30, 32, 56, 58, 60, 62, 73, 77):
    FOUNDATIONAL.extend([
        f"experiments/issue-{extension_issue}.md",
        f"experiments/issue-{extension_issue}/config.json",
        f"experiments/issue-{extension_issue}/results/environment.json",
        f"experiments/issue-{extension_issue}/results/analysis.json",
    ])


def pin(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise ValueError(f"source file is missing: {path}")
    return {
        "path": path.relative_to(common.REPO_ROOT).as_posix(),
        "sha256": common.sha256(path),
        "bytes": path.stat().st_size,
    }


def extension_games(config: dict) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    games: list[dict[str, object]] = []
    batch_pins: dict[str, dict[str, object]] = {}
    seen_trials: set[str] = set()
    for spec in config["extension_sources"]:
        root = common.REPO_ROOT / spec["results_root"]
        allowed = set(spec.get("include_experiments", []))
        issue_games: dict[tuple[str, int], dict[str, object]] = {}
        for path in sorted(root.glob("*.csv")):
            rows = common.read_csv(path)
            if not rows or not {"winner", "final_board", "trial_file"}.issubset(rows[0]):
                continue
            for row in rows:
                if allowed and row["experiment_id"] not in allowed:
                    continue
                key = row["experiment_id"], int(row["game_index"])
                if key in issue_games:
                    raise ValueError(f"duplicate extension game for Issue #{spec['issue']}: {key}")
                trial = common.REPO_ROOT / row["trial_file"]
                trial_pin = pin(trial)
                if trial_pin["sha256"] in seen_trials:
                    raise ValueError(f"extension trial duplicates another selected trial: {trial}")
                seen_trials.add(str(trial_pin["sha256"]))
                batch_pin = batch_pins.setdefault(path.as_posix(), pin(path))
                budget = int(row.get("iteration_limit") or 0)
                issue_games[key] = {
                    "source_issue": int(spec["issue"]), "board": spec["board"],
                    "budget": budget, "game_index": int(row["game_index"]),
                    "key": f"issue-{spec['issue']}-{row['experiment_id']}-g{int(row['game_index']):04d}",
                    "dataset_id": f"issue-{spec['issue']}:{row['experiment_id']}",
                    "experiment_id": row["experiment_id"], "minimum_gate": False,
                    "result_batch": batch_pin, "trial": trial_pin,
                }
        if len(issue_games) != int(spec["expected_games"]):
            raise ValueError(
                f"Issue #{spec['issue']} extension expected {spec['expected_games']} games, found {len(issue_games)}"
            )
        games.extend(issue_games[key] for key in sorted(issue_games))
    return games, list(batch_pins.values())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development-refresh", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if (common.SOURCE_LOCK.exists() or common.PROTOCOL_LOCK.exists()) and not args.development_refresh:
        raise ValueError("Issue #105 inputs are already frozen")
    config = common.load_json(common.CONFIG_PATH)
    source83 = common.load_json(MINIMUM_SOURCE)
    minimum_games = source83["games"]
    if len(minimum_games) != int(config["gate"]["required_games"]):
        raise ValueError(f"expected 597 frozen games, found {len(minimum_games)}")

    for game in minimum_games:
        game["source_issue"] = 82 if game["board"] == "3x3" else 32 if int(game["budget"]) == 10000 else 47
        game["dataset_id"] = f"issue-{game['source_issue']}:{game['board']}-uct-{int(game['budget'])}"
        game["minimum_gate"] = True
    extended, extension_batches = extension_games(config)
    games = minimum_games + extended

    observed: dict[str, dict[str, int]] = {"3x3": {}, "4x4": {}}
    for spec in config["datasets"]:
        board, budget = spec["board"], int(spec["iteration_limit"])
        count = sum(row["board"] == board and int(row["budget"]) == budget for row in minimum_games)
        if count != int(spec["expected_games"]):
            raise ValueError(f"unexpected source count for {board} {budget}: {count}")
        observed[board][str(budget)] = count

    # Copy the per-game pins into this issue's lock so it remains independently inspectable.
    source_lock = {
        "schema_version": 1,
        "issue": 105,
        "source_issues": [32, 47, 82, 83],
        "minimum_source_lock": pin(MINIMUM_SOURCE),
        "foundational_files": [pin(common.REPO_ROOT / path) for path in FOUNDATIONAL],
        "current_corrected_game": pin(common.REPO_ROOT / "games/Heitan.lud"),
        "generation_game_hashes": {
            "3x3_issue_82": common.load_json(common.REPO_ROOT / "experiments/issue-82/protocol-lock.json")["game_sha256"],
            "4x4_issue_47": common.load_json(common.REPO_ROOT / "experiments/issue-47/protocol-lock.json")["game_sha256"],
        },
        "games": games,
        "minimum_gate_games": len(minimum_games),
        "extension_games": len(extended),
        "extension_result_batches": extension_batches,
        "observed_games": observed,
        "excluded_4x4_100k": source83["excluded_4x4_100k"],
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
            for path in sorted(common.SCRIPT_DIR.glob("*.py"))
        },
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }
    common.atomic_json(common.PROTOCOL_LOCK, protocol)
    print(f"froze {len(games)} source games")


if __name__ == "__main__":
    main()
