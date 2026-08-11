#!/usr/bin/env python3
"""Validate Issue #32 evidence and compare it with the Issue #30 baseline."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from statistics import mean, median


SCRIPT = Path(__file__).resolve()
ISSUE_ROOT = SCRIPT.parent.parent
REPO_ROOT = ISSUE_ROOT.parent.parent
RESULTS = ISSUE_ROOT / "results"
BASELINE_RESULTS = REPO_ROOT / "experiments/issue-30/results"
OBJECTIVES = [f"O{row}{column}" for row in range(4) for column in range(4)]
SUPPLY_POINTS = [f"S{row}{column}" for row in range(5) for column in range(5)]


def read_csv_files(directory: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(directory.glob("*.csv")):
        with path.open(newline="", encoding="utf-8-sig") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty output: {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def wilson(successes: int, total: int) -> tuple[float, float]:
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z / denominator * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return round(100 * (centre - margin), 2), round(100 * (centre + margin), 2)


def parse_board(row: dict[str, str]) -> dict[str, tuple[int, int, int]]:
    board: dict[str, tuple[int, int, int]] = {}
    for entry in row["final_board"].split("|"):
        name, state, p1, p2 = entry.split(":")
        board[name] = (int(state), int(p1), int(p2))
    return board


def average(rows: list[dict[str, str]], field: str) -> float:
    return round(mean(float(row[field]) for row in rows), 3)


def correlation(left: list[float], right: list[float]) -> float:
    left_mean, right_mean = mean(left), mean(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    left_square = sum((a - left_mean) ** 2 for a in left)
    right_square = sum((b - right_mean) ** 2 for b in right)
    if not left_square or not right_square:
        return 0.0
    return round(numerator / math.sqrt(left_square * right_square), 4)


def validate(rows: list[dict[str, str]], expected: dict[str, int]) -> dict[str, int]:
    if not rows:
        raise ValueError("no Issue #32 raw result rows found")
    seeds: set[str] = set()
    game_keys: set[tuple[str, str]] = set()
    for row in rows:
        experiment = row["experiment_id"]
        if experiment not in expected:
            raise ValueError(f"unexpected experiment id: {experiment}")
        if int(row["iteration_limit"]) != expected[experiment]:
            raise ValueError(f"iteration mismatch: {experiment} #{row['game_index']}")
        if row["completed"] != "true" or row["end_type"] != "NaturalEnd":
            raise ValueError(f"non-natural ending: {experiment} #{row['game_index']}")
        if int(row["moves"]) != 72 or int(row["turns"]) != 24:
            raise ValueError(f"move/turn invariant failed: {experiment} #{row['game_index']}")
        if int(row["p1_total_pieces"]) != 36 or int(row["p2_total_pieces"]) != 36:
            raise ValueError(f"piece invariant failed: {experiment} #{row['game_index']}")
        p1_score = 629 * int(row["p1_secured_objectives"]) + 37 * int(row["p1_advantage_objectives"]) + int(row["p1_objective_pieces"])
        p2_score = 629 * int(row["p2_secured_objectives"]) + 37 * int(row["p2_advantage_objectives"]) + int(row["p2_objective_pieces"])
        if (p1_score, p2_score) != (int(row["p1_score"]), int(row["p2_score"])):
            raise ValueError(f"score invariant failed: {experiment} #{row['game_index']}")
        winner = 1 if p1_score > p2_score else 2 if p2_score > p1_score else 0
        if winner != int(row["winner"]):
            raise ValueError(f"winner invariant failed: {experiment} #{row['game_index']}")
        if len(parse_board(row)) != 41:
            raise ValueError(f"board invariant failed: {experiment} #{row['game_index']}")
        seed = row["seed"]
        key = (experiment, row["game_index"])
        if seed in seeds or key in game_keys:
            raise ValueError(f"duplicate seed or game index: {experiment} #{row['game_index']}")
        seeds.add(seed)
        game_keys.add(key)
        trial = REPO_ROOT / row["trial_file"]
        if not trial.is_file():
            raise ValueError(f"trial missing: {trial}")
    config = json.loads((ISSUE_ROOT / "config.json").read_text(encoding="utf-8"))
    environment = json.loads((RESULTS / "environment.json").read_text(encoding="utf-8"))
    override = environment.get("games_override")
    for experiment in config["experiments"]:
        wanted = int(override or experiment["games"])
        actual = sum(row["experiment_id"] == experiment["id"] for row in rows)
        if actual != wanted:
            raise ValueError(f"game count mismatch for {experiment['id']}: {actual} != {wanted}")
    return {
        "completed_natural_end": len(rows), "moves_72_turns_24": len(rows),
        "piece_totals_36_each": len(rows), "scores_verified": len(rows),
        "winners_verified": len(rows), "final_boards_41_sites": len(rows),
        "unique_seeds": len(seeds), "unique_experiment_game_indices": len(game_keys),
        "trial_files_verified": len(rows),
    }


def grouped(rows: list[dict[str, str]]) -> list[tuple[int, str, list[dict[str, str]]]]:
    groups: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        groups.setdefault(row["experiment_id"], []).append(row)
    return sorted((int(values[0]["iteration_limit"]), key, values) for key, values in groups.items())


def main() -> None:
    config = json.loads((ISSUE_ROOT / "config.json").read_text(encoding="utf-8"))
    expected = {item["id"]: int(item["iteration_limit"]) for item in config["experiments"]}
    current = read_csv_files(RESULTS / "raw")
    validation = validate(current, expected)
    baseline = read_csv_files(BASELINE_RESULTS / "raw")
    all_rows = baseline + current

    summaries: list[dict[str, object]] = []
    criteria: list[dict[str, object]] = []
    score_rows: list[dict[str, object]] = []
    site_rows: dict[str, list[dict[str, object]]] = {"objective": [], "supply": []}
    profiles: dict[tuple[int, str], list[float]] = {}
    for iterations, experiment_id, games in grouped(all_rows):
        p1_wins = sum(int(row["winner"]) == 1 for row in games)
        p2_wins = sum(int(row["winner"]) == 2 for row in games)
        draws = len(games) - p1_wins - p2_wins
        p1_low, p1_high = wilson(p1_wins, len(games))
        p2_low, p2_high = wilson(p2_wins, len(games))
        draw_low, draw_high = wilson(draws, len(games))
        summaries.append({
            "experiment_id": experiment_id, "iteration_limit": iterations,
            "games": len(games), "p1_wins": p1_wins, "p2_wins": p2_wins,
            "draws": draws, "p1_win_rate_pct": round(100 * p1_wins / len(games), 2),
            "p2_win_rate_pct": round(100 * p2_wins / len(games), 2),
            "draw_rate_pct": round(100 * draws / len(games), 2),
            "p1_win_rate_95ci_low_pct": p1_low, "p1_win_rate_95ci_high_pct": p1_high,
            "p2_win_rate_95ci_low_pct": p2_low, "p2_win_rate_95ci_high_pct": p2_high,
            "draw_rate_95ci_low_pct": draw_low, "draw_rate_95ci_high_pct": draw_high,
            "first_player_win_margin_pct_points": round(100 * (p1_wins - p2_wins) / len(games), 2),
            "average_p1_secured_objectives": average(games, "p1_secured_objectives"),
            "average_p2_secured_objectives": average(games, "p2_secured_objectives"),
            "average_p1_advantage_objectives": average(games, "p1_advantage_objectives"),
            "average_p2_advantage_objectives": average(games, "p2_advantage_objectives"),
            "average_p1_objective_pieces": average(games, "p1_objective_pieces"),
            "average_p2_objective_pieces": average(games, "p2_objective_pieces"),
            "average_p1_supply_pieces": average(games, "p1_supply_pieces"),
            "average_p2_supply_pieces": average(games, "p2_supply_pieces"),
            "average_p1_secured_supply": average(games, "p1_secured_supply"),
            "average_p2_secured_supply": average(games, "p2_secured_supply"),
        })
        for criterion in ("secured_objectives", "advantage_objectives", "objective_pieces", "draw"):
            count = sum(row["deciding_criterion"] == criterion for row in games)
            criteria.append({"experiment_id": experiment_id, "iteration_limit": iterations,
                             "deciding_criterion": criterion, "games": count,
                             "rate_pct": round(100 * count / len(games), 2)})
        gaps = [abs(int(row["p1_score"]) - int(row["p2_score"])) for row in games]
        secured_ties = sum(row["p1_secured_objectives"] == row["p2_secured_objectives"] for row in games)
        top_two_ties = sum(
            row["p1_secured_objectives"] == row["p2_secured_objectives"]
            and row["p1_advantage_objectives"] == row["p2_advantage_objectives"] for row in games
        )
        score_rows.append({
            "experiment_id": experiment_id, "iteration_limit": iterations,
            "games": len(games), "mean_absolute_score_difference": round(mean(gaps), 3),
            "median_absolute_score_difference": round(median(gaps), 3),
            "secured_objectives_tied_games": secured_ties,
            "secured_objectives_tied_rate_pct": round(100 * secured_ties / len(games), 2),
            "top_two_criteria_tied_games": top_two_ties,
            "top_two_criteria_tied_rate_pct": round(100 * top_two_ties / len(games), 2),
            "draw_games": draws, "draw_rate_pct": round(100 * draws / len(games), 2),
        })
        boards = [parse_board(row) for row in games]
        for point_type, names in (("objective", OBJECTIVES), ("supply", SUPPLY_POINTS)):
            profile: list[float] = []
            for name in names:
                samples = [board[name] for board in boards]
                total_average = round(mean(p1 + p2 for _, p1, p2 in samples), 3)
                profile.append(total_average)
                site_rows[point_type].append({
                    "experiment_id": experiment_id, "iteration_limit": iterations, "point": name,
                    "p1_secured_rate_pct": round(100 * sum(state == 3 for state, _, _ in samples) / len(samples), 2),
                    "p2_secured_rate_pct": round(100 * sum(state == 4 for state, _, _ in samples) / len(samples), 2),
                    "average_p1_pieces": round(mean(p1 for _, p1, _ in samples), 3),
                    "average_p2_pieces": round(mean(p2 for _, _, p2 in samples), 3),
                    "average_total_pieces": total_average,
                })
            profiles[(iterations, point_type)] = profile

    comparisons: list[dict[str, object]] = []
    ordered = [item[0] for item in grouped(all_rows)]
    for lower, higher in zip(ordered, ordered[1:]):
        row: dict[str, object] = {"lower_iteration_limit": lower, "higher_iteration_limit": higher}
        for point_type in ("objective", "supply"):
            left, right = profiles[(lower, point_type)], profiles[(higher, point_type)]
            row[f"{point_type}_usage_profile_correlation"] = correlation(left, right)
            row[f"{point_type}_usage_mean_absolute_change"] = round(mean(abs(a - b) for a, b in zip(left, right)), 4)
        comparisons.append(row)

    RESULTS.mkdir(parents=True, exist_ok=True)
    write_csv(RESULTS / "summary.csv", summaries)
    write_csv(RESULTS / "objectives.csv", site_rows["objective"])
    write_csv(RESULTS / "supply-points.csv", site_rows["supply"])
    write_csv(RESULTS / "deciding-criteria.csv", criteria)
    write_csv(RESULTS / "score-differences.csv", score_rows)
    write_csv(RESULTS / "strength-comparison.csv", comparisons)
    analysis = {
        "games_issue_32": len(current), "games_with_issue_30_baseline": len(all_rows),
        "experiment_groups": len(grouped(all_rows)), "validation": validation,
    }
    (RESULTS / "analysis.json").write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")
    print(f"validated {len(current)} Issue #32 games; analyzed {len(all_rows)} games across {len(grouped(all_rows))} strengths")


if __name__ == "__main__":
    main()
