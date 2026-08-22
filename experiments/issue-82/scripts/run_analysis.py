#!/usr/bin/env python3
"""Analyze the finalized Issue #82 sample without cross-board claims."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import statistics
from typing import Iterable

import protocol


FINAL = protocol.RESULTS_ROOT / "final"
REPORT = protocol.REPO_ROOT / "experiments/issue-82.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, object]], fields: list[str]) -> None:
    values = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(values)


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("percentile requires values")
    location = (len(ordered) - 1) * probability
    low, high = math.floor(location), math.ceil(location)
    if low == high:
        return ordered[low]
    return ordered[low] * (high - location) + ordered[high] * (location - low)


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float | None, float | None]:
    if total == 0:
        return None, None
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, centre - radius), min(1.0, centre + radius)


def newcombe_difference(a_success: int, a_total: int, b_success: int, b_total: int) -> tuple[float | None, float | None]:
    if not a_total or not b_total:
        return None, None
    pa, pb = a_success / a_total, b_success / b_total
    al, au = wilson(a_success, a_total)
    bl, bu = wilson(b_success, b_total)
    assert al is not None and au is not None and bl is not None and bu is not None
    difference = pa - pb
    lower = difference - math.sqrt((pa - al) ** 2 + (bu - pb) ** 2)
    upper = difference + math.sqrt((au - pa) ** 2 + (pb - bl) ** 2)
    return max(-1.0, lower), min(1.0, upper)


def bootstrap_rate(values: list[int], samples: int, seed: int) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    rng = random.Random(seed)
    estimates = [sum(rng.choice(values) for _ in values) / len(values) for _ in range(samples)]
    return percentile(estimates, 0.025), percentile(estimates, 0.975)


def bootstrap_difference(a: list[int], b: list[int], samples: int, seed: int) -> tuple[float | None, float | None]:
    if not a or not b:
        return None, None
    rng = random.Random(seed)
    estimates = []
    for _ in range(samples):
        pa = sum(rng.choice(a) for _ in a) / len(a)
        pb = sum(rng.choice(b) for _ in b) / len(b)
        estimates.append(pa - pb)
    return percentile(estimates, 0.025), percentile(estimates, 0.975)


def classify_stability(values: list[float], samples: list[int], policy: dict) -> tuple[str, dict[str, float | str]]:
    minimum = int(policy["minimum_games_per_primary_budget"])
    if len(values) != 3 or len(samples) != 3 or any(count < minimum for count in samples):
        return "unresolved", {"reason": "insufficient primary sample"}
    first, second = values[1] - values[0], values[2] - values[1]
    evidence: dict[str, float | str] = {"delta_30k_minus_10k": first, "delta_100k_minus_30k": second}
    material = float(policy["non_monotonic_material_delta_min"])
    stable = float(policy["stable_absolute_delta_max"])
    directional = float(policy["directionally_stabilizing_latest_delta_max"])
    epsilon = 1e-12
    if first * second < 0 and abs(first) > material + epsilon and abs(second) > material + epsilon:
        return "non-monotonic", evidence
    if abs(first) <= stable + epsilon and abs(second) <= stable + epsilon:
        return "stable / converged-looking", evidence
    if first * second >= 0 and abs(second) < abs(first) - epsilon and abs(second) <= directional + epsilon:
        return "directionally stabilizing", evidence
    return "unresolved", evidence


def load_finalized(config: dict) -> tuple[list[protocol.Task], dict, dict]:
    if config["protocol_status"] != "locked" or not protocol.LOCK_PATH.is_file():
        raise ValueError("analysis requires a locked protocol")
    if not protocol.FINALIZATION_PATH.is_file():
        raise ValueError("analysis requires terminal production finalization")
    lock = json.loads(protocol.LOCK_PATH.read_text(encoding="utf-8"))
    if lock["config_sha256"] != protocol.sha256(protocol.CONFIG_PATH):
        raise ValueError("config differs from protocol lock")
    finalization = json.loads(protocol.FINALIZATION_PATH.read_text(encoding="utf-8"))
    manifest_path = protocol.manifest_path("production")
    if finalization["manifest_sha256"] != protocol.sha256(manifest_path):
        raise ValueError("production manifest changed after finalization")
    return protocol.tasks_from_config(config, "production"), json.loads(manifest_path.read_text(encoding="utf-8")), finalization


def completed_rows(tasks: list[protocol.Task], manifest: dict) -> tuple[list[dict[str, str]], dict[tuple[int, int], Path]]:
    rows: list[dict[str, str]] = []
    state_paths: dict[tuple[int, int], Path] = {}
    seen_keys: set[tuple[int, int]] = set()
    seen_seeds: set[int] = set()
    for task in tasks:
        entry = manifest["tasks"][task.task_id]
        if entry["state"] != "completed":
            continue
        error = protocol.artifact_error(entry)
        if error:
            raise ValueError(f"completed artifact failed integrity check: {task.task_id}: {error}")
        result = read_csv(protocol.REPO_ROOT / entry["artifacts"]["result"])
        if len(result) != 1:
            raise ValueError(f"completed task has {len(result)} result rows: {task.task_id}")
        row = result[0]
        key = task.iteration_limit, task.game_index
        if key in seen_keys or task.seed in seen_seeds:
            raise ValueError("duplicate game key or seed")
        seen_keys.add(key)
        seen_seeds.add(task.seed)
        rows.append(row)
        state_paths[key] = (protocol.REPO_ROOT / entry["artifacts"]["validation"]).parent / "validation-raw" / "turn-states.csv"
    return rows, state_paths


def optional(value: float | None) -> str | float:
    return "" if value is None else round(value, 6)


def leader(rows: list[dict[str, str]]) -> int:
    objectives = [row for row in rows if row["point_type"] == "objective"]
    secured = [sum(int(row["state_at_turn_end"]) == state for row in objectives) for state in (3, 4)]
    advantage = [sum(int(row["state_at_turn_end"]) == state for row in objectives) for state in (1, 2)]
    pieces = [sum(int(row[f"p{player}_at_turn_end"]) for row in objectives) for player in (1, 2)]
    for values in (secured, advantage, pieces):
        if values[0] != values[1]:
            return 1 if values[0] > values[1] else 2
    return 0


def game_diagnostic(row: dict[str, str], states_path: Path, checkpoints: list[float]) -> tuple[dict[str, object], list[dict[str, object]]]:
    states = read_csv(states_path)
    by_turn: dict[int, list[dict[str, str]]] = defaultdict(list)
    for state in states:
        by_turn[int(state["turn_number"])].append(state)
    leaders = {turn: leader(values) for turn, values in by_turn.items()}
    winner = int(row["winner"])
    persistent: int | str = ""
    if winner:
        for turn in range(1, 19):
            if all(leaders[later] == winner for later in range(turn, 19)):
                persistent = turn
                break
    diagnostic = {
        "iteration_limit": int(row["iteration_limit"]), "game_index": int(row["game_index"]),
        "seed": int(row["seed"]), "winner": winner, "deciding_criterion": row["deciding_criterion"],
        "secured_objective_difference_p1_minus_p2": int(row["p1_secured_objectives"]) - int(row["p2_secured_objectives"]),
        "advantage_objective_difference_p1_minus_p2": int(row["p1_advantage_objectives"]) - int(row["p2_advantage_objectives"]),
        "objective_piece_difference_p1_minus_p2": int(row["p1_objective_pieces"]) - int(row["p2_objective_pieces"]),
        "first_persistent_full_lexicographic_lead_turn": persistent,
    }
    reversals = []
    for checkpoint in checkpoints:
        turn = math.ceil(checkpoint * 18)
        checkpoint_leader = leaders[turn]
        eligible = checkpoint_leader != 0 and winner != 0
        reversals.append({
            "iteration_limit": int(row["iteration_limit"]), "game_index": int(row["game_index"]),
            "checkpoint": checkpoint, "turn_number": turn, "leader": checkpoint_leader,
            "winner": winner, "eligible": str(eligible).lower(),
            "late_reversal": str(eligible and checkpoint_leader != winner).lower(),
        })
    return diagnostic, reversals


def build_outputs(config: dict, rows: list[dict[str, str]], tasks: list[protocol.Task], manifest: dict) -> dict:
    samples = int(config["analysis"]["bootstrap_samples"])
    seed = int(config["analysis"]["bootstrap_seed"])
    budgets = sorted({task.iteration_limit for task in tasks})
    by_budget = {budget: [row for row in rows if int(row["iteration_limit"]) == budget] for budget in budgets}
    balance = []
    binary: dict[int, dict[str, list[int]]] = {}
    for offset, budget in enumerate(budgets):
        selected = by_budget[budget]
        winners = [int(row["winner"]) for row in selected]
        p1, p2, draws = winners.count(1), winners.count(2), winners.count(0)
        p1_values = [int(value == 1) for value in winners]
        draw_values = [int(value == 0) for value in winners]
        decisive = [int(value == 1) for value in winners if value != 0]
        binary[budget] = {"p1": p1_values, "draw": draw_values}
        p1_ci = wilson(p1, len(winners))
        decisive_ci = wilson(p1, p1 + p2)
        p1_boot = bootstrap_rate(p1_values, samples, seed + offset)
        balance.append({
            "iteration_limit": budget, "validated_games": len(winners), "p1_wins": p1,
            "p2_wins": p2, "draws": draws, "p1_win_rate": optional(p1 / len(winners) if winners else None),
            "p1_wilson_95_low": optional(p1_ci[0]), "p1_wilson_95_high": optional(p1_ci[1]),
            "p1_bootstrap_95_low": optional(p1_boot[0]), "p1_bootstrap_95_high": optional(p1_boot[1]),
            "decisive_games": p1 + p2, "decisive_p1_share": optional(p1 / (p1 + p2) if p1 + p2 else None),
            "decisive_p1_wilson_95_low": optional(decisive_ci[0]), "decisive_p1_wilson_95_high": optional(decisive_ci[1]),
        })
    fields = list(balance[0]) if balance else ["iteration_limit"]
    write_csv(FINAL / "balance-by-depth.csv", balance, fields)

    pairs = [(30000, 10000), (100000, 30000), (100000, 10000)]
    if 300000 in budgets:
        pairs.append((300000, 100000))
    contrasts = []
    for offset, (higher, lower) in enumerate(pairs):
        if higher not in binary or lower not in binary:
            continue
        hp, lp = binary[higher]["p1"], binary[lower]["p1"]
        hd, ld = binary[higher]["draw"], binary[lower]["draw"]
        p1_diff = (sum(hp) / len(hp) - sum(lp) / len(lp)) if hp and lp else None
        draw_diff = (sum(hd) / len(hd) - sum(ld) / len(ld)) if hd and ld else None
        p1_newcombe = newcombe_difference(sum(hp), len(hp), sum(lp), len(lp))
        draw_newcombe = newcombe_difference(sum(hd), len(hd), sum(ld), len(ld))
        p1_boot = bootstrap_difference(hp, lp, samples, seed + 100 + offset)
        draw_boot = bootstrap_difference(hd, ld, samples, seed + 200 + offset)
        contrasts.append({
            "contrast": f"{higher // 1000}k - {lower // 1000}k", "higher_budget": higher, "lower_budget": lower,
            "p1_win_rate_difference": optional(p1_diff), "p1_newcombe_95_low": optional(p1_newcombe[0]),
            "p1_newcombe_95_high": optional(p1_newcombe[1]), "p1_bootstrap_95_low": optional(p1_boot[0]),
            "p1_bootstrap_95_high": optional(p1_boot[1]), "draw_rate_difference": optional(draw_diff),
            "draw_newcombe_95_low": optional(draw_newcombe[0]), "draw_newcombe_95_high": optional(draw_newcombe[1]),
            "draw_bootstrap_95_low": optional(draw_boot[0]), "draw_bootstrap_95_high": optional(draw_boot[1]),
        })
    write_csv(FINAL / "balance-contrasts.csv", contrasts, list(contrasts[0]) if contrasts else ["contrast"])

    primary_rows = [next((row for row in balance if row["iteration_limit"] == budget), None) for budget in config["primary_budgets"]]
    primary_values = [float(row["p1_win_rate"]) for row in primary_rows if row and row["p1_win_rate"] != ""]
    primary_samples = [int(row["validated_games"]) for row in primary_rows if row]
    label, evidence = classify_stability(primary_values, primary_samples, config["stability_classification"])
    classification = {
        "classification": label, "threshold_source": config["stability_classification"]["source"],
        "manual_override": False, **evidence,
    }
    write_csv(FINAL / "stability-classification.csv", [classification], list(classification))

    failures = []
    for task in tasks:
        entry = manifest["tasks"][task.task_id]
        if entry["state"] != "completed":
            failures.append({
                "task_id": task.task_id, "iteration_limit": task.iteration_limit,
                "game_index": task.game_index, "seed": task.seed, "state": entry["state"],
                "attempts": entry["attempts"], "failure_kind": entry.get("failure_kind") or "",
                "error": entry.get("error") or "",
            })
    write_csv(FINAL / "failures.csv", failures, ["task_id", "iteration_limit", "game_index", "seed", "state", "attempts", "failure_kind", "error"])
    return {"balance": balance, "contrasts": contrasts, "classification": classification, "failures": failures}


def build_diagnostics(config: dict, rows: list[dict[str, str]], state_paths: dict[tuple[int, int], Path]) -> dict:
    games, reversals = [], []
    for row in rows:
        key = int(row["iteration_limit"]), int(row["game_index"])
        game, game_reversals = game_diagnostic(row, state_paths[key], config["analysis"]["late_reversal_checkpoints"])
        games.append(game)
        reversals.extend(game_reversals)
    write_csv(FINAL / "game-diagnostics.csv", games, list(games[0]) if games else ["iteration_limit"])
    write_csv(FINAL / "late-reversals.csv", reversals, list(reversals[0]) if reversals else ["iteration_limit"])
    summary = []
    for (budget, checkpoint), selected in sorted(_group(reversals, lambda row: (row["iteration_limit"], row["checkpoint"])).items()):
        eligible = [row for row in selected if row["eligible"] == "true"]
        count = sum(row["late_reversal"] == "true" for row in eligible)
        summary.append({
            "iteration_limit": budget, "checkpoint": checkpoint, "games": len(selected),
            "eligible_games": len(eligible), "late_reversals": count,
            "late_reversal_rate": optional(count / len(eligible) if eligible else None),
        })
    write_csv(FINAL / "late-reversal-summary.csv", summary, list(summary[0]) if summary else ["iteration_limit"])
    return {"game_diagnostics": len(games), "late_reversal_rows": len(reversals)}


def _group(rows: list[dict[str, object]], key):
    result = defaultdict(list)
    for row in rows:
        result[key(row)].append(row)
    return result


def output_hashes() -> dict[str, str]:
    return {
        path.relative_to(protocol.REPO_ROOT).as_posix(): protocol.sha256(path)
        for path in sorted(FINAL.iterdir())
        if path.is_file() and path.name != "environment.json"
    }


def render_report(analysis: dict) -> str:
    def percent(value: object, signed: bool = False) -> str:
        if value == "" or value is None:
            return "NA"
        return f"{100 * float(value):+.{1}f}" if signed else f"{100 * float(value):.{1}f}"

    balance_lines = ["| UCT | Validated | P1 | P2 | Draw | P1 rate | Wilson 95% CI |", "|---:|---:|---:|---:|---:|---:|---:|"]
    for row in analysis["balance"]:
        balance_lines.append(
            f"| {row['iteration_limit']:,} | {row['validated_games']} | {row['p1_wins']} | {row['p2_wins']} | {row['draws']} | "
            f"{percent(row['p1_win_rate'])}% | {percent(row['p1_wilson_95_low'])}–{percent(row['p1_wilson_95_high'])}% |"
        )
    contrast_lines = ["| Contrast | P1-rate change | 95% CI | Draw-rate change |", "|---|---:|---:|---:|"]
    for row in analysis["contrasts"]:
        contrast_lines.append(
            f"| {row['contrast']} | {percent(row['p1_win_rate_difference'], True)} pp | "
            f"{percent(row['p1_newcombe_95_low'], True)} to {percent(row['p1_newcombe_95_high'], True)} pp | "
            f"{percent(row['draw_rate_difference'], True)} pp |"
        )
    failures = analysis["failures"]
    failure_text = "No production games failed." if not failures else f"{len(failures)} production game(s) are missing and listed in `results/final/failures.csv`. Missingness may be non-random."
    return (
        "# Issue 82: 3x3 deep-UCT first-player balance\n\n"
        "## Primary balance\n\n" + "\n".join(balance_lines) + "\n\n"
        "The unconditional P1 rate retains draws in its denominator. Decisive-game shares are secondary and are available in the CSV.\n\n"
        "## Search-depth contrasts\n\n" + "\n".join(contrast_lines) + "\n\n"
        f"## Empirical stability\n\n**{analysis['classification']['classification']}**\n\n"
        "This label applies the unchanged Issue #47 thresholds mechanically. It describes robustness across these samples only; it does not establish optimal play or solved-game balance.\n\n"
        f"## Incomplete games\n\n{failure_text}\n\n"
        "## Scope\n\nThis result is a 3x3 deep-search baseline. It makes no cross-board balance claim. Secondary structural diagnostics are reported separately and do not redefine the primary conclusion.\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-deterministic", action="store_true")
    args = parser.parse_args()
    config = protocol.load_config()
    tasks, manifest, finalization = load_finalized(config)
    rows, state_paths = completed_rows(tasks, manifest)
    analysis = build_outputs(config, rows, tasks, manifest)
    analysis["secondary"] = build_diagnostics(config, rows, state_paths)
    analysis["schema_version"] = 1
    analysis["primary_budgets"] = config["primary_budgets"]
    analysis["optional_budget_status"] = config["optional_budget"]["adoption_status"]
    analysis["planned_games_by_budget"] = finalization["planned_games_by_budget"]
    analysis["completed_games_by_budget"] = finalization["completed_games_by_budget"]
    analysis["pilot_excluded"] = True
    protocol.atomic_write_json(FINAL / "analysis.json", analysis)
    first = output_hashes()
    if args.verify_deterministic:
        rows, state_paths = completed_rows(tasks, manifest)
        repeated = build_outputs(config, rows, tasks, manifest)
        repeated["secondary"] = build_diagnostics(config, rows, state_paths)
        if first != output_hashes() or repeated != {key: analysis[key] for key in ("balance", "contrasts", "classification", "failures", "secondary")}:
            raise ValueError("deterministic regeneration mismatch")
    environment = {
        "schema_version": 1, "generated_at_utc": protocol.utc_now(),
        "python": platform.python_version(), "os": platform.platform(), "machine": platform.machine(),
        "config_sha256": protocol.sha256(protocol.CONFIG_PATH),
        "protocol_lock_sha256": protocol.sha256(protocol.LOCK_PATH),
        "finalization_sha256": protocol.sha256(protocol.FINALIZATION_PATH),
        "manifest_sha256": protocol.sha256(protocol.manifest_path("production")),
        "game_sha256": protocol.sha256(protocol.REPO_ROOT / config["game"]),
        "runner_sha256": protocol.sha256(protocol.REPO_ROOT / "experiments/issue-62/scripts/Heitan3x3Experiment.java"),
        "replayer_sha256": protocol.sha256(protocol.REPO_ROOT / "experiments/issue-62/scripts/HeitanScaleReplay.java"),
        "output_hashes": output_hashes(), "deterministic_regeneration_verified": args.verify_deterministic,
        "rerun_commands": [
            "python3 experiments/issue-82/scripts/finalize_production.py",
            "python3 experiments/issue-82/scripts/run_analysis.py --verify-deterministic",
        ],
    }
    protocol.atomic_write_json(FINAL / "environment.json", environment)
    REPORT.write_text(render_report(analysis), encoding="utf-8")
    print("Issue #82 analysis complete")


if __name__ == "__main__":
    main()
