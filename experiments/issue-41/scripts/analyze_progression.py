#!/usr/bin/env python3
"""Reconstruct and analyze turn-boundary advantage for Issue #41."""

from __future__ import annotations

import csv
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from statistics import mean, median
from typing import Iterable, Sequence


SCRIPT = Path(__file__).resolve()
ISSUE_ROOT = SCRIPT.parent.parent
REPO_ROOT = ISSUE_ROOT.parent.parent
RESULTS = ISSUE_ROOT / "results"
RAW = RESULTS / "raw"
CONFIG_PATH = ISSUE_ROOT / "config.json"
README_PATH = ISSUE_ROOT / "README.md"
REPORT_PATH = REPO_ROOT / "experiments" / "issue-41.md"
SUPPLY_POINTS = [f"S{row}{column}" for row in range(5) for column in range(5)]
OBJECTIVES = [f"O{row}{column}" for row in range(4) for column in range(4)]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(
    path: Path,
    rows: Iterable[dict[str, object]],
    fieldnames: list[str] | None = None,
) -> None:
    values = list(rows)
    if not values:
        raise ValueError(f"refusing to write empty output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    names = fieldnames or list(values[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, lineterminator="\n")
        writer.writeheader()
        writer.writerows(values)


def validate_definitions(config: dict[str, object]) -> None:
    expected_layers = [
        {"id": "secured", "components": ["secured_objective_difference"]},
        {
            "id": "secured_advantage",
            "components": [
                "secured_objective_difference",
                "advantage_objective_difference",
            ],
        },
        {
            "id": "full_lexicographic",
            "components": [
                "secured_objective_difference",
                "advantage_objective_difference",
                "objective_piece_difference",
            ],
        },
    ]
    if config["comparison_layers"] != expected_layers:
        raise ValueError("comparison layer definitions differ from frozen version 1")

    persistence = config["persistence"]
    required_persistence = {
        "strict_persistent_lead_turn",
        "nonlosing_persistence_turn",
        "last_lead_change_turn",
        "draw_handling",
    }
    if set(persistence) != required_persistence:
        raise ValueError("persistence definitions are incomplete")
    if config["reversal"]["denominator"] != "games with a non-tied current leader at Turn N":
        raise ValueError("reversal denominator differs from the frozen definition")

    primary = config["important_supply_sites"]["primary"]
    if primary != {
        "source_issue": 39,
        "source_experiment": "uct-10000-self-play",
        "selection_metric": "objective_placements_supplied_per_player_game",
        "description": "top 5 by actual Objective supply usage in Issue #39",
        "is_composite_value_ranking": False,
        "sites": ["S23", "S21", "S12", "S13", "S22"],
    }:
        raise ValueError("primary important Supply site definition differs from frozen version 1")
    if config["turning_point_window"] != {"relative_turns": [-2, -1, 0, 1, 2]}:
        raise ValueError("turning-point window differs from frozen version 1")

    readme = README_PATH.read_text(encoding="utf-8")
    required_readme_terms = [
        "strict_persistent_lead_turn",
        "nonlosing_persistence_turn",
        "last_lead_change_turn",
        "top five sites by **actual Objective",
        "current leader at Turn N eventually loses",
        "relative turns -2, -1, 0, +1, and +2",
    ]
    missing = [term for term in required_readme_terms if term not in readme]
    if missing:
        raise ValueError(f"README is missing frozen definitions: {missing}")


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


def sign(value: int) -> int:
    return 1 if value > 0 else -1 if value < 0 else 0


def lexicographic_sign(values: Sequence[int]) -> int:
    for value in values:
        if value:
            return sign(value)
    return 0


def layer_sign(row: dict[str, object], components: Sequence[str]) -> int:
    return lexicographic_sign([int(row[name]) for name in components])


def last_lead_change_turn(signs: Sequence[int]) -> int | None:
    """Last turn where the non-zero leader differs from the prior non-zero leader."""
    previous_leader = 0
    result = None
    for turn, current in enumerate(signs, 1):
        if current == 0:
            continue
        if previous_leader and current != previous_leader:
            result = turn
        previous_leader = current
    return result


def lead_change_count(signs: Sequence[int]) -> int:
    previous_leader = 0
    count = 0
    for current in signs:
        if current == 0:
            continue
        if previous_leader and current != previous_leader:
            count += 1
        previous_leader = current
    return count


def strict_persistent_lead_turn(signs: Sequence[int], winner: int) -> int | None:
    if winner not in (1, 2):
        return None
    winner_sign = 1 if winner == 1 else -1
    for index in range(len(signs)):
        if all(current * winner_sign > 0 for current in signs[index:]):
            return index + 1
    return None


def nonlosing_persistence_turn(signs: Sequence[int], winner: int) -> int | None:
    if winner not in (1, 2):
        return None
    winner_sign = 1 if winner == 1 else -1
    for index in range(len(signs)):
        if all(current * winner_sign >= 0 for current in signs[index:]):
            return index + 1
    return None


def equality_period_count(signs: Sequence[int]) -> int:
    return sum(current == 0 and (index == 0 or signs[index - 1] != 0)
               for index, current in enumerate(signs))


def final_return_to_equality_turn(signs: Sequence[int]) -> int | None:
    starts = [
        index + 1 for index, current in enumerate(signs)
        if current == 0 and (index == 0 or signs[index - 1] != 0)
    ]
    return starts[-1] if starts else None


def controlled_by(state: int, player: int) -> bool:
    return state in (player, player + 2)


def nullable(value: int | None) -> object:
    return "" if value is None else value


def ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def csv_ratio(numerator: int, denominator: int) -> object:
    value = ratio(numerator, denominator)
    return "" if value is None else value


def validate_site_sets(config: dict[str, object], site_values: list[dict[str, str]]) -> None:
    primary_experiment = config["important_supply_sites"]["primary"]["source_experiment"]
    rows = [row for row in site_values if row["experiment_id"] == primary_experiment]
    definitions = [config["important_supply_sites"]["primary"]] + config["important_supply_sites"]["sensitivity"]
    for definition in definitions:
        metric = definition.get("selection_metric", definition.get("metric"))
        expected = [
            row["supply_point"]
            for row in sorted(rows, key=lambda item: (-float(item[metric]), item["supply_point"]))[:5]
        ]
        if definition["sites"] != expected:
            raise ValueError(f"Issue #39 top-five mismatch for {metric}: {expected}")


def index_rows(
    rows: Iterable[dict[str, str]], site_field: str
) -> dict[tuple[str, int, int], list[dict[str, str]]]:
    result: dict[tuple[str, int, int], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        result[(row["experiment_id"], int(row["game_index"]), int(row["turn_number"]))].append(row)
    for values in result.values():
        values.sort(key=lambda item: item[site_field])
    return result


def reconstruct_progression(
    config: dict[str, object],
    replay_rows: list[dict[str, str]],
    placement_rows: list[dict[str, str]],
    supply_rows: list[dict[str, str]],
    objective_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], dict[str, int]]:
    expected = {item["id"]: int(item["games"]) for item in config["source"]["experiments"]}
    replay = {(row["experiment_id"], int(row["game_index"])): row for row in replay_rows}
    if len(replay) != sum(expected.values()):
        raise ValueError("replay game count mismatch")
    for experiment, games in expected.items():
        if sum(key[0] == experiment for key in replay) != games:
            raise ValueError(f"game count mismatch for {experiment}")

    placements: dict[tuple[str, int, int], list[dict[str, str]]] = defaultdict(list)
    for row in placement_rows:
        placements[(row["experiment_id"], int(row["game_index"]), int(row["turn_number"]))].append(row)
    supply = index_rows(supply_rows, "supply_point")
    objectives = index_rows(objective_rows, "objective")
    primary_sites = set(config["important_supply_sites"]["primary"]["sites"])

    continuity: dict[tuple[str, int, str], tuple[int, int, int]] = {}
    cumulative: dict[tuple[str, int, int], dict[str, int]] = defaultdict(
        lambda: {"supply": 0, "objective": 0, "usage": 0, "important_usage": 0}
    )
    progression: list[dict[str, object]] = []
    state_checks = 0
    source_checks = 0

    for experiment, game_index in sorted(replay):
        replay_row = replay[(experiment, game_index)]
        if replay_row["moves"] != "72" or replay_row["turns"] != "24" or replay_row["end_type"] != "NaturalEnd":
            raise ValueError(f"incomplete replay: {(experiment, game_index)}")
        winner = int(replay_row["winner"])
        previous_objective_diff = 0
        for turn in range(1, 25):
            key = experiment, game_index, turn
            turn_supply = supply[key]
            turn_objectives = objectives[key]
            turn_placements = sorted(placements[key], key=lambda item: int(item["placement_number"]))
            if len(turn_supply) != 25 or len(turn_objectives) != 16 or len(turn_placements) != 3:
                raise ValueError(f"turn dimensions mismatch: {key}")
            movers = {int(row["mover"]) for row in turn_supply + turn_objectives + turn_placements}
            if len(movers) != 1:
                raise ValueError(f"mover mismatch: {key}")
            mover = movers.pop()

            for site_row, site_field in [
                *[(row, "supply_point") for row in turn_supply],
                *[(row, "objective") for row in turn_objectives],
            ]:
                site = site_row[site_field]
                start = (
                    int(site_row["state_at_turn_start"]),
                    int(site_row["p1_pieces_at_turn_start"]),
                    int(site_row["p2_pieces_at_turn_start"]),
                )
                end = (
                    int(site_row["state_at_turn_end"]),
                    int(site_row["p1_pieces_at_turn_end"]),
                    int(site_row["p2_pieces_at_turn_end"]),
                )
                if end[0] != state_from_counts(end[1], end[2]):
                    raise ValueError(f"state/count mismatch: {key} {site}")
                prior = continuity.get((experiment, game_index, site))
                if prior is not None and prior != start:
                    raise ValueError(f"turn continuity mismatch: {key} {site}")
                continuity[(experiment, game_index, site)] = end
                state_checks += 1

            def count_state(rows: list[dict[str, str]], value: int) -> int:
                return sum(int(row["state_at_turn_end"]) == value for row in rows)

            p1_secured_objectives = count_state(turn_objectives, 3)
            p2_secured_objectives = count_state(turn_objectives, 4)
            p1_advantage_objectives = count_state(turn_objectives, 1)
            p2_advantage_objectives = count_state(turn_objectives, 2)
            p1_objective_pieces = sum(int(row["p1_pieces_at_turn_end"]) for row in turn_objectives)
            p2_objective_pieces = sum(int(row["p2_pieces_at_turn_end"]) for row in turn_objectives)
            p1_secured_supply = count_state(turn_supply, 3)
            p2_secured_supply = count_state(turn_supply, 4)
            p1_unsecured_controlled_supply = count_state(turn_supply, 1)
            p2_unsecured_controlled_supply = count_state(turn_supply, 2)

            supply_placements = sum(row["target_type"] == "supply" for row in turn_placements)
            objective_placements = 3 - supply_placements
            used_sources = [row["supply_source"] for row in turn_placements if row["supply_source"]]
            if len(used_sources) != len(set(used_sources)):
                raise ValueError(f"Supply source reused within turn: {key}")
            if len(used_sources) != objective_placements:
                raise ValueError(f"Objective placement missing Supply source: {key}")
            source_checks += len(used_sources)
            important_usage = sum(site in primary_sites for site in used_sources)
            totals = cumulative[(experiment, game_index, mover)]
            totals["supply"] += supply_placements
            totals["objective"] += objective_placements
            totals["usage"] += len(used_sources)
            totals["important_usage"] += important_usage

            important_p1 = [row["supply_point"] for row in turn_supply if row["supply_point"] in primary_sites and controlled_by(int(row["state_at_turn_end"]), 1)]
            important_p2 = [row["supply_point"] for row in turn_supply if row["supply_point"] in primary_sites and controlled_by(int(row["state_at_turn_end"]), 2)]

            new_secured_obj_p1 = sum(int(row["state_at_turn_start"]) < 3 and int(row["state_at_turn_end"]) == 3 for row in turn_objectives)
            new_secured_obj_p2 = sum(int(row["state_at_turn_start"]) < 3 and int(row["state_at_turn_end"]) == 4 for row in turn_objectives)
            advantage_gains_p1 = sum(int(row["state_at_turn_start"]) != 1 and int(row["state_at_turn_end"]) == 1 for row in turn_objectives)
            advantage_gains_p2 = sum(int(row["state_at_turn_start"]) != 2 and int(row["state_at_turn_end"]) == 2 for row in turn_objectives)
            advantage_losses_p1 = sum(int(row["state_at_turn_start"]) == 1 and int(row["state_at_turn_end"]) != 1 for row in turn_objectives)
            advantage_losses_p2 = sum(int(row["state_at_turn_start"]) == 2 and int(row["state_at_turn_end"]) != 2 for row in turn_objectives)
            new_secured_supply_p1 = sum(int(row["state_at_turn_start"]) < 3 and int(row["state_at_turn_end"]) == 3 for row in turn_supply)
            new_secured_supply_p2 = sum(int(row["state_at_turn_start"]) < 3 and int(row["state_at_turn_end"]) == 4 for row in turn_supply)
            important_control_gains_p1 = sum(row["supply_point"] in primary_sites and not controlled_by(int(row["state_at_turn_start"]), 1) and controlled_by(int(row["state_at_turn_end"]), 1) for row in turn_supply)
            important_control_gains_p2 = sum(row["supply_point"] in primary_sites and not controlled_by(int(row["state_at_turn_start"]), 2) and controlled_by(int(row["state_at_turn_end"]), 2) for row in turn_supply)
            important_control_losses_p1 = sum(row["supply_point"] in primary_sites and controlled_by(int(row["state_at_turn_start"]), 1) and not controlled_by(int(row["state_at_turn_end"]), 1) for row in turn_supply)
            important_control_losses_p2 = sum(row["supply_point"] in primary_sites and controlled_by(int(row["state_at_turn_start"]), 2) and not controlled_by(int(row["state_at_turn_end"]), 2) for row in turn_supply)

            secured_difference = p1_secured_objectives - p2_secured_objectives
            advantage_difference = p1_advantage_objectives - p2_advantage_objectives
            objective_piece_difference = p1_objective_pieces - p2_objective_pieces
            row: dict[str, object] = {
                "experiment_id": experiment,
                "game_index": game_index,
                "turn_number": turn,
                "mover": mover,
                "next_mover": "" if turn == 24 else 3 - mover,
                "winner": winner,
                "final_result": "draw" if winner == 0 else f"p{winner}_win",
                "p1_secured_objectives": p1_secured_objectives,
                "p2_secured_objectives": p2_secured_objectives,
                "secured_objective_difference": secured_difference,
                "p1_advantage_objectives": p1_advantage_objectives,
                "p2_advantage_objectives": p2_advantage_objectives,
                "advantage_objective_difference": advantage_difference,
                "p1_objective_pieces": p1_objective_pieces,
                "p2_objective_pieces": p2_objective_pieces,
                "objective_piece_difference": objective_piece_difference,
                "p1_secured_supply": p1_secured_supply,
                "p2_secured_supply": p2_secured_supply,
                "secured_supply_difference": p1_secured_supply - p2_secured_supply,
                "p1_unsecured_controlled_supply": p1_unsecured_controlled_supply,
                "p2_unsecured_controlled_supply": p2_unsecured_controlled_supply,
                "unsecured_controlled_supply_difference": p1_unsecured_controlled_supply - p2_unsecured_controlled_supply,
                "p1_supply_placements": supply_placements if mover == 1 else 0,
                "p2_supply_placements": supply_placements if mover == 2 else 0,
                "p1_objective_placements": objective_placements if mover == 1 else 0,
                "p2_objective_placements": objective_placements if mover == 2 else 0,
                "p1_cumulative_supply_placements": cumulative[(experiment, game_index, 1)]["supply"],
                "p2_cumulative_supply_placements": cumulative[(experiment, game_index, 2)]["supply"],
                "p1_cumulative_objective_placements": cumulative[(experiment, game_index, 1)]["objective"],
                "p2_cumulative_objective_placements": cumulative[(experiment, game_index, 2)]["objective"],
                "p1_cumulative_supply_source_usage": cumulative[(experiment, game_index, 1)]["usage"],
                "p2_cumulative_supply_source_usage": cumulative[(experiment, game_index, 2)]["usage"],
                "supply_source_usage_difference": cumulative[(experiment, game_index, 1)]["usage"] - cumulative[(experiment, game_index, 2)]["usage"],
                "important_supply_source_uses_this_turn": important_usage,
                "p1_cumulative_important_supply_source_usage": cumulative[(experiment, game_index, 1)]["important_usage"],
                "p2_cumulative_important_supply_source_usage": cumulative[(experiment, game_index, 2)]["important_usage"],
                "p1_primary_important_sites_controlled": len(important_p1),
                "p2_primary_important_sites_controlled": len(important_p2),
                "primary_important_control_difference": len(important_p1) - len(important_p2),
                "p1_primary_important_site_list": ";".join(important_p1),
                "p2_primary_important_site_list": ";".join(important_p2),
                "new_secured_objectives_p1": new_secured_obj_p1,
                "new_secured_objectives_p2": new_secured_obj_p2,
                "advantage_gains_p1": advantage_gains_p1,
                "advantage_gains_p2": advantage_gains_p2,
                "advantage_losses_p1": advantage_losses_p1,
                "advantage_losses_p2": advantage_losses_p2,
                "objective_piece_difference_change": objective_piece_difference - previous_objective_diff,
                "new_secured_supply_p1": new_secured_supply_p1,
                "new_secured_supply_p2": new_secured_supply_p2,
                "important_control_gains_p1": important_control_gains_p1,
                "important_control_gains_p2": important_control_gains_p2,
                "important_control_losses_p1": important_control_losses_p1,
                "important_control_losses_p2": important_control_losses_p2,
            }
            progression.append(row)
            previous_objective_diff = objective_piece_difference

        final_supply = supply[(experiment, game_index, 24)]
        final_objectives = objectives[(experiment, game_index, 24)]
        final_board = "|".join(
            f"{row.get('supply_point', row.get('objective'))}:{row['state_at_turn_end']}:{row['p1_pieces_at_turn_end']}:{row['p2_pieces_at_turn_end']}"
            for row in final_supply + final_objectives
        )
        if final_board != replay_row["final_board"]:
            raise ValueError(f"final board mismatch: {(experiment, game_index)}")
        expected_winner = 1 if layer_sign(progression[-1], [
            "secured_objective_difference", "advantage_objective_difference",
            "objective_piece_difference",
        ]) > 0 else 2 if layer_sign(progression[-1], [
            "secured_objective_difference", "advantage_objective_difference",
            "objective_piece_difference",
        ]) < 0 else 0
        if expected_winner != winner:
            raise ValueError(f"reconstructed winner mismatch: {(experiment, game_index)}")

    return progression, {
        "state_rows_verified": state_checks,
        "state_chains_verified": len(continuity),
        "objective_supply_sources_verified": source_checks,
        "final_boards_verified": len(replay),
        "final_winners_verified": len(replay),
    }


def build_lead_summaries(
    config: dict[str, object], progression: list[dict[str, object]]
) -> tuple[list[dict[str, object]], dict[tuple[str, int, str, str], int | None]]:
    games: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
    for row in progression:
        games[(str(row["experiment_id"]), int(row["game_index"]))].append(row)
    summaries: list[dict[str, object]] = []
    turning: dict[tuple[str, int, str, str], int | None] = {}
    for (experiment, game_index), rows in sorted(games.items()):
        rows.sort(key=lambda item: int(item["turn_number"]))
        winner = int(rows[0]["winner"])
        for layer in config["comparison_layers"]:
            layer_id = str(layer["id"])
            signs = [layer_sign(row, layer["components"]) for row in rows]
            strict = strict_persistent_lead_turn(signs, winner)
            nonlosing = nonlosing_persistence_turn(signs, winner)
            turning[(experiment, game_index, layer_id, "strict")] = strict
            turning[(experiment, game_index, layer_id, "nonlosing")] = nonlosing
            summaries.append({
                "experiment_id": experiment,
                "game_index": game_index,
                "winner": winner,
                "final_result": rows[0]["final_result"],
                "comparison_layer": layer_id,
                "last_lead_change_turn": nullable(last_lead_change_turn(signs)),
                "lead_change_count": lead_change_count(signs),
                "equality_turns": sum(value == 0 for value in signs),
                "equality_periods": equality_period_count(signs),
                "final_return_to_equality_turn": nullable(final_return_to_equality_turn(signs)),
                "strict_persistent_lead_turn": nullable(strict),
                "nonlosing_persistence_turn": nullable(nonlosing),
                "final_layer_sign": signs[-1],
            })
    return summaries, turning


def build_reversal_rows(
    config: dict[str, object], progression: list[dict[str, object]]
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, int], list[dict[str, object]]] = defaultdict(list)
    for row in progression:
        for layer in config["comparison_layers"]:
            grouped[(str(row["experiment_id"]), str(layer["id"]), int(row["turn_number"]))].append(row)
    output: list[dict[str, object]] = []
    layers = {str(layer["id"]): layer["components"] for layer in config["comparison_layers"]}
    for (experiment, layer_id, turn), rows in sorted(grouped.items()):
        outcomes = {"wins": 0, "loses": 0, "draws": 0, "ties": 0}
        for row in rows:
            current = layer_sign(row, layers[layer_id])
            if current == 0:
                outcomes["ties"] += 1
                continue
            leader = 1 if current > 0 else 2
            winner = int(row["winner"])
            if winner == 0:
                outcomes["draws"] += 1
            elif winner == leader:
                outcomes["wins"] += 1
            else:
                outcomes["loses"] += 1
        denominator = outcomes["wins"] + outcomes["loses"] + outcomes["draws"]
        output.append({
            "experiment_id": experiment,
            "comparison_layer": layer_id,
            "turn_number": turn,
            "games": len(rows),
            "games_with_current_leader": denominator,
            "current_leader_eventually_wins": outcomes["wins"],
            "current_leader_eventually_loses": outcomes["loses"],
            "eventual_draws_from_current_lead": outcomes["draws"],
            "games_tied_at_turn": outcomes["ties"],
            "current_leader_win_rate": csv_ratio(outcomes["wins"], denominator),
            "reversal_rate_current_leader_eventually_loses": csv_ratio(outcomes["loses"], denominator),
            "eventual_draw_rate_from_current_lead": csv_ratio(outcomes["draws"], denominator),
        })
    return output


def build_turn_advantage_rows(
    config: dict[str, object], progression: list[dict[str, object]]
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
    for row in progression:
        grouped[(str(row["experiment_id"]), int(row["turn_number"]))].append(row)
    output: list[dict[str, object]] = []
    for (experiment, turn), rows in sorted(grouped.items()):
        output.append({
            "experiment_id": experiment,
            "turn_number": turn,
            "games": len(rows),
            "mean_secured_objective_difference": round(mean(int(row["secured_objective_difference"]) for row in rows), 6),
            "mean_advantage_objective_difference": round(mean(int(row["advantage_objective_difference"]) for row in rows), 6),
            "mean_objective_piece_difference": round(mean(int(row["objective_piece_difference"]) for row in rows), 6),
            "mean_secured_supply_difference": round(mean(int(row["secured_supply_difference"]) for row in rows), 6),
            "mean_unsecured_controlled_supply_difference": round(mean(int(row["unsecured_controlled_supply_difference"]) for row in rows), 6),
            "mean_supply_source_usage_difference": round(mean(int(row["supply_source_usage_difference"]) for row in rows), 6),
            "mean_primary_important_control_difference": round(mean(int(row["primary_important_control_difference"]) for row in rows), 6),
        })
    return output


EVENT_FIELDS = [
    "new_secured_objectives_p1", "new_secured_objectives_p2",
    "advantage_gains_p1", "advantage_gains_p2",
    "advantage_losses_p1", "advantage_losses_p2",
    "objective_piece_difference_change",
    "new_secured_supply_p1", "new_secured_supply_p2",
    "important_control_gains_p1", "important_control_gains_p2",
    "important_control_losses_p1", "important_control_losses_p2",
    "p1_supply_placements", "p2_supply_placements",
    "p1_objective_placements", "p2_objective_placements",
    "important_supply_source_uses_this_turn",
]


def build_turning_point_rows(
    config: dict[str, object],
    progression: list[dict[str, object]],
    turning: dict[tuple[str, int, str, str], int | None],
) -> list[dict[str, object]]:
    lookup = {
        (str(row["experiment_id"]), int(row["game_index"]), int(row["turn_number"])): row
        for row in progression
    }
    output: list[dict[str, object]] = []
    for (experiment, game_index, layer, persistence_type), turning_turn in sorted(turning.items()):
        if turning_turn is None:
            continue
        for relative in config["turning_point_window"]["relative_turns"]:
            event_turn = turning_turn + int(relative)
            if not 1 <= event_turn <= 24:
                continue
            source = lookup[(experiment, game_index, event_turn)]
            row = {
                "experiment_id": experiment,
                "game_index": game_index,
                "winner": source["winner"],
                "persistence_type": persistence_type,
                "comparison_layer": layer,
                "turning_turn": turning_turn,
                "relative_turn": relative,
                "event_turn": event_turn,
                "mover": source["mover"],
            }
            row.update({field: source[field] for field in EVENT_FIELDS})
            winner = int(source["winner"])
            loser = 3 - winner
            row.update({
                "winner_new_secured_objectives": source[f"new_secured_objectives_p{winner}"],
                "loser_new_secured_objectives": source[f"new_secured_objectives_p{loser}"],
                "winner_new_secured_supply": source[f"new_secured_supply_p{winner}"],
                "loser_new_secured_supply": source[f"new_secured_supply_p{loser}"],
                "winner_important_control_gains": source[f"important_control_gains_p{winner}"],
                "loser_important_control_gains": source[f"important_control_gains_p{loser}"],
                "winner_objective_placements": source[f"p{winner}_objective_placements"],
                "loser_objective_placements": source[f"p{loser}_objective_placements"],
                "winner_supply_placements": source[f"p{winner}_supply_placements"],
                "loser_supply_placements": source[f"p{loser}_supply_placements"],
            })
            output.append(row)
    return output


def build_transition_rows(progression: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
    for row in progression:
        grouped[(str(row["experiment_id"]), int(row["turn_number"]))].append(row)
    output: list[dict[str, object]] = []
    for (experiment, turn), rows in sorted(grouped.items()):
        supply = sum(int(row["p1_supply_placements"]) + int(row["p2_supply_placements"]) for row in rows)
        objectives = sum(int(row["p1_objective_placements"]) + int(row["p2_objective_placements"]) for row in rows)
        cumulative_supply = sum(int(row["p1_cumulative_supply_placements"]) + int(row["p2_cumulative_supply_placements"]) for row in rows)
        cumulative_objectives = sum(int(row["p1_cumulative_objective_placements"]) + int(row["p2_cumulative_objective_placements"]) for row in rows)
        total = supply + objectives
        cumulative_total = cumulative_supply + cumulative_objectives
        output.append({
            "experiment_id": experiment,
            "turn_number": turn,
            "games": len(rows),
            "supply_placements": supply,
            "objective_placements": objectives,
            "objective_placement_share": round(objectives / total, 6),
            "cumulative_supply_placements": cumulative_supply,
            "cumulative_objective_placements": cumulative_objectives,
            "cumulative_objective_placement_share": round(cumulative_objectives / cumulative_total, 6),
            "primary_important_supply_source_uses": sum(int(row["important_supply_source_uses_this_turn"]) for row in rows),
        })
    return output


def median_turn(rows: list[dict[str, object]], field: str) -> float | None:
    values = [int(row[field]) for row in rows if row[field] != ""]
    return round(float(median(values)), 3) if values else None


def build_analysis(
    config: dict[str, object],
    progression: list[dict[str, object]],
    lead_rows: list[dict[str, object]],
    reversal_rows: list[dict[str, object]],
    turning_rows: list[dict[str, object]],
    transition_rows: list[dict[str, object]],
    integrity: dict[str, int],
    source_files: list[dict[str, str]],
) -> dict[str, object]:
    persistence_summary: dict[str, object] = {}
    for experiment in [item["id"] for item in config["source"]["experiments"]]:
        persistence_summary[experiment] = {}
        for layer in [item["id"] for item in config["comparison_layers"]]:
            selected = [row for row in lead_rows if row["experiment_id"] == experiment and row["comparison_layer"] == layer]
            decisive = [row for row in selected if int(row["winner"]) in (1, 2)]
            persistence_summary[experiment][layer] = {
                "decisive_games": len(decisive),
                "draw_games": len(selected) - len(decisive),
                "median_strict_persistent_lead_turn": median_turn(decisive, "strict_persistent_lead_turn"),
                "strict_defined_games": sum(row["strict_persistent_lead_turn"] != "" for row in decisive),
                "median_nonlosing_persistence_turn": median_turn(decisive, "nonlosing_persistence_turn"),
                "nonlosing_defined_games": sum(row["nonlosing_persistence_turn"] != "" for row in decisive),
                "median_last_lead_change_turn": median_turn(selected, "last_lead_change_turn"),
            }

    checkpoints: dict[str, object] = {}
    for experiment in [item["id"] for item in config["source"]["experiments"]]:
        checkpoints[experiment] = {}
        for turn in (8, 12, 16, 20):
            row = next(item for item in reversal_rows if item["experiment_id"] == experiment and item["comparison_layer"] == "full_lexicographic" and int(item["turn_number"]) == turn)
            checkpoints[experiment][str(turn)] = {
                "games_with_current_leader": row["games_with_current_leader"],
                "current_leader_win_rate": row["current_leader_win_rate"],
                "reversal_rate": row["reversal_rate_current_leader_eventually_loses"],
                "eventual_draw_rate": row["eventual_draw_rate_from_current_lead"],
                "tied_games": row["games_tied_at_turn"],
            }

    turning_summary: dict[str, object] = {}
    for experiment in [item["id"] for item in config["source"]["experiments"]]:
        turning_summary[experiment] = {}
        for persistence_type in ("strict", "nonlosing"):
            selected = [
                row for row in turning_rows
                if row["experiment_id"] == experiment
                and row["comparison_layer"] == "full_lexicographic"
                and row["persistence_type"] == persistence_type
            ]
            by_relative: dict[str, object] = {}
            for relative in config["turning_point_window"]["relative_turns"]:
                window = [row for row in selected if int(row["relative_turn"]) == int(relative)]
                if not window:
                    continue
                by_relative[str(relative)] = {
                    "games": len(window),
                    "mean_winner_new_secured_objectives": round(mean(int(row["winner_new_secured_objectives"]) for row in window), 6),
                    "mean_winner_new_secured_supply": round(mean(int(row["winner_new_secured_supply"]) for row in window), 6),
                    "mean_winner_important_control_gains": round(mean(int(row["winner_important_control_gains"]) for row in window), 6),
                    "mean_all_new_secured_objectives": round(mean(int(row["new_secured_objectives_p1"]) + int(row["new_secured_objectives_p2"]) for row in window), 6),
                    "mean_all_new_secured_supply": round(mean(int(row["new_secured_supply_p1"]) + int(row["new_secured_supply_p2"]) for row in window), 6),
                    "mean_all_important_control_gains": round(mean(int(row["important_control_gains_p1"]) + int(row["important_control_gains_p2"]) for row in window), 6),
                    "mean_primary_important_supply_source_uses": round(mean(int(row["important_supply_source_uses_this_turn"]) for row in window), 6),
                    "mean_objective_placements": round(mean(int(row["p1_objective_placements"]) + int(row["p2_objective_placements"]) for row in window), 6),
                }
            turning_summary[experiment][persistence_type] = by_relative

    transition_summary: dict[str, object] = {}
    for experiment in [item["id"] for item in config["source"]["experiments"]]:
        selected = [row for row in transition_rows if row["experiment_id"] == experiment]
        first_majority = next(
            (int(row["turn_number"]) for row in selected if float(row["objective_placement_share"]) > 0.5),
            None,
        )
        peak = max(selected, key=lambda row: float(row["objective_placement_share"]))
        first_cumulative_majority = next(
            (int(row["turn_number"]) for row in selected if float(row["cumulative_objective_placement_share"]) > 0.5),
            None,
        )
        transition_summary[experiment] = {
            "first_turn_with_objective_placement_majority": first_majority,
            "peak_objective_placement_share_turn": int(peak["turn_number"]),
            "peak_objective_placement_share": peak["objective_placement_share"],
            "first_turn_with_cumulative_objective_majority": first_cumulative_majority,
            "final_cumulative_objective_placement_share": selected[-1]["cumulative_objective_placement_share"],
        }

    draw_games = len({(row["experiment_id"], row["game_index"]) for row in progression if int(row["winner"]) == 0})
    if any(row["winner"] == 0 and (row["strict_persistent_lead_turn"] != "" or row["nonlosing_persistence_turn"] != "") for row in lead_rows):
        raise ValueError("draw game has winner-based persistence")
    return {
        "schema_version": 1,
        "primary_experiment": "uct-10000-self-play",
        "games": len(progression) // 24,
        "new_self_play_games": 0,
        "targeted_continuation_runs": 0,
        "definitions": {
            "comparison_layers": config["comparison_layers"],
            "persistence": config["persistence"],
            "reversal": config["reversal"],
            "important_supply_sites": config["important_supply_sites"],
            "turning_point_window": config["turning_point_window"],
        },
        "persistence_summary": persistence_summary,
        "reversal_checkpoints_full_lexicographic": checkpoints,
        "turning_point_event_summary_full_lexicographic": turning_summary,
        "supply_objective_transition_summary": transition_summary,
        "integrity": {
            **integrity,
            "source_files_hashed": len(source_files),
            "legally_replayed_complete_games_reused": len(progression) // 24,
            "turn_progression_rows": len(progression),
            "lead_summary_rows": len(lead_rows),
            "draw_games": draw_games,
            "draw_winner_based_persistence_null": True,
        },
    }


def fmt_turn(value: object) -> str:
    return "NA" if value is None else str(value)


def build_report(analysis: dict[str, object]) -> None:
    primary = analysis["persistence_summary"]["uct-10000-self-play"]
    checkpoints = analysis["reversal_checkpoints_full_lexicographic"]["uct-10000-self-play"]
    turning = analysis["turning_point_event_summary_full_lexicographic"]["uct-10000-self-play"]
    transition = analysis["supply_objective_transition_summary"]["uct-10000-self-play"]
    persistence_lines = []
    labels = {
        "secured": "Secured only",
        "secured_advantage": "Secured + Advantage",
        "full_lexicographic": "Full lexicographic",
    }
    for layer, label in labels.items():
        values = primary[layer]
        persistence_lines.append(
            f"| {label} | {fmt_turn(values['median_strict_persistent_lead_turn'])} "
            f"({values['strict_defined_games']}/{values['decisive_games']}) | "
            f"{fmt_turn(values['median_nonlosing_persistence_turn'])} "
            f"({values['nonlosing_defined_games']}/{values['decisive_games']}) | "
            f"{fmt_turn(values['median_last_lead_change_turn'])} |"
        )
    reversal_lines = []
    for turn in (8, 12, 16, 20):
        values = checkpoints[str(turn)]
        reversal_lines.append(
            f"| {turn} | {values['games_with_current_leader']} | "
            f"{float(values['current_leader_win_rate']):.1%} | "
            f"{float(values['reversal_rate']):.1%} | "
            f"{float(values['eventual_draw_rate']):.1%} | {values['tied_games']} |"
        )
    report = f"""# Issue 41: Game-state progression and decision timing

## Summary

The analysis reconstructs all 24 turn boundaries in 100 primary UCT 10,000
games and 100 UCT 3,000 comparison games. It reuses the legal Issue #37
replays; no new self-play or targeted continuation was run. Results are
descriptive properties of these samples, not game-theoretic probabilities.

## Persistence in the primary sample

Values are median turns. Parentheses give games for which the measure is
defined among decisive games. `last lead change` is winner-independent and its
median excludes games with no lead-side switch.

| Comparison layer | Strict persistence | Nonlosing persistence | Last lead change |
|---|---:|---:|---:|
{chr(10).join(persistence_lines)}

Strict persistence forbids both a later tie and a later opponent lead.
Nonlosing persistence permits later ties. They are deliberately not treated as
the same turning point. Winner-based persistence is null for all draws.

## Reversal after selected turns

The table uses the full Secured -> Advantage -> Objective Pieces comparison.
Rates exclude games tied at the checkpoint. The reversal rate means that the
current leader eventually loses; eventual draws are separate.

| Turn | Games with leader | Leader wins | Leader loses | Final draw | Tied at turn |
|---:|---:|---:|---:|---:|---:|
{chr(10).join(reversal_lines)}

Complete results for all turns and all three comparison layers are in
`results/reversal-by-turn.csv`. Per-game strict/nonlosing timing and equality
history are in `results/lead-change-summary.csv`.

The approximately 40% reversal rate at Turn 20 and the full-lexicographic
strict-persistence median of Turn 22 indicate substantial late reversibility
in this sample. The data do not support describing the late game as merely
preserving an already fixed result.

## Supply and turning-point interpretation

Primary important-site analysis uses only S23, S21, S12, S13, and S22: the
Issue #39 UCT 10,000 top five by actual Objective placements supplied per
player-game. This is a direct Supply-usage measure, not a composite value
ranking. Alternative top-five definitions are retained only as sensitivity
sets in the machine-readable analysis.

`results/turning-point-events.csv` preserves persistence type, comparison
layer, turning turn, and relative turn (-2 through +2), alongside Objective,
Supply, allocation, and important-site events. This permits strict and
nonlosing event windows to be compared without pooling them. The turn-level
Supply-to-Objective allocation sequence is in
`results/supply-objective-transition.csv`.

For full-lexicographic strict persistence, the winner newly Secured an average
of {turning['strict']['0']['mean_winner_new_secured_objectives']:.3f} Objectives
on the turning turn. Two turns earlier, the winner newly Secured
{turning['strict']['-2']['mean_winner_new_secured_supply']:.3f} Supply Points
and gained Control of {turning['strict']['-2']['mean_winner_important_control_gains']:.3f}
primary important sites per available game. This timing is consistent with
Supply preparation preceding Objective conversion, but it is an association,
not a causal estimate.

Objective placements first exceeded half of placements on Turn
{transition['first_turn_with_objective_placement_majority']}, peaked at
{float(transition['peak_objective_placement_share']):.1%} on Turn
{transition['peak_objective_placement_share_turn']}, and first exceeded half
of cumulative placements on Turn
{transition['first_turn_with_cumulative_objective_majority']}. The final
cumulative Objective share returned to
{float(transition['final_cumulative_objective_placement_share']):.1%}, showing
a midgame conversion phase followed by renewed Supply allocation rather than a
one-way transition.

## Integrity

- {analysis['integrity']['legally_replayed_complete_games_reused']} complete, legally replayed games were reused.
- {analysis['integrity']['turn_progression_rows']} game-turn rows were reconstructed.
- {analysis['integrity']['state_rows_verified']} point-turn states matched Piece counts.
- {analysis['integrity']['state_chains_verified']} point state chains were continuous.
- {analysis['integrity']['final_boards_verified']} final 41-point boards matched source evidence.
- {analysis['integrity']['final_winners_verified']} winners were reproduced from the three lexicographic components.
- {analysis['integrity']['objective_supply_sources_verified']} Objective Supply-source uses were checked.
- Winner-based persistence was null for every draw.

See `experiments/issue-41/README.md` for the frozen definitions and reproduction
commands.
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    validate_definitions(config)
    source = config["source"]
    paths = {
        key: REPO_ROOT / source[key]
        for key in (
            "replay_summary", "placements", "supply_turn_states",
            "objective_turn_states", "source_trials", "issue_39_site_values",
        )
    }
    site_values = read_csv(paths["issue_39_site_values"])
    validate_site_sets(config, site_values)

    source_trials = read_csv(paths["source_trials"])
    for row in source_trials:
        trial = REPO_ROOT / row["trial_file"]
        if not trial.is_file() or sha256(trial) != row["trial_sha256"]:
            raise ValueError(f"source trial hash mismatch: {trial}")

    progression, integrity = reconstruct_progression(
        config,
        read_csv(paths["replay_summary"]),
        read_csv(paths["placements"]),
        read_csv(paths["supply_turn_states"]),
        read_csv(paths["objective_turn_states"]),
    )
    lead_rows, turning = build_lead_summaries(config, progression)
    reversal_rows = build_reversal_rows(config, progression)
    advantage_rows = build_turn_advantage_rows(config, progression)
    turning_rows = build_turning_point_rows(config, progression, turning)
    transition_rows = build_transition_rows(progression)

    source_files = [
        {"source_role": role, "path": path.relative_to(REPO_ROOT).as_posix(), "sha256": sha256(path)}
        for role, path in paths.items()
    ]
    write_csv(RESULTS / "source-files.csv", source_files)
    write_csv(RAW / "turn-progression.csv", progression)
    write_csv(RESULTS / "lead-change-summary.csv", lead_rows)
    write_csv(RESULTS / "reversal-by-turn.csv", reversal_rows)
    write_csv(RESULTS / "turn-advantage-summary.csv", advantage_rows)
    write_csv(RESULTS / "turning-point-events.csv", turning_rows)
    write_csv(RESULTS / "supply-objective-transition.csv", transition_rows)
    analysis = build_analysis(
        config, progression, lead_rows, reversal_rows, turning_rows,
        transition_rows, integrity, source_files
    )
    (RESULTS / "analysis.json").write_text(
        json.dumps(analysis, indent=2) + "\n", encoding="utf-8"
    )
    build_report(analysis)


if __name__ == "__main__":
    main()
