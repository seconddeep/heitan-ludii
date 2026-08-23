#!/usr/bin/env python3
"""Compare frozen 3x3 and 4x4 deep-UCT samples for Issue #83."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import math
from pathlib import Path
import platform
import random
import statistics

import common


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
    radius = z * math.sqrt(
        proportion * (1 - proportion) / total + z * z / (4 * total * total)
    ) / denominator
    return max(0.0, centre - radius), min(1.0, centre + radius)


def bootstrap_difference(
    left: list[int], right: list[int], replicates: int, seed: int
) -> tuple[float, float]:
    if not left or not right:
        raise ValueError("bootstrap samples cannot be empty")
    rng = random.Random(seed)
    estimates = []
    for _ in range(replicates):
        a = sum(rng.choice(left) for _ in left) / len(left)
        b = sum(rng.choice(right) for _ in right) / len(right)
        estimates.append(a - b)
    return percentile(estimates, 0.025), percentile(estimates, 0.975)


def bootstrap_did(
    four_10k: list[int], four_100k: list[int], three_10k: list[int],
    three_100k: list[int], replicates: int, seed: int,
) -> tuple[float, float]:
    groups = (four_10k, four_100k, three_10k, three_100k)
    if any(not group for group in groups):
        raise ValueError("DiD samples cannot be empty")
    rng = random.Random(seed)
    estimates = []
    for _ in range(replicates):
        means = [sum(rng.choice(group) for _ in group) / len(group) for group in groups]
        estimates.append((means[1] - means[0]) - (means[3] - means[2]))
    return percentile(estimates, 0.025), percentile(estimates, 0.975)


def classify(contrasts: list[float] | None, margin: float) -> dict[str, object]:
    if contrasts is None or len(contrasts) != 3 or any(not math.isfinite(value) for value in contrasts):
        return {
            "classification_internal": "unresolved-invalid",
            "classification_report": "未解決",
            "classification_reason": "required contrast estimate is missing or invalid",
            "rule_number": 1,
            "subclassification": "",
        }
    positive = sum(value > margin for value in contrasts)
    negative = sum(value < -margin for value in contrasts)
    similar = sum(abs(value) <= margin for value in contrasts)
    if positive and negative:
        internal, reason, rule, subtype = (
            "non-monotonic", "material positive and negative contrasts both occur", 2, "",
        )
    elif positive >= 2 and negative == 0:
        internal, reason, rule, subtype = (
            "consistent", "at least two material positive contrasts and no material negative contrast", 3,
            "stronger observed P1 advantage on 4x4",
        )
    elif negative >= 2 and positive == 0:
        internal, reason, rule, subtype = (
            "consistent", "at least two material negative contrasts and no material positive contrast", 3,
            "stronger observed P1 advantage on 3x3",
        )
    elif similar == 3:
        internal, reason, rule, subtype = (
            "consistent", "all three contrasts are within the practical-equivalence margin", 3,
            "descriptively similar balance",
        )
    elif positive + negative + similar == 3:
        internal, reason, rule, subtype = (
            "search-dependent", "valid contrasts do not meet the non-monotonic or consistent rules", 4, "",
        )
    else:
        internal, reason, rule, subtype = (
            "unresolved", "defensive classification fallback", 5, "",
        )
    labels = {
        "non-monotonic": "非単調", "consistent": "一貫",
        "search-dependent": "探索依存", "unresolved": "未解決",
    }
    return {
        "classification_internal": internal,
        "classification_report": labels[internal],
        "classification_reason": reason,
        "rule_number": rule,
        "subclassification": subtype,
    }


def verify_pin(record: dict, cache: dict[Path, str]) -> None:
    path = common.REPO_ROOT / str(record["path"])
    if not path.is_file():
        raise ValueError(f"pinned source is missing: {path}")
    actual = cache.setdefault(path, common.sha256(path))
    if actual != record["sha256"] or path.stat().st_size != int(record["bytes"]):
        raise ValueError(f"pinned source changed: {path}")


def verify_locks(config: dict, source: dict) -> None:
    if not common.PROTOCOL_LOCK.is_file() or not common.SOURCE_LOCK.is_file():
        raise ValueError("run freeze_inputs.py before analysis")
    protocol = common.load_json(common.PROTOCOL_LOCK)
    if protocol["config_sha256"] != common.sha256(common.CONFIG_PATH):
        raise ValueError("config differs from protocol lock")
    if protocol["source_lock_sha256"] != common.sha256(common.SOURCE_LOCK):
        raise ValueError("source lock differs from protocol lock")
    scripts = {
        path.name: common.sha256(path)
        for path in sorted(common.SCRIPT.parent.glob("*.py"))
    }
    if protocol.get("analysis_script_hashes") != scripts:
        raise ValueError("analysis scripts differ from protocol lock")
    cache: dict[Path, str] = {}
    for item in source["foundational_files"] + source["baseline_batch_files"]:
        verify_pin(item, cache)
    for game in source["games"]:
        for name in ("result", "result_batch", "trial", "validation", "turn_states"):
            if name in game:
                verify_pin(game[name], cache)
    if source["new_self_play_included"] or config["scope"]["new_self_play"]:
        raise ValueError("new self-play cannot enter Issue #83")


def final_metrics(final_board: str) -> dict[str, int | str]:
    sites = []
    for encoded in final_board.split("|"):
        name, state, p1, p2 = encoded.split(":")
        if name.startswith("O"):
            sites.append((int(state), int(p1), int(p2)))
    secured = [sum(state == value for state, _, _ in sites) for value in (3, 4)]
    advantage = [sum(state == value for state, _, _ in sites) for value in (1, 2)]
    pieces = [sum(site[player] for site in sites) for player in (1, 2)]
    if secured[0] != secured[1]:
        layer = "secured_objectives"
    elif advantage[0] != advantage[1]:
        layer = "advantage_objectives"
    elif pieces[0] != pieces[1]:
        layer = "objective_pieces"
    else:
        layer = "draw"
    return {
        "secured_margin": secured[0] - secured[1],
        "advantage_margin": advantage[0] - advantage[1],
        "objective_piece_margin": pieces[0] - pieces[1],
        "deciding_layer": layer,
    }


def normalize_layer(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_")
    return {
        "secured": "secured_objectives",
        "secured_objectives": "secured_objectives",
        "advantage": "advantage_objectives",
        "advantage_objectives": "advantage_objectives",
        "pieces": "objective_pieces",
        "objective_pieces": "objective_pieces",
        "draw": "draw",
    }.get(normalized, normalized)


def load_games(source: dict) -> list[dict[str, object]]:
    batch_rows: dict[Path, dict[int, dict[str, str]]] = {}
    games = []
    for record in source["games"]:
        if "result" in record:
            rows = common.read_csv(common.REPO_ROOT / record["result"]["path"])
            if len(rows) != 1:
                raise ValueError(f"source result must contain one row: {record['key']}")
            row = rows[0]
        else:
            path = common.REPO_ROOT / record["result_batch"]["path"]
            if path not in batch_rows:
                batch_rows[path] = {
                    int(row["game_index"]): row for row in common.read_csv(path)
                    if row["experiment_id"] == "uct-10000-self-play"
                }
            row = batch_rows[path][int(record["game_index"])]
        metrics = final_metrics(row["final_board"])
        if row.get("p1_secured_objectives", ""):
            metrics = {
                "secured_margin": int(row["p1_secured_objectives"]) - int(row["p2_secured_objectives"]),
                "advantage_margin": int(row["p1_advantage_objectives"]) - int(row["p2_advantage_objectives"]),
                "objective_piece_margin": int(row["p1_objective_pieces"]) - int(row["p2_objective_pieces"]),
                "deciding_layer": normalize_layer(row["deciding_criterion"]),
            }
        game = {
            "board": record["board"], "budget": int(record["budget"]),
            "game_index": int(record["game_index"]), "key": record["key"],
            "winner": int(row["winner"]), "turn_states": record["turn_states"], **metrics,
        }
        games.append(game)
    keys = [(row["board"], row["budget"], row["game_index"]) for row in games]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate board-budget-game key")
    return games


def leader(rows: list[dict[str, str]]) -> int:
    if rows and "point_type" in rows[0]:
        rows = [row for row in rows if row["point_type"] == "objective"]
        states = [int(row["state_at_turn_end"]) for row in rows]
        p1 = [int(row["p1_at_turn_end"]) for row in rows]
        p2 = [int(row["p2_at_turn_end"]) for row in rows]
    else:
        states = [int(row["state_at_turn_end"]) for row in rows]
        p1 = [int(row["p1_pieces_at_turn_end"]) for row in rows]
        p2 = [int(row["p2_pieces_at_turn_end"]) for row in rows]
    scores = (
        (sum(value == 3 for value in states), sum(value == 1 for value in states), sum(p1)),
        (sum(value == 4 for value in states), sum(value == 2 for value in states), sum(p2)),
    )
    return 0 if scores[0] == scores[1] else (1 if scores[0] > scores[1] else 2)


def add_turn_diagnostics(games: list[dict[str, object]], config: dict) -> list[dict[str, object]]:
    shared: dict[Path, dict[tuple[str, int, int], list[dict[str, str]]]] = {}
    diagnostics = []
    for game in games:
        path = common.REPO_ROOT / game["turn_states"]["path"]
        if path not in shared:
            grouped: dict[tuple[str, int, int], list[dict[str, str]]] = defaultdict(list)
            for row in common.read_csv(path):
                experiment = row["experiment_id"]
                grouped[(experiment, int(row["game_index"]), int(row["turn_number"]))].append(row)
            shared[path] = grouped
        if game["board"] == "3x3":
            experiment = f"3x3-uct-{game['budget']}"
        else:
            experiment = f"uct-{game['budget']}-self-play"
        total = int(config["boards"][game["board"]]["total_turns"])
        by_turn = {
            turn: shared[path][(experiment, int(game["game_index"]), turn)]
            for turn in range(1, total + 1)
        }
        leaders = {turn: leader(rows) for turn, rows in by_turn.items()}
        winner = int(game["winner"])
        persistent_turn: int | None = None
        if winner:
            for turn in range(1, total + 1):
                if all(leaders[later] == winner for later in range(turn, total + 1)):
                    persistent_turn = turn
                    break
        for checkpoint in config["secondary"]["checkpoints"]:
            turn = math.ceil(total * float(checkpoint))
            checkpoint_leader = leaders[turn]
            eligible = checkpoint_leader != 0 and winner != 0
            diagnostics.append({
                "board": game["board"], "iteration_limit": game["budget"],
                "game_index": game["game_index"], "checkpoint": checkpoint,
                "checkpoint_turn": turn, "total_turns": total,
                "leader": checkpoint_leader, "winner": winner,
                "eligible": eligible, "late_reversal": eligible and checkpoint_leader != winner,
                "first_persistent_lead_turn": persistent_turn if persistent_turn is not None else "",
                "first_persistent_lead_progress": (
                    persistent_turn / total if persistent_turn is not None else ""
                ),
            })
    return diagnostics


def rounded(value: float | None) -> float | str:
    return "" if value is None else round(value, 6)


def build_outputs(config: dict, source: dict) -> dict:
    games = load_games(source)
    expected = config["source_samples"]
    by_condition: dict[tuple[str, int], list[dict[str, object]]] = {}
    for board in ("3x3", "4x4"):
        for budget in config["primary_budgets"]:
            selected = [row for row in games if row["board"] == board and row["budget"] == budget]
            if len(selected) != int(expected[board][str(budget)]):
                raise ValueError(f"unexpected sample count for {board} {budget}")
            by_condition[(board, budget)] = selected

    balance = []
    binary: dict[tuple[str, int], dict[str, list[int]]] = {}
    for (board, budget), selected in by_condition.items():
        winners = [int(row["winner"]) for row in selected]
        counts = Counter(winners)
        ci = wilson(counts[1], len(winners))
        decisive_ci = wilson(counts[1], counts[1] + counts[2])
        binary[(board, budget)] = {
            "p1": [int(value == 1) for value in winners],
            "draw": [int(value == 0) for value in winners],
        }
        balance.append({
            "board": board, "iteration_limit": budget, "validated_games": len(winners),
            "p1_wins": counts[1], "p2_wins": counts[2], "draws": counts[0],
            "p1_win_rate": rounded(counts[1] / len(winners)),
            "p1_wilson_95_low": rounded(ci[0]), "p1_wilson_95_high": rounded(ci[1]),
            "draw_rate": rounded(counts[0] / len(winners)),
            "decisive_games": counts[1] + counts[2],
            "decisive_p1_share": rounded(counts[1] / (counts[1] + counts[2])),
            "decisive_p1_wilson_95_low": rounded(decisive_ci[0]),
            "decisive_p1_wilson_95_high": rounded(decisive_ci[1]),
        })
    common.write_csv(common.FINAL / "balance-by-board-depth.csv", balance)

    reps = int(config["analysis"]["bootstrap_replicates"])
    seed = int(config["analysis"]["bootstrap_seed"])
    cross = []
    for offset, budget in enumerate(config["primary_budgets"]):
        four, three = binary[("4x4", budget)], binary[("3x3", budget)]
        p1 = sum(four["p1"]) / len(four["p1"]) - sum(three["p1"]) / len(three["p1"])
        draw = sum(four["draw"]) / len(four["draw"]) - sum(three["draw"]) / len(three["draw"])
        p1_ci = bootstrap_difference(four["p1"], three["p1"], reps, seed + offset)
        draw_ci = bootstrap_difference(four["draw"], three["draw"], reps, seed + 100 + offset)
        cross.append({
            "iteration_limit": budget, "contrast_direction": "4x4 - 3x3",
            "games_4x4": len(four["p1"]), "games_3x3": len(three["p1"]),
            "p1_rate_4x4": rounded(sum(four["p1"]) / len(four["p1"])),
            "p1_rate_3x3": rounded(sum(three["p1"]) / len(three["p1"])),
            "p1_rate_difference": rounded(p1),
            "p1_bootstrap_95_low": rounded(p1_ci[0]), "p1_bootstrap_95_high": rounded(p1_ci[1]),
            "draw_rate_difference": rounded(draw),
            "draw_bootstrap_95_low": rounded(draw_ci[0]), "draw_bootstrap_95_high": rounded(draw_ci[1]),
        })
    common.write_csv(common.FINAL / "cross-board-contrasts.csv", cross)

    pairs = [(30000, 10000), (100000, 30000), (100000, 10000)]
    trends = []
    for board_offset, board in enumerate(("3x3", "4x4")):
        for pair_offset, (higher, lower) in enumerate(pairs):
            high, low = binary[(board, higher)], binary[(board, lower)]
            p1 = sum(high["p1"]) / len(high["p1"]) - sum(low["p1"]) / len(low["p1"])
            draw = sum(high["draw"]) / len(high["draw"]) - sum(low["draw"]) / len(low["draw"])
            p1_ci = bootstrap_difference(high["p1"], low["p1"], reps, seed + 200 + board_offset * 10 + pair_offset)
            draw_ci = bootstrap_difference(high["draw"], low["draw"], reps, seed + 300 + board_offset * 10 + pair_offset)
            trends.append({
                "board": board, "contrast": f"{higher // 1000}k - {lower // 1000}k",
                "higher_budget": higher, "lower_budget": lower,
                "p1_rate_change": rounded(p1), "p1_bootstrap_95_low": rounded(p1_ci[0]),
                "p1_bootstrap_95_high": rounded(p1_ci[1]), "draw_rate_change": rounded(draw),
                "draw_bootstrap_95_low": rounded(draw_ci[0]), "draw_bootstrap_95_high": rounded(draw_ci[1]),
            })
    common.write_csv(common.FINAL / "depth-trends.csv", trends)

    values = [binary[(board, budget)]["p1"] for board, budget in (
        ("4x4", 10000), ("4x4", 100000), ("3x3", 10000), ("3x3", 100000)
    )]
    did = ((sum(values[1]) / len(values[1]) - sum(values[0]) / len(values[0]))
           - (sum(values[3]) / len(values[3]) - sum(values[2]) / len(values[2])))
    did_ci = bootstrap_did(*values, reps, seed + 400)
    did_rows = [{
        "contrast": "(4x4_100k - 4x4_10k) - (3x3_100k - 3x3_10k)",
        "estimate": rounded(did), "bootstrap_95_low": rounded(did_ci[0]),
        "bootstrap_95_high": rounded(did_ci[1]), "bootstrap_method": "direct four-sample independent resampling",
    }]
    common.write_csv(common.FINAL / "difference-in-differences.csv", did_rows)

    diagnostics = add_turn_diagnostics(games, config)
    common.write_csv(common.FINAL / "turn-diagnostics.csv", diagnostics)
    late = []
    for board in ("3x3", "4x4"):
        for budget in config["primary_budgets"]:
            for checkpoint in config["secondary"]["checkpoints"]:
                rows = [row for row in diagnostics if row["board"] == board and row["iteration_limit"] == budget and row["checkpoint"] == checkpoint]
                eligible = [row for row in rows if row["eligible"]]
                reversals = sum(bool(row["late_reversal"]) for row in eligible)
                ci = wilson(reversals, len(eligible))
                persistent = [float(row["first_persistent_lead_progress"]) for row in rows if row["first_persistent_lead_progress"] != ""]
                late.append({
                    "board": board, "iteration_limit": budget, "checkpoint": checkpoint,
                    "checkpoint_turn": rows[0]["checkpoint_turn"], "total_turns": rows[0]["total_turns"],
                    "eligible_games": len(eligible), "late_reversals": reversals,
                    "late_reversal_rate": rounded(reversals / len(eligible) if eligible else None),
                    "late_reversal_wilson_95_low": rounded(ci[0]), "late_reversal_wilson_95_high": rounded(ci[1]),
                    "games_with_persistent_lead": len(persistent),
                    "mean_first_persistent_lead_progress": rounded(statistics.mean(persistent) if persistent else None),
                })
    common.write_csv(common.FINAL / "progress-checkpoints.csv", late)

    secondary = []
    for (board, budget), selected in by_condition.items():
        layers = Counter(str(row["deciding_layer"]) for row in selected)
        secondary.append({
            "board": board, "iteration_limit": budget, "validated_games": len(selected),
            "secured_decisions": layers["secured_objectives"],
            "advantage_decisions": layers["advantage_objectives"],
            "objective_piece_decisions": layers["objective_pieces"], "draws": layers["draw"],
            "mean_secured_margin_p1_minus_p2": rounded(statistics.mean(float(row["secured_margin"]) for row in selected)),
            "mean_advantage_margin_p1_minus_p2": rounded(statistics.mean(float(row["advantage_margin"]) for row in selected)),
            "mean_objective_piece_margin_p1_minus_p2": rounded(statistics.mean(float(row["objective_piece_margin"]) for row in selected)),
        })
    common.write_csv(common.FINAL / "secondary-scoring.csv", secondary)

    contrasts = [float(row["p1_rate_difference"]) for row in cross]
    classification = classify(contrasts, float(config["analysis"]["practical_equivalence_margin"]))
    classification.update({
        "practical_equivalence_margin": config["analysis"]["practical_equivalence_margin"],
        "d10k": contrasts[0], "d30k": contrasts[1], "d100k": contrasts[2],
    })
    common.write_csv(common.FINAL / "classification.csv", [classification])

    analysis = {
        "schema_version": 1, "balance": balance, "cross_board_contrasts": cross,
        "depth_trends": trends, "difference_in_differences": did_rows[0],
        "classification": classification, "progress_checkpoints": late,
        "secondary_scoring": secondary,
        "integrity": {
            "source_games": len(games), "new_self_play_included": False,
            "protocol_lock_sha256": common.sha256(common.PROTOCOL_LOCK),
            "source_lock_sha256": common.sha256(common.SOURCE_LOCK),
            "excluded_4x4_100k": source["excluded_4x4_100k"],
        },
        "limitations": [
            "UCT iteration counts are matched nominal budgets, not equal effective search depth.",
            "The three failed 4x4 UCT-100k games may be missing not at random.",
            "Results do not establish causality, optimal play, or game-theoretic convergence.",
        ],
    }
    common.atomic_json(common.FINAL / "analysis.json", analysis)
    common.atomic_json(common.FINAL / "environment.json", {
        "python": platform.python_version(), "platform": platform.platform(),
        "bootstrap_seed": seed, "bootstrap_replicates": reps,
        "config_sha256": common.sha256(common.CONFIG_PATH),
        "protocol_lock_sha256": common.sha256(common.PROTOCOL_LOCK),
        "source_lock_sha256": common.sha256(common.SOURCE_LOCK),
    })
    write_report(analysis)
    write_artifact_manifest()
    return analysis


def percent(value: object) -> str:
    return f"{100 * float(value):.1f}%"


def pp(value: object) -> str:
    return f"{100 * float(value):+.1f} pp"


def write_report(analysis: dict) -> None:
    balance = analysis["balance"]
    cross = analysis["cross_board_contrasts"]
    trends = analysis["depth_trends"]
    classification = analysis["classification"]
    lines = [
        "# Issue 83: 3x3 and 4x4 first-player balance under deep UCT search", "",
        "## Primary balance", "",
        "| Board | UCT | Games | P1 | P2 | Draw | P1 rate | Wilson 95% CI |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in balance:
        lines.append(
            f"| {row['board']} | {int(row['iteration_limit']) // 1000}k | {row['validated_games']} | "
            f"{row['p1_wins']} | {row['p2_wins']} | {row['draws']} | {percent(row['p1_win_rate'])} | "
            f"{percent(row['p1_wilson_95_low'])}–{percent(row['p1_wilson_95_high'])} |"
        )
    lines += ["", "## Cross-board contrasts", "",
              "Positive values mean greater observed P1 advantage on 4x4.", "",
              "| UCT | 4x4 - 3x3 | Bootstrap 95% CI | Games (4x4 / 3x3) |",
              "|---:|---:|---:|---:|"]
    for row in cross:
        lines.append(
            f"| {int(row['iteration_limit']) // 1000}k | {pp(row['p1_rate_difference'])} | "
            f"{pp(row['p1_bootstrap_95_low'])} to {pp(row['p1_bootstrap_95_high'])} | "
            f"{row['games_4x4']} / {row['games_3x3']} |"
        )
    lines += ["", "## Search-depth trends", "",
              "| Board | Contrast | P1-rate change | Bootstrap 95% CI | Draw-rate change |",
              "|---|---|---:|---:|---:|"]
    for row in trends:
        lines.append(
            f"| {row['board']} | {row['contrast']} | {pp(row['p1_rate_change'])} | "
            f"{pp(row['p1_bootstrap_95_low'])} to {pp(row['p1_bootstrap_95_high'])} | "
            f"{pp(row['draw_rate_change'])} |"
        )
    lines += ["", "## Draw behavior", "",
              "| UCT | 3x3 draw rate | 4x4 draw rate | 4x4 - 3x3 | Bootstrap 95% CI |",
              "|---:|---:|---:|---:|---:|"]
    balance_by_key = {(row["board"], row["iteration_limit"]): row for row in balance}
    for row in cross:
        budget = row["iteration_limit"]
        lines.append(
            f"| {int(budget) // 1000}k | {percent(balance_by_key[('3x3', budget)]['draw_rate'])} | "
            f"{percent(balance_by_key[('4x4', budget)]['draw_rate'])} | {pp(row['draw_rate_difference'])} | "
            f"{pp(row['draw_bootstrap_95_low'])} to {pp(row['draw_bootstrap_95_high'])} |"
        )
    did = analysis["difference_in_differences"]
    lines += ["", "## Difference in differences", "",
              f"The directly bootstrapped endpoint DiD is **{pp(did['estimate'])}** "
              f"(95% CI {pp(did['bootstrap_95_low'])} to {pp(did['bootstrap_95_high'])}). "
              "Every replicate independently resamples all four board-budget samples.", "",
              "## Frozen classification", "",
              f"**{classification['classification_report']}** (`{classification['classification_internal']}`): "
              f"{classification['classification_reason']}.", ""]
    if classification["subclassification"]:
        lines += [f"Subtype: **{classification['subclassification']}**.", ""]
    lines += [
        "The practical-equivalence margin is ±5 percentage points. This is a descriptive, mechanically applied "
        "classification; confidence intervals are reported separately and are not treated as equivalence tests.", "",
        "## Progress-based diagnostics", "",
        "Late-reversal checkpoints use end-of-turn state at 75% and 90% progress: turns 14 and 17 on 3x3, "
        "and turns 18 and 22 on 4x4.", "",
        "| Board | UCT | Progress | Turn | Eligible | Reversals | Rate | Wilson 95% CI |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in analysis["progress_checkpoints"]:
        lines.append(
            f"| {row['board']} | {int(row['iteration_limit']) // 1000}k | {percent(row['checkpoint'])} | "
            f"{row['checkpoint_turn']} / {row['total_turns']} | {row['eligible_games']} | {row['late_reversals']} | "
            f"{percent(row['late_reversal_rate'])} | {percent(row['late_reversal_wilson_95_low'])}–"
            f"{percent(row['late_reversal_wilson_95_high'])} |"
        )
    lines += ["", "## Secondary scoring diagnostics", "",
              "| Board | UCT | Secured / Advantage / Pieces / Draw | Mean margins (Secured / Advantage / Pieces) |",
              "|---|---:|---:|---:|"]
    for row in analysis["secondary_scoring"]:
        lines.append(
            f"| {row['board']} | {int(row['iteration_limit']) // 1000}k | "
            f"{row['secured_decisions']} / {row['advantage_decisions']} / {row['objective_piece_decisions']} / {row['draws']} | "
            f"{row['mean_secured_margin_p1_minus_p2']:+.3f} / {row['mean_advantage_margin_p1_minus_p2']:+.3f} / "
            f"{row['mean_objective_piece_margin_p1_minus_p2']:+.3f} |"
        )
    lines += ["",
        "## Limitations", "",
        "The 4x4 UCT-100k result contains 97 validated games. Games 61, 78, and 93 failed during memory-intensive "
        "MCTS and were not replaced. The missing games may be missing not at random.", "",
        "Matched nominal UCT iterations do not imply equal effective depth, branching burden, memory use, or convergence "
        "quality across board sizes. These results do not identify a pure causal board-size effect, establish optimal play, "
        "or demonstrate game-theoretic convergence.", "",
        "## Reproducibility", "",
        "All source manifests, trials, validation artifacts, aggregate inputs, source analyses, seeds, exclusions, and hashes "
        "are pinned by `experiments/issue-83/source-lock.json`. No new self-play is included.",
    ]
    common.REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_artifact_manifest() -> None:
    artifacts = [
        path for path in sorted(common.FINAL.glob("*"))
        if path.is_file() and path.name != "artifact-manifest.json"
    ] + [common.REPORT]
    common.atomic_json(common.FINAL / "artifact-manifest.json", {
        "schema_version": 1,
        "artifacts": {
            path.relative_to(common.REPO_ROOT).as_posix(): common.sha256(path)
            for path in artifacts
        },
    })


def output_hashes() -> dict[str, str]:
    paths = sorted(path for path in common.FINAL.glob("*") if path.is_file()) + [common.REPORT]
    return {path.relative_to(common.REPO_ROOT).as_posix(): common.sha256(path) for path in paths}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-deterministic", action="store_true")
    args = parser.parse_args()
    config = common.load_json(common.CONFIG_PATH)
    source = common.load_json(common.SOURCE_LOCK) if common.SOURCE_LOCK.is_file() else {}
    verify_locks(config, source)
    build_outputs(config, source)
    if args.verify_deterministic:
        before = output_hashes()
        build_outputs(config, source)
        after = output_hashes()
        if before != after:
            raise ValueError("analysis outputs are not deterministic")
    print(f"wrote {len(output_hashes())} deterministic Issue #83 artifacts")


if __name__ == "__main__":
    main()
