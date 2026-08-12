#!/usr/bin/env python3
"""Reconstruct and analyze per-site Supply Point value for Issue #39."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
from statistics import mean
from typing import Iterable


SCRIPT = Path(__file__).resolve()
ISSUE_ROOT = SCRIPT.parent.parent
REPO_ROOT = ISSUE_ROOT.parent.parent
RESULTS = ISSUE_ROOT / "results"
RAW = RESULTS / "raw"
CONFIG_PATH = ISSUE_ROOT / "config.json"
README_PATH = ISSUE_ROOT / "README.md"
REPORT_PATH = REPO_ROOT / "experiments" / "issue-39.md"
SUPPLY_POINTS = [f"S{row}{column}" for row in range(5) for column in range(5)]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    values = list(rows)
    if not values:
        raise ValueError(f"refusing to write empty output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    names = fieldnames or list(values[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, lineterminator="\n")
        writer.writeheader()
        writer.writerows(values)


def bool_text(value: bool) -> str:
    return str(value).lower()


def phase(turn: int, config: dict[str, object]) -> str:
    for item in config["turn_phases"]:
        if int(item["first_turn"]) <= turn <= int(item["last_turn"]):
            return str(item["id"])
    raise ValueError(f"turn outside configured phases: {turn}")


def result_status(player: int, winner: int) -> str:
    return "draw" if winner == 0 else "winner" if player == winner else "loser"


def spatial_category(site: str) -> str:
    row, column = int(site[1]), int(site[2])
    boundaries = int(row in (0, 4)) + int(column in (0, 4))
    return "corner" if boundaries == 2 else "edge" if boundaries == 1 else "interior"


def adjacent_objectives(site: str) -> list[str]:
    row, column = int(site[1]), int(site[2])
    return sorted(
        f"O{objective_row}{objective_column}"
        for objective_row in (row - 1, row)
        for objective_column in (column - 1, column)
        if 0 <= objective_row < 4 and 0 <= objective_column < 4
    )


def adjacent_supplies(objective: str) -> list[str]:
    row, column = int(objective[1]), int(objective[2])
    return [
        f"S{row}{column}", f"S{row}{column + 1}",
        f"S{row + 1}{column}", f"S{row + 1}{column + 1}",
    ]


def control_flags(state: int, player: int) -> dict[str, bool]:
    """Return mutually auditable turn-end ownership flags."""
    unsecured = state == player
    secured = state == player + 2
    return {
        "is_unsecured_controlled": unsecured,
        "is_secured": secured,
        "is_controlled_or_secured": unsecured or secured,
    }


def count_control_turns(turn_rows: Iterable[dict[str, object]]) -> dict[str, int]:
    rows = list(turn_rows)
    unsecured = sum(bool(row["is_unsecured_controlled"]) for row in rows)
    secured = sum(bool(row["is_secured"]) for row in rows)
    combined = sum(bool(row["is_controlled_or_secured"]) for row in rows)
    if combined != unsecured + secured:
        raise ValueError("combined Control identity failed")
    return {
        "unsecured_controlled_turns": unsecured,
        "secured_turns": secured,
        "controlled_or_secured_turns": combined,
    }


def validate_definitions(config: dict[str, object]) -> None:
    expected = {
        "version": 1,
        "evaluation_point": "end_of_turn",
        "game_rule_relationship": "A Secured Supply Point is Controlled by its owner.",
        "analysis_policy": "Separate reversible unsecured Control from permanent Secured state, while also retaining their combined ownership/control measure.",
        "is_unsecured_controlled": "state_at_turn_end equals player",
        "is_secured": "state_at_turn_end equals player plus 2",
        "is_controlled_or_secured": "is_unsecured_controlled or is_secured",
        "required_identity": "controlled_or_secured_turns = unsecured_controlled_turns + secured_turns",
        "share_denominator": "all 24 game turns for lifecycle/site summaries and all 8 phase turns for phase summaries",
    }
    if config["control_aggregation"] != expected:
        raise ValueError("Control aggregation definition differs from frozen version 1")
    readme = README_PATH.read_text(encoding="utf-8")
    required = [
        "a Secured Supply Point is Controlled by its owner",
        "reversible unsecured Control from the permanent Secured state",
        "controlled_or_secured_turns = unsecured_controlled_turns + secured_turns",
        "A turn after Securing\nnever contributes to `unsecured_controlled_turns`",
    ]
    for text in required:
        if text not in readme:
            raise ValueError(f"README is missing frozen definition: {text}")


def state_from_counts(p1: int, p2: int) -> int:
    if p1 == 3:
        return 3
    if p2 == 3:
        return 4
    if p1 > p2:
        return 1
    if p2 > p1:
        return 2
    return 0


def average(values: list[float | int]) -> float:
    return round(mean(values), 6) if values else 0.0


def ratio(numerator: int | float, denominator: int | float) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    result = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position + 1
        while end < len(order) and values[order[end]] == values[order[position]]:
            end += 1
        rank = (position + 1 + end) / 2
        for index in order[position:end]:
            result[index] = rank
        position = end
    return result


def pearson(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("correlation inputs must have equal non-zero length")
    left_mean, right_mean = mean(left), mean(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    denominator = math.sqrt(
        sum((x - left_mean) ** 2 for x in left)
        * sum((y - right_mean) ** 2 for y in right)
    )
    return round(numerator / denominator, 6) if denominator else 0.0


def new_unit(experiment: str, game: int, player: int, site: str, winner: int, iteration: int) -> dict[str, object]:
    return {
        "experiment_id": experiment, "iteration_limit": iteration,
        "game_index": game, "player": player,
        "player_result_status": result_status(player, winner),
        "supply_point": site, "spatial_category": spatial_category(site),
        "first_piece_placement_turn": None, "first_control_turn": None,
        "first_unsecured_control_turn": None, "first_securing_turn": None,
        "unsecured_controlled_turns": 0, "secured_turns": 0,
        "controlled_or_secured_turns": 0, "neutral_turns": 0,
        "contested_turns": 0, "own_pieces_placed": 0,
        "opponent_pieces_placed": 0, "supply_usage_turns": 0,
        "objective_placements_supplied": 0, "objectives_supplied": set(),
        "usage_after_first_control": 0, "usage_after_securing": 0,
        "adjacent_live_objectives_at_first_control": None,
        "adjacent_live_objectives_at_securing": None,
        "legal_securable_opportunities": 0, "securing_opportunities_taken": 0,
        "final_state": 0, "final_own_pieces": 0, "final_opponent_pieces": 0,
    }


def lifecycle_row(unit: dict[str, object]) -> dict[str, object]:
    unsecured = int(unit["unsecured_controlled_turns"])
    secured = int(unit["secured_turns"])
    combined = int(unit["controlled_or_secured_turns"])
    if combined != unsecured + secured:
        raise ValueError("lifecycle combined Control identity failed")
    objectives = sorted(unit["objectives_supplied"])
    adjacency = len(adjacent_objectives(str(unit["supply_point"])))
    first_control = unit["first_control_turn"]
    first_securing = unit["first_securing_turn"]
    return {
        "experiment_id": unit["experiment_id"],
        "iteration_limit": unit["iteration_limit"],
        "game_index": unit["game_index"], "player": unit["player"],
        "player_result_status": unit["player_result_status"],
        "supply_point": unit["supply_point"],
        "spatial_category": unit["spatial_category"],
        "first_piece_placement_turn": unit["first_piece_placement_turn"] or "",
        "first_control_turn": first_control or "",
        "first_unsecured_control_turn": unit["first_unsecured_control_turn"] or "",
        "first_securing_turn": first_securing or "",
        "unsecured_controlled_turns": unsecured, "secured_turns": secured,
        "controlled_or_secured_turns": combined,
        "unsecured_controlled_turn_share": ratio(unsecured, 24),
        "secured_turn_share": ratio(secured, 24),
        "controlled_or_secured_turn_share": ratio(combined, 24),
        "neutral_turns": unit["neutral_turns"],
        "contested_turns": unit["contested_turns"],
        "own_pieces_placed": unit["own_pieces_placed"],
        "opponent_pieces_placed": unit["opponent_pieces_placed"],
        "supply_usage_turns": unit["supply_usage_turns"],
        "objective_placements_supplied": unit["objective_placements_supplied"],
        "objective_sites_supplied": ";".join(objectives),
        "objective_sites_supplied_count": len(objectives),
        "adjacent_objective_count": adjacency,
        "objective_coverage": ratio(len(objectives), adjacency),
        "usage_after_first_control": unit["usage_after_first_control"],
        "usage_after_securing": unit["usage_after_securing"],
        "adjacent_live_objectives_at_first_control": unit["adjacent_live_objectives_at_first_control"] if first_control else "",
        "adjacent_live_objectives_at_securing": unit["adjacent_live_objectives_at_securing"] if first_securing else "",
        "legal_securable_opportunities": unit["legal_securable_opportunities"],
        "ever_securable": bool_text(int(unit["legal_securable_opportunities"]) > 0),
        "securing_opportunities_taken": unit["securing_opportunities_taken"],
        "final_state": unit["final_state"],
        "final_own_pieces": unit["final_own_pieces"],
        "final_opponent_pieces": unit["final_opponent_pieces"],
        "final_is_unsecured_controlled": bool_text(int(unit["final_state"]) == int(unit["player"])),
        "final_is_secured": bool_text(int(unit["final_state"]) == int(unit["player"]) + 2),
        "final_is_controlled_or_secured": bool_text(int(unit["final_state"]) in (int(unit["player"]), int(unit["player"]) + 2)),
    }


def summarize_lifecycles(rows: list[dict[str, object]], experiment: str, site: str) -> dict[str, object]:
    selected = [row for row in rows if row["experiment_id"] == experiment and row["supply_point"] == site]
    return summarize_selected(selected, experiment, site)


def summarize_selected(selected: list[dict[str, object]], experiment: str, site: str) -> dict[str, object]:
    if not selected:
        raise ValueError(f"empty lifecycle group: {experiment} {site}")
    player_games = len(selected)
    opportunities = sum(int(row["legal_securable_opportunities"]) for row in selected)
    taken = sum(int(row["securing_opportunities_taken"]) for row in selected)
    ever_securable = sum(row["ever_securable"] == "true" for row in selected)
    secured_units = sum(bool(row["first_securing_turn"]) for row in selected)
    unsecured_turns = sum(int(row["unsecured_controlled_turns"]) for row in selected)
    secured_turns = sum(int(row["secured_turns"]) for row in selected)
    combined_turns = sum(int(row["controlled_or_secured_turns"]) for row in selected)
    if combined_turns != unsecured_turns + secured_turns:
        raise ValueError("site combined Control identity failed")
    return {
        "experiment_id": experiment,
        "iteration_limit": int(selected[0]["iteration_limit"]),
        "supply_point": site, "spatial_category": spatial_category(site),
        "player_games": player_games,
        "player_games_with_placement": sum(int(row["own_pieces_placed"]) > 0 for row in selected),
        "placement_player_game_frequency": ratio(sum(int(row["own_pieces_placed"]) > 0 for row in selected), player_games),
        "pieces_placed": sum(int(row["own_pieces_placed"]) for row in selected),
        "pieces_placed_per_player_game": ratio(sum(int(row["own_pieces_placed"]) for row in selected), player_games),
        "mean_first_placement_turn": average([int(row["first_piece_placement_turn"]) for row in selected if row["first_piece_placement_turn"]]),
        "player_games_with_unsecured_control": sum(bool(row["first_unsecured_control_turn"]) for row in selected),
        "unsecured_control_frequency": ratio(sum(bool(row["first_unsecured_control_turn"]) for row in selected), player_games),
        "mean_first_unsecured_control_turn": average([int(row["first_unsecured_control_turn"]) for row in selected if row["first_unsecured_control_turn"]]),
        "player_games_with_controlled_or_secured": sum(bool(row["first_control_turn"]) for row in selected),
        "controlled_or_secured_frequency": ratio(sum(bool(row["first_control_turn"]) for row in selected), player_games),
        "mean_first_control_turn": average([int(row["first_control_turn"]) for row in selected if row["first_control_turn"]]),
        "unsecured_controlled_turns": unsecured_turns,
        "secured_turns": secured_turns,
        "controlled_or_secured_turns": combined_turns,
        "unsecured_controlled_turn_share": ratio(unsecured_turns, player_games * 24),
        "secured_turn_share": ratio(secured_turns, player_games * 24),
        "controlled_or_secured_turn_share": ratio(combined_turns, player_games * 24),
        "neutral_turn_share": ratio(sum(int(row["neutral_turns"]) for row in selected), player_games * 24),
        "contested_turn_share": ratio(sum(int(row["contested_turns"]) for row in selected), player_games * 24),
        "player_games_secured": secured_units,
        "secured_frequency": ratio(secured_units, player_games),
        "mean_first_securing_turn": average([int(row["first_securing_turn"]) for row in selected if row["first_securing_turn"]]),
        "legal_securable_opportunities": opportunities,
        "securing_opportunities_taken": taken,
        "securing_rate_per_repeated_opportunity": ratio(taken, opportunities),
        "ever_securable_player_sites": ever_securable,
        "ever_securable_eventually_secured": sum(row["ever_securable"] == "true" and bool(row["first_securing_turn"]) for row in selected),
        "eventual_securing_rate_per_ever_securable_player_site": ratio(sum(row["ever_securable"] == "true" and bool(row["first_securing_turn"]) for row in selected), ever_securable),
        "supply_usage_turns": sum(int(row["supply_usage_turns"]) for row in selected),
        "objective_placements_supplied": sum(int(row["objective_placements_supplied"]) for row in selected),
        "objective_placements_supplied_per_player_game": ratio(sum(int(row["objective_placements_supplied"]) for row in selected), player_games),
        "player_games_with_supply_usage": sum(int(row["objective_placements_supplied"]) > 0 for row in selected),
        "supply_usage_player_game_frequency": ratio(sum(int(row["objective_placements_supplied"]) > 0 for row in selected), player_games),
        "mean_objective_sites_supplied": average([int(row["objective_sites_supplied_count"]) for row in selected]),
        "mean_objective_coverage": average([float(row["objective_coverage"]) for row in selected]),
        "usage_after_first_control": sum(int(row["usage_after_first_control"]) for row in selected),
        "usage_after_securing": sum(int(row["usage_after_securing"]) for row in selected),
        "mean_usage_after_securing_per_secured_player_site": ratio(sum(int(row["usage_after_securing"]) for row in selected), secured_units),
        "final_unsecured_control_rate": ratio(sum(row["final_is_unsecured_controlled"] == "true" for row in selected), player_games),
        "final_secured_rate": ratio(sum(row["final_is_secured"] == "true" for row in selected), player_games),
        "final_controlled_or_secured_rate": ratio(sum(row["final_is_controlled_or_secured"] == "true" for row in selected), player_games),
    }


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    validate_definitions(config)
    configured = {item["id"]: item for item in config["source"]["experiments"]}
    expected_ids = set(configured)
    source_paths = {name: REPO_ROOT / config["source"][name] for name in (
        "source_trials", "replay_summary", "placements", "supply_turn_states",
        "objective_turn_states", "securable_opportunities",
    )}
    for path in source_paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)

    replay_rows = [row for row in read_csv(source_paths["replay_summary"]) if row["experiment_id"] in expected_ids]
    expected_games = sum(int(item["games"]) for item in configured.values())
    if len(replay_rows) != expected_games:
        raise ValueError(f"replay count {len(replay_rows)} != {expected_games}")
    winners = {(row["experiment_id"], int(row["game_index"])): int(row["winner"]) for row in replay_rows}
    for row in replay_rows:
        if row["moves"] != "72" or row["turns"] != "24" or row["end_type"] != "NaturalEnd":
            raise ValueError(f"incomplete source replay: {row}")

    source_trial_rows = [row for row in read_csv(source_paths["source_trials"]) if row["experiment_id"] in expected_ids]
    if len(source_trial_rows) != expected_games:
        raise ValueError("source trial index count mismatch")
    for row in source_trial_rows:
        trial = REPO_ROOT / row["trial_file"]
        if not trial.is_file() or sha256(trial) != row["trial_sha256"]:
            raise ValueError(f"source trial hash mismatch: {trial}")
    write_csv(RESULTS / "source-trials.csv", source_trial_rows)

    placements = [row for row in read_csv(source_paths["placements"]) if row["experiment_id"] in expected_ids]
    supply_rows = [row for row in read_csv(source_paths["supply_turn_states"]) if row["experiment_id"] in expected_ids]
    objective_rows = [row for row in read_csv(source_paths["objective_turn_states"]) if row["experiment_id"] in expected_ids]
    opportunities = [row for row in read_csv(source_paths["securable_opportunities"]) if row["experiment_id"] in expected_ids]
    if len(placements) != expected_games * 72 or len(supply_rows) != expected_games * 24 * 25:
        raise ValueError("placement or Supply-turn row count mismatch")
    if len(objective_rows) != expected_games * 24 * 16 or len(opportunities) != expected_games * 24 * 25:
        raise ValueError("Objective-turn or opportunity row count mismatch")

    objective_index = {
        (row["experiment_id"], int(row["game_index"]), int(row["turn_number"]), row["objective"]): row
        for row in objective_rows
    }
    placement_targets: Counter[tuple[str, int, int, int, str]] = Counter()
    source_uses: dict[tuple[str, int, int, int, str], list[str]] = defaultdict(list)
    for row in placements:
        key = row["experiment_id"], int(row["game_index"]), int(row["turn_number"]), int(row["mover"])
        if row["target_type"] == "supply":
            placement_targets[key + (row["target"],)] += 1
        else:
            source = row["supply_source"]
            if source not in adjacent_supplies(row["target"]):
                raise ValueError(f"non-adjacent Supply source: {row}")
            source_uses[key + (source,)].append(row["target"])

    opportunity_index = {
        (row["experiment_id"], int(row["game_index"]), int(row["turn_number"]), int(row["player"]), row["supply_point"]): row
        for row in opportunities
    }
    supply_start_index = {
        (row["experiment_id"], int(row["game_index"]), int(row["turn_number"]), row["supply_point"]): row
        for row in supply_rows
    }
    for key, targets in source_uses.items():
        experiment, game, turn, player, site = key
        source_state = int(supply_start_index[(experiment, game, turn, site)]["state_at_turn_start"])
        if source_state not in (player, player + 2) or len(targets) > 1:
            raise ValueError(f"invalid or repeated Supply use: {key}")

    units: dict[tuple[str, int, int, str], dict[str, object]] = {}
    phase_counts: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    phase_objectives: dict[tuple[str, str, str], set[tuple[int, int, str]]] = defaultdict(set)
    RAW.mkdir(parents=True, exist_ok=True)
    turn_fields = [
        "experiment_id", "iteration_limit", "game_index", "turn_number", "turn_phase",
        "player", "player_result_status", "supply_point", "spatial_category",
        "state_at_turn_start", "state_at_turn_end", "own_pieces_at_turn_end",
        "opponent_pieces_at_turn_end", "is_unsecured_controlled", "is_secured",
        "is_controlled_or_secured", "is_neutral", "is_contested",
        "own_placements_this_turn", "opponent_placements_this_turn",
        "supply_source_uses_this_turn", "objectives_supplied_this_turn",
        "adjacent_live_objectives_at_turn_end", "is_players_turn",
        "is_securable_opportunity", "secured_this_turn",
    ]
    with (RAW / "site-turn-lifecycle.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=turn_fields, lineterminator="\n")
        writer.writeheader()
        for row in supply_rows:
            experiment, game, turn, site = row["experiment_id"], int(row["game_index"]), int(row["turn_number"]), row["supply_point"]
            winner = winners[(experiment, game)]
            iteration = int(configured[experiment]["iteration_limit"])
            mover = int(row["mover"])
            p1_end, p2_end = int(row["p1_pieces_at_turn_end"]), int(row["p2_pieces_at_turn_end"])
            state_end = int(row["state_at_turn_end"])
            if state_end != state_from_counts(p1_end, p2_end):
                raise ValueError(f"Piece-derived Supply state mismatch: {experiment} #{game} turn {turn} {site}")
            live = sum(
                int(objective_index[(experiment, game, turn, objective)]["state_at_turn_end"]) < 3
                for objective in adjacent_objectives(site)
            )
            for player in (1, 2):
                flags = control_flags(state_end, player)
                own, opponent = (p1_end, p2_end) if player == 1 else (p2_end, p1_end)
                own_placements = placement_targets[(experiment, game, turn, player, site)]
                opponent_placements = placement_targets[(experiment, game, turn, 3 - player, site)]
                uses = source_uses[(experiment, game, turn, player, site)]
                opportunity = opportunity_index.get((experiment, game, turn, player, site))
                securable = opportunity is not None and opportunity["securable"] == "true"
                secured_this_turn = int(row["state_at_turn_start"]) < 3 and state_end == player + 2
                output = {
                    "experiment_id": experiment, "iteration_limit": iteration,
                    "game_index": game, "turn_number": turn, "turn_phase": phase(turn, config),
                    "player": player, "player_result_status": result_status(player, winner),
                    "supply_point": site, "spatial_category": spatial_category(site),
                    "state_at_turn_start": row["state_at_turn_start"], "state_at_turn_end": state_end,
                    "own_pieces_at_turn_end": own, "opponent_pieces_at_turn_end": opponent,
                    **{key: bool_text(value) for key, value in flags.items()},
                    "is_neutral": bool_text(state_end == 0),
                    "is_contested": bool_text(p1_end > 0 and p2_end > 0),
                    "own_placements_this_turn": own_placements,
                    "opponent_placements_this_turn": opponent_placements,
                    "supply_source_uses_this_turn": len(uses),
                    "objectives_supplied_this_turn": ";".join(uses),
                    "adjacent_live_objectives_at_turn_end": live,
                    "is_players_turn": bool_text(mover == player),
                    "is_securable_opportunity": bool_text(securable),
                    "secured_this_turn": bool_text(secured_this_turn),
                }
                writer.writerow(output)

                unit_key = experiment, game, player, site
                unit = units.setdefault(unit_key, new_unit(experiment, game, player, site, winner, iteration))
                if own_placements and unit["first_piece_placement_turn"] is None:
                    unit["first_piece_placement_turn"] = turn
                if flags["is_controlled_or_secured"] and unit["first_control_turn"] is None:
                    unit["first_control_turn"] = turn
                    unit["adjacent_live_objectives_at_first_control"] = live
                if flags["is_unsecured_controlled"] and unit["first_unsecured_control_turn"] is None:
                    unit["first_unsecured_control_turn"] = turn
                if secured_this_turn and unit["first_securing_turn"] is None:
                    unit["first_securing_turn"] = turn
                    unit["adjacent_live_objectives_at_securing"] = live
                unit["unsecured_controlled_turns"] += int(flags["is_unsecured_controlled"])
                unit["secured_turns"] += int(flags["is_secured"])
                unit["controlled_or_secured_turns"] += int(flags["is_controlled_or_secured"])
                unit["neutral_turns"] += int(state_end == 0)
                unit["contested_turns"] += int(p1_end > 0 and p2_end > 0)
                unit["own_pieces_placed"] += own_placements
                unit["opponent_pieces_placed"] += opponent_placements
                unit["supply_usage_turns"] += int(bool(uses))
                unit["objective_placements_supplied"] += len(uses)
                unit["objectives_supplied"].update(uses)
                if uses and unit["first_control_turn"] is not None and turn > int(unit["first_control_turn"]):
                    unit["usage_after_first_control"] += len(uses)
                if uses and unit["first_securing_turn"] is not None and turn > int(unit["first_securing_turn"]):
                    unit["usage_after_securing"] += len(uses)
                unit["legal_securable_opportunities"] += int(securable)
                unit["securing_opportunities_taken"] += int(securable and secured_this_turn)
                if turn == 24:
                    unit["final_state"] = state_end
                    unit["final_own_pieces"] = own
                    unit["final_opponent_pieces"] = opponent

                phase_key = experiment, site, phase(turn, config)
                counts = phase_counts[phase_key]
                counts["turn_records"] += 1
                counts["placements"] += own_placements
                counts["unsecured_controlled_turns"] += int(flags["is_unsecured_controlled"])
                counts["secured_turns"] += int(flags["is_secured"])
                counts["controlled_or_secured_turns"] += int(flags["is_controlled_or_secured"])
                counts["neutral_turns"] += int(state_end == 0)
                counts["contested_turns"] += int(p1_end > 0 and p2_end > 0)
                counts["supply_usage_turns"] += int(bool(uses))
                counts["objective_placements_supplied"] += len(uses)
                counts["legal_securable_opportunities"] += int(securable)
                counts["securing_events"] += int(securable and secured_this_turn)
                for objective in uses:
                    phase_objectives[phase_key].add((game, player, objective))

    lifecycle_rows = [lifecycle_row(unit) for unit in units.values()]
    if len(lifecycle_rows) != expected_games * 2 * 25:
        raise ValueError("site lifecycle row count mismatch")
    write_csv(RAW / "site-lifecycle.csv", lifecycle_rows)

    site_rows = [
        summarize_lifecycles(lifecycle_rows, experiment, site)
        for experiment in sorted(expected_ids) for site in SUPPLY_POINTS
    ]
    write_csv(RESULTS / "site-value-summary.csv", site_rows)

    control_fields = [
        "experiment_id", "iteration_limit", "supply_point", "spatial_category", "player_games",
        "player_games_with_unsecured_control", "unsecured_control_frequency",
        "mean_first_unsecured_control_turn", "player_games_with_controlled_or_secured",
        "controlled_or_secured_frequency", "mean_first_control_turn",
        "unsecured_controlled_turns", "secured_turns", "controlled_or_secured_turns",
        "unsecured_controlled_turn_share", "secured_turn_share", "controlled_or_secured_turn_share",
        "neutral_turn_share", "contested_turn_share", "final_unsecured_control_rate",
        "final_secured_rate", "final_controlled_or_secured_rate",
    ]
    write_csv(RESULTS / "site-control-summary.csv", ({key: row[key] for key in control_fields} for row in site_rows), control_fields)
    securing_fields = [
        "experiment_id", "iteration_limit", "supply_point", "spatial_category", "player_games",
        "player_games_secured", "secured_frequency", "mean_first_securing_turn", "secured_turns",
        "secured_turn_share", "legal_securable_opportunities", "securing_opportunities_taken",
        "securing_rate_per_repeated_opportunity", "ever_securable_player_sites",
        "ever_securable_eventually_secured", "eventual_securing_rate_per_ever_securable_player_site",
        "usage_after_securing", "mean_usage_after_securing_per_secured_player_site",
    ]
    write_csv(RESULTS / "site-securing-summary.csv", ({key: row[key] for key in securing_fields} for row in site_rows), securing_fields)
    usage_fields = [
        "experiment_id", "iteration_limit", "supply_point", "spatial_category", "player_games",
        "supply_usage_turns", "objective_placements_supplied", "objective_placements_supplied_per_player_game",
        "player_games_with_supply_usage", "supply_usage_player_game_frequency",
        "mean_objective_sites_supplied", "mean_objective_coverage", "usage_after_first_control",
        "usage_after_securing", "mean_usage_after_securing_per_secured_player_site",
    ]
    write_csv(RESULTS / "site-usage-summary.csv", ({key: row[key] for key in usage_fields} for row in site_rows), usage_fields)

    phase_rows: list[dict[str, object]] = []
    for experiment in sorted(expected_ids):
        for site in SUPPLY_POINTS:
            for phase_id in ("early", "midgame", "late"):
                counts = phase_counts[(experiment, site, phase_id)]
                denominator = counts["turn_records"]
                if counts["controlled_or_secured_turns"] != counts["unsecured_controlled_turns"] + counts["secured_turns"]:
                    raise ValueError("phase combined Control identity failed")
                phase_rows.append({
                    "experiment_id": experiment, "iteration_limit": configured[experiment]["iteration_limit"],
                    "supply_point": site, "spatial_category": spatial_category(site), "turn_phase": phase_id,
                    "player_turn_records": denominator, "pieces_placed": counts["placements"],
                    "unsecured_controlled_turns": counts["unsecured_controlled_turns"],
                    "secured_turns": counts["secured_turns"],
                    "controlled_or_secured_turns": counts["controlled_or_secured_turns"],
                    "unsecured_controlled_turn_share": ratio(counts["unsecured_controlled_turns"], denominator),
                    "secured_turn_share": ratio(counts["secured_turns"], denominator),
                    "controlled_or_secured_turn_share": ratio(counts["controlled_or_secured_turns"], denominator),
                    "neutral_turn_share": ratio(counts["neutral_turns"], denominator),
                    "contested_turn_share": ratio(counts["contested_turns"], denominator),
                    "supply_usage_turns": counts["supply_usage_turns"],
                    "objective_placements_supplied": counts["objective_placements_supplied"],
                    "distinct_game_player_objectives_supplied": len(phase_objectives[(experiment, site, phase_id)]),
                    "legal_securable_opportunities": counts["legal_securable_opportunities"],
                    "securing_events": counts["securing_events"],
                    "securing_rate_per_repeated_opportunity": ratio(counts["securing_events"], counts["legal_securable_opportunities"]),
                })
    write_csv(RESULTS / "site-phase-summary.csv", phase_rows)

    outcome_rows: list[dict[str, object]] = []
    for experiment in sorted(expected_ids):
        for site in SUPPLY_POINTS:
            for status in ("winner", "loser", "draw"):
                selected = [row for row in lifecycle_rows if row["experiment_id"] == experiment and row["supply_point"] == site and row["player_result_status"] == status]
                if not selected:
                    continue
                summary = summarize_selected(selected, experiment, site)
                summary["player_result_status"] = status
                outcome_rows.append(summary)
    write_csv(RESULTS / "winner-loser-site-comparison.csv", outcome_rows)

    by_key = {(row["experiment_id"], row["supply_point"]): row for row in site_rows}
    compare_metrics = [
        "pieces_placed_per_player_game", "unsecured_controlled_turn_share", "secured_turn_share",
        "controlled_or_secured_turn_share", "secured_frequency",
        "objective_placements_supplied_per_player_game", "mean_objective_coverage",
        "securing_rate_per_repeated_opportunity", "eventual_securing_rate_per_ever_securable_player_site",
    ]
    strength_rows: list[dict[str, object]] = []
    for site in SUPPLY_POINTS:
        weak, strong = by_key[("uct-3000-self-play", site)], by_key[("uct-10000-self-play", site)]
        output: dict[str, object] = {"supply_point": site, "spatial_category": spatial_category(site)}
        for metric in compare_metrics:
            output[f"uct_3000_{metric}"] = weak[metric]
            output[f"uct_10000_{metric}"] = strong[metric]
            output[f"delta_10000_minus_3000_{metric}"] = round(float(strong[metric]) - float(weak[metric]), 6)
        strength_rows.append(output)
    write_csv(RESULTS / "search-strength-site-comparison.csv", strength_rows)

    correlations: dict[str, dict[str, float]] = {}
    concentration: dict[str, dict[str, float]] = {}
    s22_comparison: dict[str, dict[str, object]] = {}
    s22_metrics = [
        "pieces_placed_per_player_game", "unsecured_controlled_turn_share", "secured_turn_share",
        "controlled_or_secured_turn_share", "objective_placements_supplied_per_player_game",
        "mean_objective_coverage",
    ]
    for experiment in sorted(expected_ids):
        rows = [by_key[(experiment, site)] for site in SUPPLY_POINTS]
        placement_values = [float(row["pieces_placed_per_player_game"]) for row in rows]
        usage_values = [float(row["objective_placements_supplied_per_player_game"]) for row in rows]
        correlations[experiment] = {
            "placement_usage_pearson": pearson(placement_values, usage_values),
            "placement_usage_spearman": pearson(ranks(placement_values), ranks(usage_values)),
        }
        total_usage = sum(int(row["objective_placements_supplied"]) for row in rows)
        shares = sorted((ratio(int(row["objective_placements_supplied"]), total_usage) for row in rows), reverse=True)
        concentration[experiment] = {
            "usage_top_3_share": round(sum(shares[:3]), 6),
            "usage_top_5_share": round(sum(shares[:5]), 6),
            "usage_hhi": round(sum(value * value for value in shares), 6),
        }
        s22 = by_key[(experiment, "S22")]
        other_sites = [f"S{row}{column}" for row in range(1, 4) for column in range(1, 4) if f"S{row}{column}" != "S22"]
        comparison: dict[str, object] = {}
        for metric in s22_metrics:
            other_mean = average([float(by_key[(experiment, site)][metric]) for site in other_sites])
            comparison[metric] = {
                "s22": s22[metric], "other_interior_8_mean": other_mean,
                "difference": round(float(s22[metric]) - other_mean, 6),
            }
        s22_comparison[experiment] = comparison

    source_file_rows = [
        {"source_role": name, "path": path.relative_to(REPO_ROOT).as_posix(), "sha256": sha256(path)}
        for name, path in source_paths.items()
    ]
    write_csv(RESULTS / "source-files.csv", source_file_rows)
    analysis = {
        "schema_version": 1, "primary_experiment": "uct-10000-self-play",
        "games": expected_games, "new_self_play_games": 0,
        "definitions": {
            "control_aggregation": config["control_aggregation"],
            "neutral_and_contest": config["neutral_and_contest"],
            "objective_coverage": config["objective_coverage"],
            "securable_opportunity": config["securable_opportunity"],
        },
        "placement_usage_correlation": correlations,
        "usage_concentration": concentration,
        "s22_vs_other_interior_8": s22_comparison,
        "integrity": {
            "source_trials_hashed_and_verified": len(source_trial_rows),
            "issue_37_natural_end_replays_reused": len(replay_rows),
            "placement_rows": len(placements), "supply_turn_rows": len(supply_rows),
            "objective_turn_rows": len(objective_rows), "opportunity_rows": len(opportunities),
            "site_turn_lifecycle_rows": len(supply_rows) * 2,
            "site_lifecycle_rows": len(lifecycle_rows),
            "control_identity_verified_lifecycle_rows": len(lifecycle_rows),
            "control_identity_verified_phase_rows": len(phase_rows),
            "objective_supply_sources_verified": sum(len(values) for values in source_uses.values()),
        },
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "analysis.json").write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")
    print(f"analyzed {expected_games} games into {len(lifecycle_rows)} player-site lifecycles")


if __name__ == "__main__":
    main()
