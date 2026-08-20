#!/usr/bin/env python3
"""Regenerate frozen predecessor analyses and Issue #47 depth comparisons."""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
from typing import Iterable

import protocol


RESULTS = protocol.ISSUE_ROOT / "results"
PRODUCTION = RESULTS / "production"
DERIVED = RESULTS / "derived"
FINAL_REPORT = protocol.REPO_ROOT / "experiments/issue-47.md"
FINALIZATION = PRODUCTION / "finalization.json"
BASELINE_ID = "uct-10000-self-play"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, object]], fields: list[str] | None = None) -> None:
    values = list(rows)
    if fields is None:
        fields = list(values[0]) if values else []
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(values)


def load_finalization(config: dict, manifest: dict | None = None) -> dict:
    """Validate the explicit terminal sample decision against the frozen task set."""
    if not FINALIZATION.is_file():
        raise ValueError("production finalization record is missing")
    value = json.loads(FINALIZATION.read_text(encoding="utf-8"))
    manifest = manifest or json.loads(protocol.manifest_path("production").read_text(encoding="utf-8"))
    tasks = protocol.tasks_from_config(config, "production")
    task_by_id = {task.task_id: task for task in tasks}
    planned = Counter(task.iteration_limit for task in tasks)
    recorded_planned = {int(key): int(count) for key, count in value["planned_games_by_budget"].items()}
    if dict(planned) != recorded_planned:
        raise ValueError("finalization planned counts differ from frozen task set")
    excluded = {row["task_id"]: row for row in value["excluded_tasks"]}
    if len(excluded) != len(value["excluded_tasks"]) or not set(excluded).issubset(task_by_id):
        raise ValueError("finalization contains duplicate or unknown excluded tasks")
    completed = Counter()
    for task in tasks:
        entry = manifest["tasks"].get(task.task_id)
        if entry is None:
            raise ValueError(f"manifest task is missing: {task.task_id}")
        if task.task_id in excluded:
            record = excluded[task.task_id]
            expected = (task.game_index, task.seed, entry["state"], int(entry["attempts"]))
            actual = (int(record["game_index"]), int(record["seed"]), record["final_state"], int(record["attempts"]))
            if expected != actual or entry["state"] != "failed":
                raise ValueError(f"finalized exclusion does not match manifest: {task.task_id}")
        elif entry["state"] == "completed":
            completed[task.iteration_limit] += 1
        else:
            raise ValueError(f"unfinalized production task is not completed: {task.task_id}")
    recorded_completed = {int(key): int(count) for key, count in value["analyzed_games_by_budget"].items()}
    if dict(completed) != recorded_completed:
        raise ValueError("finalization analyzed counts differ from completed manifest tasks")
    if not value.get("additional_production_execution_forbidden"):
        raise ValueError("production finalization is not terminal")
    return value


def production_rows(config: dict) -> list[dict[str, str]]:
    """Read the explicitly finalized, completed production sample only."""
    manifest_path = protocol.manifest_path("production")
    if not manifest_path.is_file():
        raise ValueError("production manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    finalization = load_finalization(config, manifest)
    excluded = {row["task_id"] for row in finalization["excluded_tasks"]}
    expected = protocol.tasks_from_config(config, "production")
    rows: list[dict[str, str]] = []
    for task in expected:
        if task.task_id in excluded:
            continue
        entry = manifest["tasks"].get(task.task_id)
        if entry is None or entry["state"] != "completed":
            raise ValueError(f"production task is not completed: {task.task_id}")
        if entry["namespace"] != "production":
            raise ValueError("non-production task reached production aggregation")
        row = read_csv(protocol.REPO_ROOT / entry["artifacts"]["result"])
        if len(row) != 1:
            raise ValueError(f"invalid result row count: {task.task_id}")
        rows.append(row[0])
    return rows


def baseline_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    raw = protocol.REPO_ROOT / "experiments/issue-32/results/raw"
    for path in sorted(raw.glob("*.csv")):
        rows.extend(row for row in read_csv(path) if row["experiment_id"] == BASELINE_ID)
    if len(rows) != 100:
        raise ValueError(f"expected 100 baseline games, found {len(rows)}")
    return rows


def copy_csv_rows(source_paths: list[Path], destination: Path, experiment_ids: set[str] | None = None) -> None:
    rows: list[dict[str, str]] = []
    fields: list[str] | None = None
    for path in source_paths:
        selected = read_csv(path)
        if experiment_ids is not None:
            selected = [row for row in selected if row["experiment_id"] in experiment_ids]
        if selected and fields is None:
            fields = list(selected[0])
        rows.extend(selected)
    write_csv(destination, rows, fields)


def normalize_replay_trial_paths(path: Path, metadata: list[dict[str, str]]) -> None:
    """Point staged replay rows at immutable source trials, not validation copies."""
    sources = {(row["experiment_id"], int(row["game_index"])): row["trial_file"] for row in metadata}
    rows = read_csv(path)
    for row in rows:
        key = row["experiment_id"], int(row["game_index"])
        if key not in sources:
            raise ValueError(f"staged replay has no metadata source: {key}")
        row["trial_file"] = sources[key]
    write_csv(path, rows)


def prepare_inputs(config: dict) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    metadata = baseline_rows() + production_rows(config)
    metadata_dir = DERIVED / "inputs" / "metadata"
    write_csv(metadata_dir / "all-games.csv", metadata)
    raw37 = DERIVED / "issue-37" / "results" / "raw"
    names = ("replay-summary.csv", "placements.csv", "supply-turn-states.csv", "objective-turn-states.csv")
    baseline_raw = protocol.REPO_ROOT / "experiments/issue-37/results/raw"
    production_manifest = json.loads(protocol.manifest_path("production").read_text(encoding="utf-8"))
    validation_dirs = [
        (protocol.REPO_ROOT / row["artifacts"]["validation"]).parent / "validation-raw"
        for row in production_manifest["tasks"].values() if row["state"] == "completed"
    ]
    for name in names:
        paths = [baseline_raw / name] + [directory / name for directory in validation_dirs]
        copy_csv_rows(paths, raw37 / name, {BASELINE_ID, "uct-30000-self-play", "uct-100000-self-play"})
        if name == "replay-summary.csv":
            normalize_replay_trial_paths(raw37 / name, metadata)
    return metadata, read_csv(raw37 / "replay-summary.csv")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def experiments(config: dict) -> list[dict[str, object]]:
    finalization = load_finalization(config)
    analyzed = {int(key): int(count) for key, count in finalization["analyzed_games_by_budget"].items()}
    result = [{"id": BASELINE_ID, "iteration_limit": 10000, "games": 100, "role": "baseline"}]
    for spec in config["production"]["tasks"]:
        result.append({
            "id": spec["id"], "iteration_limit": spec["iteration_limit"],
            "games": analyzed[int(spec["iteration_limit"])], "role": "deeper_evaluation",
        })
    return result


def stage_config(issue: int, config: dict) -> Path:
    source_path = protocol.REPO_ROOT / f"experiments/issue-{issue}/config.json"
    value = json.loads(source_path.read_text(encoding="utf-8"))
    root = DERIVED / f"issue-{issue}"
    previous = DERIVED / "issue-37/results"
    exps = experiments(config)
    if issue == 37:
        value["source"]["raw_results"] = (DERIVED / "inputs/metadata").relative_to(protocol.REPO_ROOT).as_posix()
        value["source"]["trial_root"] = "experiments/issue-47/results/production/tasks"
        value["source"]["experiments"] = exps
    elif issue == 39:
        value["source"].update({
            "source_trials": (previous / "source-trials.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "replay_summary": (previous / "raw/replay-summary.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "placements": (previous / "raw/placements.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "supply_turn_states": (previous / "raw/supply-turn-states.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "objective_turn_states": (previous / "raw/objective-turn-states.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "securable_opportunities": (previous / "raw/securable-opportunities.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "experiments": exps,
        })
    elif issue == 41:
        value["source"].update({
            "replay_summary": (previous / "raw/replay-summary.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "placements": (previous / "raw/placements.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "supply_turn_states": (previous / "raw/supply-turn-states.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "objective_turn_states": (previous / "raw/objective-turn-states.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "source_trials": (previous / "source-trials.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "issue_39_site_values": (DERIVED / "issue-39/results/site-value-summary.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "experiments": exps,
        })
    elif issue == 43:
        value["source"].update({
            "turn_progression": (DERIVED / "issue-41/results/raw/turn-progression.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "lead_change_summary": (DERIVED / "issue-41/results/lead-change-summary.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "reversal_by_turn": (DERIVED / "issue-41/results/reversal-by-turn.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "placements": (previous / "raw/placements.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "supply_turn_states": (previous / "raw/supply-turn-states.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "objective_turn_states": (previous / "raw/objective-turn-states.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "source_trials": (previous / "source-trials.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "site_values": (DERIVED / "issue-39/results/site-value-summary.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "experiments": [{"id": item["id"], "games": item["games"], "role": item["role"]} for item in exps],
        })
    elif issue == 44:
        value["source"].update({
            "replay_summary": (previous / "raw/replay-summary.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "placements": (previous / "raw/placements.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "supply_turn_states": (previous / "raw/supply-turn-states.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "objective_turn_states": (previous / "raw/objective-turn-states.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "source_trials": (previous / "source-trials.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "turn_progression": (DERIVED / "issue-41/results/raw/turn-progression.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "reversal_by_turn": (DERIVED / "issue-41/results/reversal-by-turn.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "site_values": (DERIVED / "issue-39/results/site-value-summary.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "issue_43_config": (DERIVED / "issue-43/config.json").relative_to(protocol.REPO_ROOT).as_posix(),
            "issue_43_checkpoint_cohorts": (DERIVED / "issue-43/results/raw/checkpoint-cohorts.csv").relative_to(protocol.REPO_ROOT).as_posix(),
            "experiments": [{"id": item["id"], "games": item["games"], "role": item["role"]} for item in exps],
        })
    path = root / "config.json"
    protocol.atomic_write_json(path, value)
    return path


def run_frozen(issue: int, config: dict) -> None:
    filenames = {37: "analyze_results.py", 39: "analyze_site_value.py", 41: "analyze_progression.py", 43: "analyze_reversals.py", 44: "analyze_prediction.py"}
    module = load_module(f"issue47_frozen_{issue}", protocol.REPO_ROOT / f"experiments/issue-{issue}/scripts/{filenames[issue]}")
    root = DERIVED / f"issue-{issue}"
    root.mkdir(parents=True, exist_ok=True)
    module.ISSUE_ROOT = root
    module.RESULTS = root / "results"
    module.RAW = module.RESULTS / "raw"
    module.CONFIG_PATH = stage_config(issue, config)
    if hasattr(module, "REPORT"):
        module.REPORT = root / "report.md"
    if hasattr(module, "REPORT_PATH"):
        module.REPORT_PATH = root / "report.md"
    skip_issue44_legacy_sensitivity = False
    if issue == 44:
        staged = json.loads(module.CONFIG_PATH.read_text(encoding="utf-8"))
        configured_ids = {row["id"] for row in staged["source"]["experiments"]}
        if "uct-3000-self-play" not in configured_ids:
            # The frozen feature construction, effects, folds, and models all
            # support arbitrary configured cohorts. Only the historical
            # sensitivity table/report hard-code 3k. Skip those two narrative
            # products while preserving every configured Issue #44 metric.
            def issue47_sensitivity_rows(comparisons):
                by_key = {
                    (int(row["checkpoint_turn"]), str(row["feature"]), str(row["experiment_id"])): row
                    for row in comparisons
                }
                output = []
                keys = sorted({(int(row["checkpoint_turn"]), str(row["feature"])) for row in comparisons})
                for checkpoint, feature in keys:
                    lower = by_key[(checkpoint, feature, "uct-30000-self-play")]
                    higher = by_key[(checkpoint, feature, "uct-100000-self-play")]
                    lower_effect = float(lower["standardized_mean_difference"])
                    higher_effect = float(higher["standardized_mean_difference"])
                    output.append({
                        "checkpoint_turn": checkpoint,
                        "feature": feature,
                        "uct_30000_standardized_mean_difference": lower_effect,
                        "uct_100000_standardized_mean_difference": higher_effect,
                        "direction_agreement": int(module.sign(lower_effect) == module.sign(higher_effect)),
                        "uct_30000_direction": lower["effect_direction"],
                        "uct_100000_direction": higher["effect_direction"],
                    })
                return output

            module.sensitivity_rows = issue47_sensitivity_rows
            module.write_report = lambda *args, **kwargs: None
            skip_issue44_legacy_sensitivity = True
    try:
        module.main()
        if skip_issue44_legacy_sensitivity:
            protocol.atomic_write_json(root / "adapter-note.json", {
                "schema_version": 1,
                "frozen_issue": 44,
                "behavior_preserved": True,
                "skipped_legacy_report_section": "uct-10000-self-play vs uct-3000-self-play narrative",
                "replacement_path_adapter": "The unchanged standardized-effect and direction-agreement calculation is applied to configured 30k vs 100k cohorts.",
                "reason": "Issue #47 has no 3k cohort; configured feature comparisons, effects, folds, and model evaluations are unchanged.",
            })
    except KeyError as error:
        # Issue #39 computes every configured site-value table before its
        # historical report-only 3k-vs-10k comparison. Issue #47 deliberately
        # has no 3k cohort, so accept only that exact late legacy lookup after
        # verifying the frozen metric output already exists. No definition or
        # threshold is changed.
        expected_legacy_key = ("uct-3000-self-play", "S00")
        required = module.RESULTS / "site-value-summary.csv"
        if issue != 39 or not error.args or error.args[0] != expected_legacy_key or not required.is_file():
            raise
        protocol.atomic_write_json(root / "adapter-note.json", {
            "schema_version": 1,
            "frozen_issue": 39,
            "behavior_preserved": True,
            "skipped_legacy_report_section": "uct-3000-self-play vs uct-10000-self-play",
            "reason": "Issue #47 config contains only 10k, 30k, and 100k cohorts; all configured site-value metric tables were written before the legacy lookup.",
        })
    except statistics.StatisticsError as error:
        # Issue #43 likewise writes all configured mechanism/cohort tables
        # before building a historical 10k-vs-3k report headline. With no 3k
        # cohort that report-only mean is empty. Preserve the written frozen
        # metrics and skip only that unavailable legacy narrative.
        required = [
            module.RESULTS / "reversal-mechanism-summary.csv",
            module.RESULTS / "raw/checkpoint-cohorts.csv",
        ]
        if issue != 43 or str(error) != "mean requires at least one data point" or not all(path.is_file() for path in required):
            raise
        protocol.atomic_write_json(root / "adapter-note.json", {
            "schema_version": 1,
            "frozen_issue": 43,
            "behavior_preserved": True,
            "skipped_legacy_report_section": "uct-10000-self-play vs uct-3000-self-play headline",
            "reason": "Issue #47 has no 3k cohort; all configured reversal mechanism and checkpoint cohort tables were written before the empty legacy mean.",
        })


def wilson(wins: int, total: int) -> tuple[float, float]:
    if total == 0:
        return 0.0, 0.0
    z = 1.959963984540054
    p = wins / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return center - margin, center + margin


def spearman(left: dict[str, float], right: dict[str, float]) -> float:
    def rank(values: dict[str, float]) -> dict[str, float]:
        ordered = sorted(values, key=lambda key: (values[key], key))
        return {key: float(index) for index, key in enumerate(ordered, 1)}
    a, b = rank(left), rank(right)
    keys = sorted(left)
    mean_a = statistics.mean(a[key] for key in keys)
    mean_b = statistics.mean(b[key] for key in keys)
    numerator = sum((a[key] - mean_a) * (b[key] - mean_b) for key in keys)
    denominator = math.sqrt(sum((a[key] - mean_a) ** 2 for key in keys) * sum((b[key] - mean_b) ** 2 for key in keys))
    return numerator / denominator if denominator else 0.0


def classify(values: list[float], samples: list[int], preserve_direction: bool = True) -> tuple[str, dict[str, float]]:
    evidence = {"value_10k": values[0], "value_30k": values[1], "value_100k": values[2], "delta_10k_30k": values[1] - values[0], "delta_30k_100k": values[2] - values[1]}
    if min(samples[1:]) < 25:
        return "insufficient evidence", evidence
    first, second = evidence["delta_10k_30k"], evidence["delta_30k_100k"]
    if first * second < 0 and abs(first) > 0.03 and abs(second) > 0.03:
        return "non-monotonic", evidence
    if abs(first) <= 0.03 and abs(second) <= 0.03 and preserve_direction:
        return "stable / converged-looking", evidence
    if first * second >= 0 and abs(second) < abs(first) and abs(second) <= 0.07:
        return "directionally stabilizing", evidence
    return "search-sensitive", evidence


def aggregate(config: dict, metadata: list[dict[str, str]]) -> dict:
    final = RESULTS / "final"
    ids = [BASELINE_ID, "uct-30000-self-play", "uct-100000-self-play"]
    depths = {BASELINE_ID: 10000, "uct-30000-self-play": 30000, "uct-100000-self-play": 100000}
    samples = {item["id"]: int(item["games"]) for item in experiments(config)}
    balance: list[dict[str, object]] = []
    for experiment in ids:
        selected = [row for row in metadata if row["experiment_id"] == experiment]
        counts = Counter(int(row["winner"]) for row in selected)
        p1_low, p1_high = wilson(counts[1], len(selected))
        p2_low, p2_high = wilson(counts[2], len(selected))
        balance.append({
            "experiment_id": experiment, "iteration_limit": depths[experiment], "games": len(selected),
            "p1_wins": counts[1], "p2_wins": counts[2], "draws": counts[0],
            "p1_win_rate": round(counts[1] / len(selected), 6), "p1_wilson_95_low": round(p1_low, 6), "p1_wilson_95_high": round(p1_high, 6),
            "p2_win_rate": round(counts[2] / len(selected), 6), "p2_wilson_95_low": round(p2_low, 6), "p2_wilson_95_high": round(p2_high, 6),
            **{field: round(statistics.mean(int(row[field]) for row in selected), 6) for field in (
                "p1_secured_objectives", "p2_secured_objectives", "p1_advantage_objectives", "p2_advantage_objectives",
                "p1_objective_pieces", "p2_objective_pieces", "p1_supply_pieces", "p2_supply_pieces", "p1_secured_supply", "p2_secured_supply",
            )},
        })
    write_csv(final / "balance-by-depth.csv", balance)

    timing = read_csv(DERIVED / "issue-37/results/securing-timing-summary.csv")
    events = read_csv(DERIVED / "issue-37/results/raw/supply-events.csv")
    opportunities = read_csv(DERIVED / "issue-37/results/raw/securable-opportunities.csv")
    securing: list[dict[str, object]] = []
    for experiment in ids:
        selected = [row for row in events if row["experiment_id"] == experiment]
        turns = [int(row["securing_turn"]) for row in selected]
        games_with = len({int(row["game_index"]) for row in selected})
        legal = [row for row in opportunities if row["experiment_id"] == experiment and row["securable"] == "true"]
        ever = {(row["game_index"], row["player"], row["supply_point"]): row["eventually_secured_by_player"] == "true" for row in legal}
        phases = Counter(row["securing_phase"] for row in selected)
        securing.append({
            "experiment_id": experiment, "iteration_limit": depths[experiment], "games": samples[experiment],
            "games_with_any_securing": games_with, "games_with_any_securing_rate": round(games_with / samples[experiment], 6),
            "first_securing_turn_mean": round(statistics.mean(min(int(row["securing_turn"]) for row in selected if int(row["game_index"]) == game) for game in {int(row["game_index"]) for row in selected}), 6) if selected else "",
            "first_securing_turn_median": statistics.median(min(int(row["securing_turn"]) for row in selected if int(row["game_index"]) == game) for game in {int(row["game_index"]) for row in selected}) if selected else "",
            "total_securing_events": len(selected), "mean_securing_turn": round(statistics.mean(turns), 6) if turns else "",
            "early_events": phases["early"], "midgame_events": phases["midgame"], "late_events": phases["late"],
            "legal_securable_opportunities": len(legal), "immediate_take_rate": round(sum(row["secured_this_turn"] == "true" for row in legal) / len(legal), 6) if legal else 0,
            "ever_securable_player_sites": len(ever), "eventual_securing_rate": round(sum(ever.values()) / len(ever), 6) if ever else 0,
            "later_objective_uses_after_securing": sum(int(row["future_objective_placements_supported"]) for row in selected),
        })
    write_csv(final / "supply-securing-by-depth.csv", securing)

    site_rows = read_csv(DERIVED / "issue-39/results/site-value-summary.csv")
    write_csv(final / "site-value-by-depth.csv", site_rows)
    metric = "objective_placements_supplied_per_player_game"
    maps = {experiment: {row["supply_point"]: float(row[metric]) for row in site_rows if row["experiment_id"] == experiment} for experiment in ids}
    ranks: list[dict[str, object]] = []
    for left, right in zip(ids, ids[1:]):
        values = sorted(maps[right].values(), reverse=True)
        total = sum(maps[right].values())
        shares = sorted((value / total for value in maps[right].values()), reverse=True) if total else [0.0] * 25
        ranks.append({
            "metric": metric, "from_experiment": left, "to_experiment": right,
            "spearman_rank_correlation": round(spearman(maps[left], maps[right]), 6),
            "top_3_usage_share": round(sum(shares[:3]), 6), "top_5_usage_share": round(sum(shares[:5]), 6),
            "usage_hhi": round(sum(value * value for value in shares), 6),
            "frozen_important_sites": ";".join(config["important_supply_sites"]),
            "frozen_important_sites_in_top5": sum(site in {key for key, _ in sorted(maps[right].items(), key=lambda pair: (-pair[1], pair[0]))[:5]} for site in config["important_supply_sites"]),
        })
    write_csv(final / "site-rank-convergence.csv", ranks)

    reversals_all = read_csv(DERIVED / "issue-41/results/reversal-by-turn.csv")
    reversals = [row for row in reversals_all if row["comparison_layer"] == "full_lexicographic" and int(row["turn_number"]) in (8, 12, 16, 20)]
    write_csv(final / "reversibility-by-depth.csv", reversals)
    mechanisms = read_csv(DERIVED / "issue-43/results/reversal-mechanism-summary.csv")
    write_csv(final / "reversal-mechanisms-by-depth.csv", mechanisms)
    precursors = read_csv(DERIVED / "issue-44/results/feature-comparison-summary.csv")
    key_features = {"decisive_margin", "leader_trend_4_usable_support_edges", "opponent_trend_4_usable_support_edges", "leader_primary_important_control_margin", "opponent_recent_4_supply_allocation_change"}
    precursor_selected = [row for row in precursors if row["feature"] in key_features]
    write_csv(final / "reversal-precursors-by-depth.csv", precursor_selected)

    summary: list[dict[str, object]] = []
    series = {
        "p1_win_rate": [float(next(row for row in balance if row["experiment_id"] == experiment)["p1_win_rate"]) for experiment in ids],
        "games_with_any_securing_rate": [float(next(row for row in securing if row["experiment_id"] == experiment)["games_with_any_securing_rate"]) for experiment in ids],
        "turn20_reversal_rate": [float(next(row for row in reversals if row["experiment_id"] == experiment and int(row["turn_number"]) == 20)["reversal_rate_current_leader_eventually_loses"]) for experiment in ids],
    }
    sample_list = [samples[experiment] for experiment in ids]
    for name, values in series.items():
        label, evidence = classify(values, sample_list)
        summary.append({"metric": name, "normalization": "proportion", **evidence, "classification": label, "manual_override": "false"})
    write_csv(final / "strategic-convergence-summary.csv", summary)
    finalization = load_finalization(config)
    return {
        "schema_version": 1, "protocol_lock_sha256": protocol.sha256(protocol.ISSUE_ROOT / "protocol-lock.json"),
        "finalization_sha256": protocol.sha256(FINALIZATION),
        "samples": samples,
        "planned_production_samples": finalization["planned_games_by_budget"],
        "excluded_production_tasks": finalization["excluded_tasks"],
        "pilot_excluded": True, "convergence_summary": summary,
        "integrity": {"metadata_games": len(metadata), "production_games": len(metadata) - 100, "baseline_games": 100},
    }


def render_report(analysis: dict) -> str:
    balance = read_csv(RESULTS / "final/balance-by-depth.csv")
    securing = read_csv(RESULTS / "final/supply-securing-by-depth.csv")
    ranks = read_csv(RESULTS / "final/site-rank-convergence.csv")
    reversals = read_csv(RESULTS / "final/reversibility-by-depth.csv")
    finalization = load_finalization(protocol.load_config())
    balance_lines = ["| Budget | Games | P1 wins | P2 wins | Draws | P1 win rate | 95% CI |", "|---:|---:|---:|---:|---:|---:|---:|"]
    for row in balance:
        balance_lines.append(
            f"| {int(row['iteration_limit']):,} | {row['games']} | {row['p1_wins']} | {row['p2_wins']} | {row['draws']} | "
            f"{100 * float(row['p1_win_rate']):.1f}% | {100 * float(row['p1_wilson_95_low']):.1f}–{100 * float(row['p1_wilson_95_high']):.1f}% |"
        )
    securing_lines = ["| Budget | Games | Supply events/game | First securing turn | Immediate take | Eventual securing |", "|---:|---:|---:|---:|---:|---:|"]
    for row in securing:
        games = int(row["games"])
        securing_lines.append(
            f"| {int(row['iteration_limit']):,} | {games} | {int(row['total_securing_events']) / games:.2f} | "
            f"{float(row['first_securing_turn_mean']):.2f} | {100 * float(row['immediate_take_rate']):.2f}% | "
            f"{100 * float(row['eventual_securing_rate']):.2f}% |"
        )
    rank_100k = next(row for row in ranks if row["to_experiment"] == "uct-100000-self-play")
    reversal_100k = [row for row in reversals if row["experiment_id"] == "uct-100000-self-play"]
    reversal_text = ", ".join(
        f"T{row['turn_number']}={100 * float(row['reversal_rate_current_leader_eventually_loses']):.1f}%"
        for row in reversal_100k
    )
    convergence_lines = ["| Metric | 10k | 30k | 100k (97 games) | Classification |", "|---|---:|---:|---:|---|"]
    for row in analysis["convergence_summary"]:
        convergence_lines.append(
            f"| {row['metric']} | {row['value_10k']:.4f} | {row['value_30k']:.4f} | {row['value_100k']:.4f} | {row['classification']} |"
        )
    excluded = ", ".join(f"game {row['game_index']} (seed {row['seed']})" for row in finalization["excluded_tasks"])
    diagnostic = finalization["memory_diagnostic_10g"]
    return (
        "# Issue 47: Strategic convergence under deeper UCT search\n\n"
        "## Final production sample\n\n"
        "The UCT 100,000 production analysis is finalized at **97 validated games**. The locked plan targeted "
        "100 games; the remaining three were not replaced and are not treated as completed. UCT 30,000 contains "
        "100 validated games, and the existing UCT 10,000 baseline contains 100 games. The excluded pilot and all "
        "memory diagnostics are absent from these aggregates.\n\n"
        f"The uncompleted identities are {excluded}. They exhausted memory during 100k MCTS search. This creates a "
        "possible missing-not-at-random limitation because memory-intensive search trajectories may differ from completed games.\n\n"
        "## Memory diagnosis and stopping decision\n\n"
        f"The excluded 10GB diagnostic failed after approximately 57 minutes. Full GC retained {diagnostic['full_gc_live_heap_mib']:,} MiB, "
        "showing that the live MCTS search tree, rather than reclaimable temporary objects, filled the heap. A "
        f"{diagnostic['heap_dump_size_bytes'] / (1024 ** 3):.1f} GiB heap dump was created. The project will not change tree retention, "
        "increase the production heap further, use a larger-memory host, or generate replacement seeds for this analysis.\n\n"
        "## Balance\n\n" + "\n".join(balance_lines) + "\n\n"
        "## Supply behavior\n\n" + "\n".join(securing_lines) + "\n\n"
        "For 30k→100k, the Supply-site usage rank correlation is "
        f"{float(rank_100k['spearman_rank_correlation']):.3f}; the 100k top-five usage share is "
        f"{100 * float(rank_100k['top_5_usage_share']):.1f}% and HHI is {float(rank_100k['usage_hhi']):.4f}.\n\n"
        f"The 100k full-lexicographic reversal rates are {reversal_text}.\n\n"
        "## Frozen convergence classifications\n\n" + "\n".join(convergence_lines) + "\n\n"
        "These labels apply the pre-locked mechanical rules without manual override. They describe empirical robustness "
        "across these samples; they do not establish game-theoretic convergence or solve Heitan. Numeric evidence is in "
        "`experiments/issue-47/results/final/analysis.json` and the by-depth CSV files.\n"
    )


def output_hashes() -> dict[str, str]:
    return {path.relative_to(protocol.REPO_ROOT).as_posix(): protocol.sha256(path) for path in sorted((RESULTS / "final").glob("*")) if path.is_file()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ludii-jar", default=os.environ.get("LUDII_JAR", ""))
    parser.add_argument("--verify-deterministic", action="store_true")
    args = parser.parse_args()
    config = protocol.load_config()
    if config["protocol_status"] != "locked":
        raise ValueError("analysis requires a locked production protocol")
    metadata, replay = prepare_inputs(config)
    for issue in (37, 39, 41, 43, 44):
        run_frozen(issue, config)
    analysis = aggregate(config, metadata)
    final = RESULTS / "final"
    protocol.atomic_write_json(final / "analysis.json", analysis)
    first = output_hashes()
    if args.verify_deterministic:
        metadata, replay = prepare_inputs(config)
        for issue in (37, 39, 41, 43, 44):
            run_frozen(issue, config)
        protocol.atomic_write_json(final / "analysis.json", aggregate(config, metadata))
        second = output_hashes()
        if first != second:
            raise ValueError("deterministic regeneration mismatch")
    environment = {
        "schema_version": 1, "generated_at_utc": protocol.utc_now(),
        "config_sha256": protocol.sha256(protocol.CONFIG_PATH),
        "protocol_lock_sha256": protocol.sha256(protocol.ISSUE_ROOT / "protocol-lock.json"),
        "finalization_sha256": protocol.sha256(FINALIZATION),
        "game_sha256": protocol.sha256(protocol.REPO_ROOT / config["game"]),
        "python": platform.python_version(), "os": platform.platform(), "machine": platform.machine(),
        "deterministic_regeneration_verified": args.verify_deterministic,
        "output_hashes": output_hashes(), "pilot_paths_in_outputs": 0,
    }
    protocol.atomic_write_json(final / "environment.json", environment)
    FINAL_REPORT.write_text(render_report(analysis), encoding="utf-8")


if __name__ == "__main__":
    main()
