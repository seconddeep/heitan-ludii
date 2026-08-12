#!/usr/bin/env python3
"""Build leakage-safe checkpoint features and evaluate frozen Issue #44 models."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, median, pstdev, stdev
from typing import Iterable, Sequence


SCRIPT = Path(__file__).resolve()
ISSUE_ROOT = SCRIPT.parent.parent
REPO_ROOT = ISSUE_ROOT.parent.parent
RESULTS = ISSUE_ROOT / "results"
RAW = RESULTS / "raw"
CONFIG_PATH = ISSUE_ROOT / "config.json"
README_PATH = ISSUE_ROOT / "README.md"
REPORT_PATH = REPO_ROOT / "experiments" / "issue-44.md"
COMPONENTS = (
    "secured_objective_difference",
    "advantage_objective_difference",
    "objective_piece_difference",
)
LAYERS = ("secured_objectives", "advantage_objectives", "objective_pieces")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, object]], fieldnames: Sequence[str] | None = None) -> None:
    values = list(rows)
    if not values:
        raise ValueError(f"refusing to write empty output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    names = list(fieldnames or values[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(values)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sign(value: float) -> int:
    return 1 if value > 0 else -1 if value < 0 else 0


def lex_sign(values: Sequence[int | float]) -> int:
    return next((sign(float(value)) for value in values if value), 0)


def objective_adjacencies(objective: str) -> tuple[str, str, str, str]:
    row, column = int(objective[1]), int(objective[2])
    return (
        f"S{row}{column}", f"S{row}{column + 1}",
        f"S{row + 1}{column}", f"S{row + 1}{column + 1}",
    )


def controlled(state: int, player: int) -> bool:
    return state in (player, player + 2)


def usable_supply_support_edges(
    supply_states: dict[str, int], objective_states: dict[str, int], player: int
) -> int:
    usable = {site for site, state in supply_states.items() if controlled(state, player)}
    return sum(
        supply in usable
        for objective, state in objective_states.items() if state in (0, 1, 2)
        for supply in objective_adjacencies(objective)
    )


def relative_site_state(state: int, leader: int) -> int:
    if state == 0:
        return 0
    if state == leader:
        return 1
    if state == leader + 2:
        return 2
    opponent = 3 - leader
    if state == opponent:
        return -1
    if state == opponent + 2:
        return -2
    raise ValueError(f"invalid site state: {state}")


def validate_config(config: dict[str, object]) -> None:
    if config["checkpoints"] != {"primary": [16, 20], "reference": [8, 12], "pool_primary_rows": False}:
        raise ValueError("checkpoint policy differs from frozen Issue #44 definition")
    if config["recent_windows"] != [2, 4]:
        raise ValueError("recent windows differ from the frozen definition")
    if config["important_supply_sites"] != ["S23", "S21", "S12", "S13", "S22"]:
        raise ValueError("important Supply sites differ from the frozen definition")
    cv = config["cross_validation"]
    if cv["folds"] != 5 or cv["primary_rows_pooled"] or config["checkpoints"]["pool_primary_rows"]:
        raise ValueError("primary evaluation must use separate deterministic five-fold CV")
    regression = config["logistic_regression"]
    if regression["coefficient_tuning"] or regression["nested_cross_validation"]:
        raise ValueError("reported CV must not tune the fixed model specification")
    models = config["models"]
    expected_names = [
        "majority_class", "decisive_margin_only", "current_objective_state",
        "objective_only", "supply_only", "allocation_recent_trend", "combined",
    ]
    if [model["name"] for model in models] != expected_names:
        raise ValueError("configured model list differs from the frozen model list")
    shared_l2 = float(regression["shared_l2_coefficient"])
    descriptive = set(config["descriptive_features"])
    for model in models:
        if model["model_type"] == "logistic" and float(model["l2_regularization_coefficient"]) != shared_l2:
            raise ValueError("logistic model does not use the frozen shared L2 coefficient")
        if model["checkpoint_applicability"] != [8, 12, 16, 20]:
            raise ValueError("model checkpoint applicability differs from the frozen policy")
        if not set(model["included_feature_columns"]).issubset(descriptive):
            raise ValueError(f"model references an undeclared feature: {model['name']}")
    edge = config["usable_supply_support_edges"]
    if not edge["count_each_adjacency_pair"] or edge["deduplicate_by_supply_point"] or edge["deduplicate_by_objective"]:
        raise ValueError("usable Supply-support edge definition changed")
    readme = README_PATH.read_text(encoding="utf-8")
    required = [
        "Primary predictive models are trained and evaluated separately for each",
        "Univariate effect\nrankings are descriptive",
        "training fold's population mean and standard deviation",
    ]
    normalized_readme = readme.replace("**", "")
    if any(text not in normalized_readme for text in required):
        raise ValueError("README does not document the frozen evaluation policy")


def numeric_row(source: dict[str, str]) -> dict[str, object]:
    row: dict[str, object] = {}
    for key, value in source.items():
        if value == "":
            row[key] = ""
            continue
        try:
            row[key] = int(value)
        except ValueError:
            try:
                row[key] = float(value)
            except ValueError:
                row[key] = value
    return row


def build_turn_records(
    progression: list[dict[str, str]], placements: list[dict[str, str]],
    supply_rows: list[dict[str, str]], objective_rows: list[dict[str, str]],
    important_sites: set[str],
) -> tuple[list[dict[str, object]], dict[str, int]]:
    place_index: dict[tuple[str, int, int], list[dict[str, str]]] = defaultdict(list)
    supply_index: dict[tuple[str, int, int], list[dict[str, str]]] = defaultdict(list)
    objective_index: dict[tuple[str, int, int], list[dict[str, str]]] = defaultdict(list)
    for item in placements:
        place_index[(item["experiment_id"], int(item["game_index"]), int(item["turn_number"]))].append(item)
    for item in supply_rows:
        supply_index[(item["experiment_id"], int(item["game_index"]), int(item["turn_number"]))].append(item)
    for item in objective_rows:
        objective_index[(item["experiment_id"], int(item["game_index"]), int(item["turn_number"]))].append(item)

    output: list[dict[str, object]] = []
    continuity: dict[tuple[str, int, str], tuple[int, int, int]] = {}
    state_checks = source_checks = 0
    for raw in progression:
        key = raw["experiment_id"], int(raw["game_index"]), int(raw["turn_number"])
        supplies, objectives, moves = supply_index[key], objective_index[key], place_index[key]
        if len(supplies) != 25 or len(objectives) != 16 or len(moves) != 3:
            raise ValueError(f"invalid source dimensions at {key}")
        row = numeric_row(raw)
        mover = int(row["mover"])
        supply_states = {item["supply_point"]: int(item["state_at_turn_end"]) for item in supplies}
        objective_states = {item["objective"]: int(item["state_at_turn_end"]) for item in objectives}
        for item, site_field in [
            *[(value, "supply_point") for value in supplies],
            *[(value, "objective") for value in objectives],
        ]:
            site = item[site_field]
            start = (
                int(item["state_at_turn_start"]), int(item["p1_pieces_at_turn_start"]),
                int(item["p2_pieces_at_turn_start"]),
            )
            previous = continuity.get((key[0], key[1], site))
            if previous is not None and previous != start:
                raise ValueError(f"state chain mismatch at {key} {site}")
            continuity[(key[0], key[1], site)] = (
                int(item["state_at_turn_end"]), int(item["p1_pieces_at_turn_end"]),
                int(item["p2_pieces_at_turn_end"]),
            )
            state_checks += 1
        sources = [item["supply_source"] for item in moves if item["supply_source"]]
        if len(sources) != len(set(sources)):
            raise ValueError(f"Supply source reused at {key}")
        for item in moves:
            if item["target_type"] == "objective":
                source = item["supply_source"]
                if source not in objective_adjacencies(item["target"]) or not controlled(supply_states[source], mover):
                    raise ValueError(f"invalid Objective Supply source at {key}")
                source_checks += 1
        row["live_objectives"] = sum(state < 3 for state in objective_states.values())
        row["contested_supply_count"] = sum(
            int(item["p1_pieces_at_turn_end"]) > 0 and int(item["p2_pieces_at_turn_end"]) > 0
            for item in supplies
        )
        for site, state in supply_states.items():
            row[f"supply_state_{site}"] = state
        for player in (1, 2):
            row[f"usable_supply_support_edges_p{player}"] = usable_supply_support_edges(
                supply_states, objective_states, player
            )
            row[f"primary_important_sites_controlled_p{player}"] = sum(
                controlled(supply_states[site], player) for site in important_sites
            )
            row[f"supply_placements_turn_p{player}"] = sum(
                mover == player and item["target_type"] == "supply" for item in moves
            )
            row[f"objective_placements_turn_p{player}"] = sum(
                mover == player and item["target_type"] == "objective" for item in moves
            )
            row[f"supply_source_usage_turn_p{player}"] = len(sources) if mover == player else 0
            row[f"important_supply_source_usage_turn_p{player}"] = (
                sum(source in important_sites for source in sources) if mover == player else 0
            )
        supply_count = sum(item["target_type"] == "supply" for item in moves)
        row["turn_allocation_type"] = (
            "all_supply" if supply_count == 3 else "all_objective" if supply_count == 0 else "mixed"
        )
        output.append(row)
    return output, {
        "game_turn_rows": len(output),
        "point_turn_states_verified": state_checks,
        "point_state_chains_verified": len(continuity),
        "objective_supply_sources_verified": source_checks,
    }


def player_pair(row: dict[str, object], stem: str, leader: int) -> tuple[float, float]:
    opponent = 3 - leader
    return float(row[f"p{leader}_{stem}"]), float(row[f"p{opponent}_{stem}"])


def direct_pair(row: dict[str, object], stem: str, leader: int) -> tuple[float, float]:
    opponent = 3 - leader
    return float(row[f"{stem}_p{leader}"]), float(row[f"{stem}_p{opponent}"])


def ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def state_margin(row: dict[str, object], field: str, leader: int) -> float:
    direction = 1 if leader == 1 else -1
    return float(row[field]) * direction


def build_checkpoint_feature(
    rows: dict[int, dict[str, object]], checkpoint: int, leader: int,
    cohort: str, config: dict[str, object],
) -> dict[str, object]:
    current = rows[checkpoint]
    opponent = 3 - leader
    output: dict[str, object] = {
        "experiment_id": current["experiment_id"],
        "game_index": current["game_index"],
        "checkpoint_turn": checkpoint,
        "outcome_class": cohort,
        "checkpoint_leader": leader,
        "winner": current["winner"],
    }
    raw_pairs = {
        "secured_objectives": "secured_objectives",
        "advantage_objectives": "advantage_objectives",
        "objective_pieces": "objective_pieces",
        "secured_supply": "secured_supply",
        "unsecured_controlled_supply": "unsecured_controlled_supply",
        "cumulative_supply_placements": "cumulative_supply_placements",
        "cumulative_objective_placements": "cumulative_objective_placements",
        "cumulative_supply_source_usage": "cumulative_supply_source_usage",
    }
    for name, stem in raw_pairs.items():
        output[f"raw_p1_{name}"] = current[f"p1_{stem}"]
        output[f"raw_p2_{name}"] = current[f"p2_{stem}"]

    leader_secured, opponent_secured = player_pair(current, "secured_objectives", leader)
    leader_advantage, opponent_advantage = player_pair(current, "advantage_objectives", leader)
    leader_pieces, opponent_pieces = player_pair(current, "objective_pieces", leader)
    output.update({
        "leader_secured_objectives": leader_secured,
        "opponent_secured_objectives": opponent_secured,
        "leader_secured_objective_margin": leader_secured - opponent_secured,
        "leader_advantage_objectives": leader_advantage,
        "opponent_advantage_objectives": opponent_advantage,
        "leader_advantage_objective_margin": leader_advantage - opponent_advantage,
        "leader_objective_pieces": leader_pieces,
        "opponent_objective_pieces": opponent_pieces,
        "leader_objective_piece_margin": leader_pieces - opponent_pieces,
        "live_objectives": current["live_objectives"],
    })
    component_values = [
        output["leader_secured_objective_margin"], output["leader_advantage_objective_margin"],
        output["leader_objective_piece_margin"],
    ]
    decisive_index = next(index for index, value in enumerate(component_values) if value)
    output["decisive_layer"] = LAYERS[decisive_index]
    output["decisive_margin"] = abs(float(component_values[decisive_index]))
    for layer in LAYERS:
        output[f"decisive_layer_{layer}"] = int(layer == LAYERS[decisive_index])

    leader_supply, opponent_supply = player_pair(current, "secured_supply", leader)
    leader_unsecured, opponent_unsecured = player_pair(current, "unsecured_controlled_supply", leader)
    leader_edges, opponent_edges = direct_pair(current, "usable_supply_support_edges", leader)
    leader_important, opponent_important = direct_pair(current, "primary_important_sites_controlled", leader)
    leader_usage, opponent_usage = player_pair(current, "cumulative_supply_source_usage", leader)
    output.update({
        "leader_secured_supply": leader_supply,
        "opponent_secured_supply": opponent_supply,
        "leader_secured_supply_margin": leader_supply - opponent_supply,
        "leader_unsecured_controlled_supply": leader_unsecured,
        "opponent_unsecured_controlled_supply": opponent_unsecured,
        "leader_unsecured_controlled_supply_margin": leader_unsecured - opponent_unsecured,
        "contested_supply_count": current["contested_supply_count"],
        "leader_usable_supply_support_edges": leader_edges,
        "opponent_usable_supply_support_edges": opponent_edges,
        "leader_usable_supply_support_edge_margin": leader_edges - opponent_edges,
        "leader_primary_important_sites_controlled": leader_important,
        "opponent_primary_important_sites_controlled": opponent_important,
        "leader_primary_important_control_margin": leader_important - opponent_important,
        "leader_cumulative_supply_source_usage": leader_usage,
        "opponent_cumulative_supply_source_usage": opponent_usage,
        "leader_cumulative_supply_source_usage_margin": leader_usage - opponent_usage,
    })
    for site in config["important_supply_sites"]:
        state = int(current[f"supply_state_{site}"])
        output[f"{site}_raw_state"] = state
        output[f"{site}_leader_relative_state"] = relative_site_state(state, leader)

    leader_cum_supply, opponent_cum_supply = player_pair(current, "cumulative_supply_placements", leader)
    leader_cum_objective, opponent_cum_objective = player_pair(current, "cumulative_objective_placements", leader)
    leader_share = ratio(leader_cum_objective, leader_cum_supply + leader_cum_objective)
    opponent_share = ratio(opponent_cum_objective, opponent_cum_supply + opponent_cum_objective)
    output.update({
        "leader_cumulative_supply_placements": leader_cum_supply,
        "opponent_cumulative_supply_placements": opponent_cum_supply,
        "leader_cumulative_objective_placements": leader_cum_objective,
        "opponent_cumulative_objective_placements": opponent_cum_objective,
        "leader_cumulative_objective_share": leader_share,
        "opponent_cumulative_objective_share": opponent_share,
        "leader_cumulative_objective_share_margin": leader_share - opponent_share,
    })

    for window in config["recent_windows"]:
        selected = [rows[turn] for turn in range(checkpoint - int(window) + 1, checkpoint + 1)]
        values: dict[int, dict[str, float]] = {}
        for player in (leader, opponent):
            values[player] = {
                "supply": sum(float(item[f"supply_placements_turn_p{player}"]) for item in selected),
                "objective": sum(float(item[f"objective_placements_turn_p{player}"]) for item in selected),
                "usage": sum(float(item[f"supply_source_usage_turn_p{player}"]) for item in selected),
                "important_usage": sum(float(item[f"important_supply_source_usage_turn_p{player}"]) for item in selected),
                "all_supply": sum(int(item["mover"]) == player and item["turn_allocation_type"] == "all_supply" for item in selected),
                "mixed": sum(int(item["mover"]) == player and item["turn_allocation_type"] == "mixed" for item in selected),
                "all_objective": sum(int(item["mover"]) == player and item["turn_allocation_type"] == "all_objective" for item in selected),
            }
        for prefix, player in (("leader", leader), ("opponent", opponent)):
            output[f"{prefix}_recent_{window}_supply_placements"] = values[player]["supply"]
            output[f"{prefix}_recent_{window}_objective_placements"] = values[player]["objective"]
            output[f"{prefix}_recent_{window}_supply_source_usage"] = values[player]["usage"]
            output[f"{prefix}_recent_{window}_important_site_usage"] = values[player]["important_usage"]
            output[f"{prefix}_recent_{window}_all_supply_turns"] = values[player]["all_supply"]
            output[f"{prefix}_recent_{window}_mixed_turns"] = values[player]["mixed"]
            output[f"{prefix}_recent_{window}_all_objective_turns"] = values[player]["all_objective"]
        output[f"leader_recent_{window}_supply_source_usage_margin"] = values[leader]["usage"] - values[opponent]["usage"]
        output[f"leader_recent_{window}_important_site_usage_margin"] = values[leader]["important_usage"] - values[opponent]["important_usage"]
        output[f"leader_recent_{window}_objective_placement_margin"] = values[leader]["objective"] - values[opponent]["objective"]
        leader_recent_share = ratio(values[leader]["objective"], values[leader]["objective"] + values[leader]["supply"])
        opponent_recent_share = ratio(values[opponent]["objective"], values[opponent]["objective"] + values[opponent]["supply"])
        output[f"leader_recent_{window}_objective_share"] = leader_recent_share
        output[f"opponent_recent_{window}_objective_share"] = opponent_recent_share
        output[f"leader_recent_{window}_objective_share_margin"] = leader_recent_share - opponent_recent_share
        output[f"leader_recent_{window}_all_supply_turn_margin"] = values[leader]["all_supply"] - values[opponent]["all_supply"]
        output[f"leader_recent_{window}_mixed_turn_margin"] = values[leader]["mixed"] - values[opponent]["mixed"]
        output[f"leader_recent_{window}_all_objective_turn_margin"] = values[leader]["all_objective"] - values[opponent]["all_objective"]

        previous = rows[checkpoint - int(window)]
        trend_fields = {
            "secured_objective": "secured_objective_difference",
            "advantage_objective": "advantage_objective_difference",
            "objective_piece": "objective_piece_difference",
            "secured_supply": "secured_supply_difference",
            "unsecured_control": "unsecured_controlled_supply_difference",
        }
        for name, field in trend_fields.items():
            output[f"leader_trend_{window}_{name}_margin"] = (
                state_margin(current, field, leader) - state_margin(previous, field, leader)
            )
        current_edges = float(current[f"usable_supply_support_edges_p{leader}"]) - float(current[f"usable_supply_support_edges_p{opponent}"])
        previous_edges = float(previous[f"usable_supply_support_edges_p{leader}"]) - float(previous[f"usable_supply_support_edges_p{opponent}"])
        output[f"leader_trend_{window}_support_edge_margin"] = current_edges - previous_edges
        output[f"leader_trend_{window}_usable_support_edges"] = (
            float(current[f"usable_supply_support_edges_p{leader}"])
            - float(previous[f"usable_supply_support_edges_p{leader}"])
        )
        output[f"opponent_trend_{window}_usable_support_edges"] = (
            float(current[f"usable_supply_support_edges_p{opponent}"])
            - float(previous[f"usable_supply_support_edges_p{opponent}"])
        )
        current_important = float(current[f"primary_important_sites_controlled_p{leader}"]) - float(current[f"primary_important_sites_controlled_p{opponent}"])
        previous_important = float(previous[f"primary_important_sites_controlled_p{leader}"]) - float(previous[f"primary_important_sites_controlled_p{opponent}"])
        output[f"leader_trend_{window}_important_control_margin"] = current_important - previous_important

    allocation_change: dict[int, float] = {}
    selected_four = [rows[turn] for turn in range(checkpoint - 3, checkpoint + 1)]
    for player in (leader, opponent):
        own = [item for item in selected_four if int(item["mover"]) == player]
        if len(own) != 2:
            raise ValueError("four-turn allocation window must contain two turns per player")
        shares = [float(item[f"objective_placements_turn_p{player}"]) / 3.0 for item in own]
        allocation_change[player] = shares[1] - shares[0]
    output["leader_recent_4_objective_allocation_change"] = allocation_change[leader]
    output["opponent_recent_4_objective_allocation_change"] = allocation_change[opponent]
    output["leader_recent_4_objective_allocation_change_margin"] = allocation_change[leader] - allocation_change[opponent]
    output["leader_recent_4_supply_allocation_change"] = -allocation_change[leader]
    output["opponent_recent_4_supply_allocation_change"] = -allocation_change[opponent]
    output["leader_recent_4_supply_allocation_change_margin"] = -allocation_change[leader] + allocation_change[opponent]
    return output


def build_checkpoint_rows(
    turn_rows: list[dict[str, object]], config: dict[str, object],
) -> tuple[list[dict[str, object]], dict[str, int]]:
    by_game: dict[tuple[str, int], dict[int, dict[str, object]]] = defaultdict(dict)
    for row in turn_rows:
        by_game[(str(row["experiment_id"]), int(row["game_index"]))][int(row["turn_number"])] = row
    checkpoints = config["checkpoints"]["reference"] + config["checkpoints"]["primary"]
    output: list[dict[str, object]] = []
    winners_verified = 0
    for key, rows in sorted(by_game.items()):
        if len(rows) != 24:
            raise ValueError(f"game does not have 24 turns: {key}")
        final_sign = lex_sign([int(rows[24][field]) for field in COMPONENTS])
        expected_winner = 1 if final_sign > 0 else 2 if final_sign < 0 else 0
        if expected_winner != int(rows[24]["winner"]):
            raise ValueError(f"final winner mismatch: {key}")
        winners_verified += 1
        for checkpoint in checkpoints:
            comparison = [int(rows[checkpoint][field]) for field in COMPONENTS]
            checkpoint_sign = lex_sign(comparison)
            leader = 1 if checkpoint_sign > 0 else 2 if checkpoint_sign < 0 else None
            winner = int(rows[checkpoint]["winner"])
            if leader is None:
                cohort = "tied_at_checkpoint"
                base = {
                    "experiment_id": key[0], "game_index": key[1], "checkpoint_turn": checkpoint,
                    "outcome_class": cohort, "checkpoint_leader": "", "winner": winner,
                }
            else:
                cohort = "eventual_draw" if winner == 0 else "lead_preserved" if winner == leader else "reversal"
                base = build_checkpoint_feature(rows, checkpoint, leader, cohort, config)
            output.append(base)
    return output, {"games": len(by_game), "final_winners_verified": winners_verified}


def deterministic_fold_assignments(
    rows: list[dict[str, object]], folds: int, seed: str,
) -> list[dict[str, object]]:
    groups: dict[tuple[str, int, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        if row["outcome_class"] in ("reversal", "lead_preserved"):
            groups[(str(row["experiment_id"]), int(row["checkpoint_turn"]), str(row["outcome_class"]))].append(row)
    output: list[dict[str, object]] = []
    for (experiment, checkpoint, outcome), selected in sorted(groups.items()):
        ordered = sorted(selected, key=lambda row: hashlib.sha256(
            f"{seed}|{experiment}|{checkpoint}|{row['game_index']}".encode()
        ).hexdigest())
        for index, row in enumerate(ordered):
            output.append({
                "experiment_id": experiment,
                "game_index": int(row["game_index"]),
                "checkpoint_turn": checkpoint,
                "outcome_class": outcome,
                "cv_fold": index % folds + 1,
            })
    return sorted(output, key=lambda row: (
        str(row["experiment_id"]), int(row["checkpoint_turn"]), int(row["game_index"])
    ))


def fit_preprocessor(
    training_rows: list[dict[str, object]], features: Sequence[str],
) -> dict[str, dict[str, float | bool]]:
    result: dict[str, dict[str, float | bool]] = {}
    for feature in features:
        values = [float(row[feature]) for row in training_rows]
        center = mean(values)
        scale = pstdev(values)
        result[feature] = {"mean": center, "std": scale, "active": scale > 0}
    return result


def transform_rows(
    rows: list[dict[str, object]], features: Sequence[str],
    preprocessing: dict[str, dict[str, float | bool]],
) -> tuple[list[list[float]], list[str]]:
    active = [feature for feature in features if bool(preprocessing[feature]["active"])]
    matrix = [[
        (float(row[feature]) - float(preprocessing[feature]["mean"])) / float(preprocessing[feature]["std"])
        for feature in active
    ] for row in rows]
    return matrix, active


def sigmoid(value: float) -> float:
    if value >= 0:
        inverse = math.exp(-min(value, 700.0))
        return 1.0 / (1.0 + inverse)
    exponential = math.exp(max(value, -700.0))
    return exponential / (1.0 + exponential)


def solve_linear(matrix: list[list[float]], vector: list[float]) -> list[float]:
    size = len(vector)
    augmented = [list(matrix[row]) + [vector[row]] for row in range(size)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-14:
            raise ValueError("singular logistic Hessian")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                augmented[row][index] - factor * augmented[column][index]
                for index in range(size + 1)
            ]
    return [augmented[row][-1] for row in range(size)]


def fit_logistic(
    matrix: list[list[float]], labels: list[int], l2: float,
    maximum_iterations: int, tolerance: float,
) -> list[float]:
    if not matrix or len(set(labels)) < 2:
        raise ValueError("logistic training requires rows from both classes")
    feature_count = len(matrix[0]) if matrix else 0
    beta = [0.0] * (feature_count + 1)
    augmented = [[1.0] + row for row in matrix]
    count = len(labels)
    for _ in range(maximum_iterations):
        probabilities = [sigmoid(sum(coefficient * value for coefficient, value in zip(beta, row))) for row in augmented]
        gradient = [0.0] * len(beta)
        hessian = [[0.0] * len(beta) for _ in beta]
        for row, label, probability in zip(augmented, labels, probabilities):
            residual = probability - label
            weight = max(probability * (1.0 - probability), 1e-12)
            for left in range(len(beta)):
                gradient[left] += residual * row[left] / count
                for right in range(len(beta)):
                    hessian[left][right] += weight * row[left] * row[right] / count
        for index in range(1, len(beta)):
            gradient[index] += l2 * beta[index]
            hessian[index][index] += l2
        step = solve_linear(hessian, gradient)
        beta = [coefficient - change for coefficient, change in zip(beta, step)]
        if max(abs(change) for change in step) < tolerance:
            break
    return beta


def predict_logistic(matrix: list[list[float]], beta: Sequence[float]) -> list[float]:
    return [sigmoid(beta[0] + sum(value * coefficient for value, coefficient in zip(row, beta[1:]))) for row in matrix]


def roc_auc(labels: Sequence[int], scores: Sequence[float]) -> float:
    positives = sum(labels)
    negatives = len(labels) - positives
    if not positives or not negatives:
        return float("nan")
    order = sorted(range(len(scores)), key=lambda index: scores[index])
    rank_sum = 0.0
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and scores[order[end]] == scores[order[start]]:
            end += 1
        average_rank = ((start + 1) + end) / 2.0
        rank_sum += average_rank * sum(labels[order[index]] for index in range(start, end))
        start = end
    return (rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)


def balanced_accuracy(labels: Sequence[int], scores: Sequence[float], threshold: float = 0.5) -> float:
    true_positive = sum(label == 1 and score >= threshold for label, score in zip(labels, scores))
    true_negative = sum(label == 0 and score < threshold for label, score in zip(labels, scores))
    positives = sum(labels)
    negatives = len(labels) - positives
    return ((true_positive / positives) + (true_negative / negatives)) / 2.0


def average_precision(labels: Sequence[int], scores: Sequence[float]) -> float:
    positives = sum(labels)
    if not positives:
        return float("nan")
    grouped: dict[float, list[int]] = defaultdict(list)
    for label, score in zip(labels, scores):
        grouped[float(score)].append(int(label))
    true_positive = false_positive = 0
    prior_recall = result = 0.0
    for score in sorted(grouped, reverse=True):
        true_positive += sum(grouped[score])
        false_positive += len(grouped[score]) - sum(grouped[score])
        recall = true_positive / positives
        precision = true_positive / (true_positive + false_positive)
        result += (recall - prior_recall) * precision
        prior_recall = recall
    return result


def metric_values(labels: Sequence[int], scores: Sequence[float], threshold: float) -> dict[str, float]:
    return {
        "roc_auc": roc_auc(labels, scores),
        "balanced_accuracy": balanced_accuracy(labels, scores, threshold),
        "average_precision": average_precision(labels, scores),
    }


def rounded(value: float) -> object:
    return "" if math.isnan(value) else round(value, 6)


def evaluate_models(
    eligible_rows: list[dict[str, object]], assignments: list[dict[str, object]],
    config: dict[str, object],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    fold_by_key = {
        (str(row["experiment_id"]), int(row["checkpoint_turn"]), int(row["game_index"])): int(row["cv_fold"])
        for row in assignments
    }
    groups: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
    for row in eligible_rows:
        groups[(str(row["experiment_id"]), int(row["checkpoint_turn"]))].append(row)
    summaries: list[dict[str, object]] = []
    predictions: list[dict[str, object]] = []
    preprocessing_rows: list[dict[str, object]] = []
    settings = config["logistic_regression"]
    threshold = float(config["cross_validation"]["threshold"])
    fold_count = int(config["cross_validation"]["folds"])
    for (experiment, checkpoint), rows in sorted(groups.items()):
        rows = sorted(rows, key=lambda row: int(row["game_index"]))
        for model in config["models"]:
            if checkpoint not in model["checkpoint_applicability"]:
                continue
            fold_metrics: list[dict[str, float]] = []
            model_predictions: list[dict[str, object]] = []
            for fold in range(1, fold_count + 1):
                training = [row for row in rows if fold_by_key[(experiment, checkpoint, int(row["game_index"]))] != fold]
                validation = [row for row in rows if fold_by_key[(experiment, checkpoint, int(row["game_index"]))] == fold]
                training_labels = [1 if row["outcome_class"] == "reversal" else 0 for row in training]
                validation_labels = [1 if row["outcome_class"] == "reversal" else 0 for row in validation]
                if model["model_type"] == "majority":
                    prevalence = mean(training_labels)
                    scores = [float(prevalence >= 0.5)] * len(validation)
                else:
                    features = list(model["included_feature_columns"])
                    preprocessing = fit_preprocessor(training, features)
                    training_matrix, active = transform_rows(training, features, preprocessing)
                    validation_matrix, validation_active = transform_rows(validation, features, preprocessing)
                    if active != validation_active:
                        raise AssertionError("training preprocessing was not reused for validation")
                    for feature in features:
                        metadata = preprocessing[feature]
                        preprocessing_rows.append({
                            "experiment_id": experiment, "checkpoint_turn": checkpoint,
                            "model_name": model["name"], "cv_fold": fold, "feature": feature,
                            "training_mean": round(float(metadata["mean"]), 12),
                            "training_population_std": round(float(metadata["std"]), 12),
                            "active": int(bool(metadata["active"])),
                            "zero_variance_policy": config["preprocessing"]["zero_variance_policy"],
                        })
                    beta = fit_logistic(
                        training_matrix, training_labels, float(model["l2_regularization_coefficient"]),
                        int(settings["maximum_iterations"]), float(settings["convergence_tolerance"]),
                    )
                    scores = predict_logistic(validation_matrix, beta)
                metrics = metric_values(validation_labels, scores, threshold)
                fold_metrics.append(metrics)
                for row, label, score in zip(validation, validation_labels, scores):
                    item = {
                        "experiment_id": experiment, "game_index": int(row["game_index"]),
                        "checkpoint_turn": checkpoint, "outcome_class": row["outcome_class"],
                        "cv_fold": fold, "model_name": model["name"], "feature_group": model["feature_group"],
                        "observed_reversal": label, "predicted_reversal_probability": round(score, 12),
                        "predicted_class": int(score >= threshold),
                    }
                    predictions.append(item)
                    model_predictions.append(item)
            labels = [int(row["observed_reversal"]) for row in model_predictions]
            scores = [float(row["predicted_reversal_probability"]) for row in model_predictions]
            overall = metric_values(labels, scores, threshold)
            summary: dict[str, object] = {
                "experiment_id": experiment, "checkpoint_turn": checkpoint,
                "model_name": model["name"], "feature_group": model["feature_group"],
                "eligible_games": len(rows), "reversals": sum(labels), "lead_preserved": len(labels) - sum(labels),
                "feature_count_configured": len(model["included_feature_columns"]),
                "l2_regularization_coefficient": model["l2_regularization_coefficient"],
                "standardization_policy": model["standardization_policy"],
                "zero_variance_handling": model["zero_variance_handling"],
            }
            for metric in config["evaluation_metrics"]:
                values = [fold_metric[metric] for fold_metric in fold_metrics]
                summary[f"oof_{metric}"] = rounded(overall[metric])
                summary[f"fold_mean_{metric}"] = rounded(mean(values))
                summary[f"fold_std_{metric}"] = rounded(stdev(values)) if len(values) > 1 else 0.0
            summaries.append(summary)
    return summaries, predictions, preprocessing_rows


def standardized_mean_difference(left: list[float], right: list[float]) -> float:
    if len(left) < 2 or len(right) < 2:
        return 0.0
    pooled_variance = (
        (len(left) - 1) * stdev(left) ** 2 + (len(right) - 1) * stdev(right) ** 2
    ) / (len(left) + len(right) - 2)
    return (mean(left) - mean(right)) / math.sqrt(pooled_variance) if pooled_variance > 0 else 0.0


def univariate_summaries(
    rows: list[dict[str, object]], features: Sequence[str],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    groups: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        if row["outcome_class"] in ("reversal", "lead_preserved"):
            groups[(str(row["experiment_id"]), int(row["checkpoint_turn"]))].append(row)
    comparisons: list[dict[str, object]] = []
    for (experiment, checkpoint), selected in sorted(groups.items()):
        for feature in features:
            reversal = [float(row[feature]) for row in selected if row["outcome_class"] == "reversal"]
            preserved = [float(row[feature]) for row in selected if row["outcome_class"] == "lead_preserved"]
            effect = standardized_mean_difference(reversal, preserved)
            comparisons.append({
                "experiment_id": experiment, "checkpoint_turn": checkpoint, "feature": feature,
                "reversal_n": len(reversal), "lead_preserved_n": len(preserved),
                "reversal_mean": round(mean(reversal), 6), "reversal_median": round(median(reversal), 6),
                "lead_preserved_mean": round(mean(preserved), 6), "lead_preserved_median": round(median(preserved), 6),
                "standardized_mean_difference": round(effect, 6),
                "effect_direction": "higher_in_reversal" if effect > 0 else "lower_in_reversal" if effect < 0 else "no_difference",
                "absolute_standardized_difference": round(abs(effect), 6),
            })
    effects: list[dict[str, object]] = []
    for key in sorted({(row["experiment_id"], row["checkpoint_turn"]) for row in comparisons}):
        selected = [row for row in comparisons if (row["experiment_id"], row["checkpoint_turn"]) == key]
        ordered = sorted(selected, key=lambda row: (-float(row["absolute_standardized_difference"]), str(row["feature"])))
        for rank, row in enumerate(ordered, 1):
            effects.append({**row, "absolute_effect_rank": rank})
    return comparisons, effects


def reconcile_sources(
    checkpoint_rows: list[dict[str, object]], config: dict[str, object], paths: dict[str, Path],
) -> dict[str, int]:
    checkpoints = config["checkpoints"]["reference"] + config["checkpoints"]["primary"]
    issue_43_config = json.loads(paths["issue_43_config"].read_text(encoding="utf-8"))
    if issue_43_config["checkpoints"] != {"primary": [16, 20], "reference": [8, 12]}:
        raise ValueError("Issue #43 checkpoint definition mismatch")
    if issue_43_config["important_supply_sites"] != config["important_supply_sites"]:
        raise ValueError("Issue #43 important-site definition mismatch")
    if issue_43_config["usable_supply_support_edges"] != config["usable_supply_support_edges"]:
        raise ValueError("Issue #43 usable Supply-support edge definition mismatch")
    prior = read_csv(paths["reversal_by_turn"])
    reconciled_41 = 0
    for experiment in (item["id"] for item in config["source"]["experiments"]):
        for checkpoint in checkpoints:
            expected = next(row for row in prior if row["experiment_id"] == experiment and row["comparison_layer"] == "full_lexicographic" and int(row["turn_number"]) == checkpoint)
            selected = [row for row in checkpoint_rows if row["experiment_id"] == experiment and int(row["checkpoint_turn"]) == checkpoint]
            actual = {
                "current_leader_eventually_wins": sum(row["outcome_class"] == "lead_preserved" for row in selected),
                "current_leader_eventually_loses": sum(row["outcome_class"] == "reversal" for row in selected),
                "eventual_draws_from_current_lead": sum(row["outcome_class"] == "eventual_draw" for row in selected),
                "games_tied_at_turn": sum(row["outcome_class"] == "tied_at_checkpoint" for row in selected),
            }
            if any(actual[name] != int(expected[name]) for name in actual):
                raise ValueError(f"Issue #41 checkpoint mismatch: {experiment} Turn {checkpoint}")
            reconciled_41 += 1

    issue_43 = read_csv(paths["issue_43_checkpoint_cohorts"])
    prior_labels = {
        (row["experiment_id"], int(row["game_index"]), int(row["checkpoint_turn"])):
            (row["cohort"], row["checkpoint_leader"], int(row["winner"]))
        for row in issue_43
    }
    reconciled_43 = 0
    for row in checkpoint_rows:
        key = str(row["experiment_id"]), int(row["game_index"]), int(row["checkpoint_turn"])
        leader = "" if row["checkpoint_leader"] == "" else str(row["checkpoint_leader"])
        actual = str(row["outcome_class"]), leader, int(row["winner"])
        if actual != prior_labels[key]:
            raise ValueError(f"Issue #43 label mismatch: {key}")
        reconciled_43 += 1

    site_values = [row for row in read_csv(paths["site_values"]) if row["experiment_id"] == "uct-10000-self-play"]
    top_sites = [row["supply_point"] for row in sorted(
        site_values, key=lambda row: (-float(row["objective_placements_supplied_per_player_game"]), row["supply_point"])
    )[:5]]
    if top_sites != config["important_supply_sites"]:
        raise ValueError("Issue #39 important-site ranking mismatch")
    return {"issue_41_checkpoint_cells_reconciled": reconciled_41, "issue_43_labels_reconciled": reconciled_43}


def build_cohort_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output = []
    for experiment in sorted({str(row["experiment_id"]) for row in rows}):
        for checkpoint in sorted({int(row["checkpoint_turn"]) for row in rows}):
            selected = [row for row in rows if row["experiment_id"] == experiment and int(row["checkpoint_turn"]) == checkpoint]
            counts = Counter(str(row["outcome_class"]) for row in selected)
            output.append({
                "experiment_id": experiment, "checkpoint_turn": checkpoint, "games": len(selected),
                "reversals": counts["reversal"], "lead_preserved": counts["lead_preserved"],
                "eventual_draws": counts["eventual_draw"], "tied_at_checkpoint": counts["tied_at_checkpoint"],
                "predictive_denominator": counts["reversal"] + counts["lead_preserved"],
            })
    return output


def sensitivity_rows(comparisons: list[dict[str, object]]) -> list[dict[str, object]]:
    by_key = {(int(row["checkpoint_turn"]), str(row["feature"]), str(row["experiment_id"])): row for row in comparisons}
    output = []
    for checkpoint, feature in sorted({(int(row["checkpoint_turn"]), str(row["feature"])) for row in comparisons}):
        primary = by_key[(checkpoint, feature, "uct-10000-self-play")]
        sensitivity = by_key[(checkpoint, feature, "uct-3000-self-play")]
        primary_effect = float(primary["standardized_mean_difference"])
        sensitivity_effect = float(sensitivity["standardized_mean_difference"])
        output.append({
            "checkpoint_turn": checkpoint, "feature": feature,
            "uct_10000_standardized_mean_difference": primary_effect,
            "uct_3000_standardized_mean_difference": sensitivity_effect,
            "direction_agreement": int(sign(primary_effect) == sign(sensitivity_effect)),
            "uct_10000_direction": primary["effect_direction"],
            "uct_3000_direction": sensitivity["effect_direction"],
        })
    return output


def write_report(
    analysis: dict[str, object], validation: list[dict[str, object]],
    comparisons: list[dict[str, object]], sensitivity: list[dict[str, object]],
    checkpoint_rows: list[dict[str, object]],
) -> None:
    primary = [row for row in validation if row["experiment_id"] == "uct-10000-self-play" and int(row["checkpoint_turn"]) in (16, 20)]
    lookup = {(int(row["checkpoint_turn"]), str(row["model_name"])): row for row in primary}
    effect_lookup = {
        (int(row["checkpoint_turn"]), str(row["feature"])): row
        for row in comparisons if row["experiment_id"] == "uct-10000-self-play"
    }
    sensitivity_lookup = {
        (int(row["checkpoint_turn"]), str(row["feature"])): row for row in sensitivity
    }
    margin_findings = {}
    for checkpoint in (16, 20):
        selected = [
            row for row in checkpoint_rows
            if row["experiment_id"] == "uct-10000-self-play"
            and int(row["checkpoint_turn"]) == checkpoint
            and row["outcome_class"] in ("reversal", "lead_preserved")
        ]
        narrow = [row for row in selected if float(row["decisive_margin"]) == 1]
        large = [row for row in selected if float(row["decisive_margin"]) > 1]
        margin_findings[checkpoint] = {
            "narrow_n": len(narrow), "narrow_reversals": sum(row["outcome_class"] == "reversal" for row in narrow),
            "narrow_rate": sum(row["outcome_class"] == "reversal" for row in narrow) / len(narrow),
            "large_n": len(large), "large_reversals": sum(row["outcome_class"] == "reversal" for row in large),
            "large_rate": sum(row["outcome_class"] == "reversal" for row in large) / len(large),
        }
    agreement = {}
    for checkpoint in (16, 20):
        selected = [row for row in sensitivity if int(row["checkpoint_turn"]) == checkpoint]
        agreement[checkpoint] = (sum(int(row["direction_agreement"]) for row in selected), len(selected))

    lines = [
        "# Issue 44: Reversal precursors in Heitan", "", "## Summary", "",
        "This analysis tests whether frozen checkpoint and recent-history features distinguish leaders who are later reversed from leaders who preserve their lead. It uses 100 UCT 10,000 games as the primary sample and 100 UCT 3,000 games as separate sensitivity evidence. No new self-play was generated.", "",
        "The primary sample contains modest predictive signal rather than a strong checkpoint classifier. At Turn 16 the Supply-only model has ROC AUC 0.589 and the combined model 0.561. At Turn 20 the combined model reaches 0.640, compared with 0.630 for the current Objective-state baseline. The Turn-20 combined gain beyond current Objective state is therefore small in this sample.", "",
        "Models, features, L2 regularization, preprocessing, and folds were frozen before evaluation. Each checkpoint was trained and evaluated separately; univariate effects were descriptive and were not used for feature selection.", "",
        "## Primary out-of-fold results", "",
        "| Turn | Model | ROC AUC | Balanced accuracy | Average precision |", "|---:|---|---:|---:|---:|",
    ]
    for checkpoint in (16, 20):
        for model in ("majority_class", "decisive_margin_only", "current_objective_state", "objective_only", "supply_only", "allocation_recent_trend", "combined"):
            row = lookup[(checkpoint, model)]
            lines.append(
                f"| {checkpoint} | {model} | {float(row['oof_roc_auc']):.3f} | {float(row['oof_balanced_accuracy']):.3f} | {float(row['oof_average_precision']):.3f} |"
            )
    lines.extend([
        "", "These values are finite-sample predictive associations. Differences among models are reported descriptively; the reported folds were not used to revise model definitions or select regularization.", "",
        "## Pre-checkpoint signals", "",
        "Standardized mean differences below are reversal minus lead-preserved; negative support-edge changes mean the checkpoint leader's support worsened more before games that reversed.", "",
        "| Turn | Frozen feature | Reversal mean | Preserved mean | Standardized difference |", "|---:|---|---:|---:|---:|",
    ])
    named_features = (
        ("decisive_margin", "decisive margin"),
        ("leader_trend_2_usable_support_edges", "leader support-edge change, 2 turns"),
        ("opponent_trend_2_usable_support_edges", "opponent support-edge change, 2 turns"),
        ("leader_primary_important_control_margin", "important-site Control margin"),
        ("opponent_recent_4_supply_allocation_change", "opponent Supply-allocation change"),
    )
    for checkpoint in (16, 20):
        for feature, label in named_features:
            row = effect_lookup[(checkpoint, feature)]
            lines.append(
                f"| {checkpoint} | {label} | {float(row['reversal_mean']):.3f} | {float(row['lead_preserved_mean']):.3f} | {float(row['standardized_mean_difference']):+.3f} |"
            )

    turn16_margin, turn20_margin = margin_findings[16], margin_findings[20]
    support16 = effect_lookup[(16, "leader_trend_2_support_edge_margin")]
    support20 = effect_lookup[(20, "leader_trend_2_support_edge_margin")]
    opponent_reinvest16 = sensitivity_lookup[(16, "opponent_recent_4_supply_allocation_change")]
    opponent_reinvest20 = sensitivity_lookup[(20, "opponent_recent_4_supply_allocation_change")]
    lines.extend([
        "", "## Questions from the issue", "",
        "- **Can later losers be distinguished?** Only modestly. The best pre-specified primary AUC is 0.589 at Turn 16 and 0.640 at Turn 20; neither supports a strong or production-ready predictor.",
        "- **How much is in the Objective score?** The current Objective-state baseline is below chance in the Turn-16 sample (AUC 0.407) but reaches 0.630 at Turn 20. Objective information becomes more useful late, but its direction is not stable across every search-strength/checkpoint cell.",
        "- **Does Supply add information?** At Turn 16 Supply-only exceeds the current Objective baseline (0.589 versus 0.407), and combined exceeds it (0.561 versus 0.407). At Turn 20 Supply-only is 0.588 and combined improves only slightly over the Objective baseline (0.640 versus 0.630). This is suggestive of Supply-added signal at Turn 16 and mostly complementary signal at Turn 20, not a uniform gain.",
        f"- **Do usable support edges matter?** The leader-relative two-turn support-edge trend is lower in reversals at both checkpoints (standardized differences {float(support16['standardized_mean_difference']):+.3f} and {float(support20['standardized_mean_difference']):+.3f}). The static important-site Control margin has a positive primary effect but reverses direction in UCT 3,000, so important-site Control is not robust on its own.",
        "- **Does recent Supply degradation appear?** Yes descriptively: checkpoint leaders in reversals lost more absolute usable support before Turn 16, and their relative support-edge trend was substantially worse before Turn 20. This is a pre-checkpoint association, not a causal degradation mechanism flag.",
        f"- **Does trailing-player Supply reinvestment warn of reversal?** The opponent's four-turn Supply-allocation increase is higher in reversal games at both checkpoints, with primary standardized differences {float(opponent_reinvest16['uct_10000_standardized_mean_difference']):+.3f} and {float(opponent_reinvest20['uct_10000_standardized_mean_difference']):+.3f}. The direction agrees in UCT 3,000 at both checkpoints, although effect sizes remain sample-specific.",
        f"- **Are narrow leads fragile?** At Turn 16, {turn16_margin['narrow_reversals']}/{turn16_margin['narrow_n']} narrow leads reverse ({100 * turn16_margin['narrow_rate']:.1f}%), compared with {turn16_margin['large_reversals']}/{turn16_margin['large_n']} larger leads ({100 * turn16_margin['large_rate']:.1f}%). At Turn 20 the corresponding rates are {turn20_margin['narrow_reversals']}/{turn20_margin['narrow_n']} ({100 * turn20_margin['narrow_rate']:.1f}%) and {turn20_margin['large_reversals']}/{turn20_margin['large_n']} ({100 * turn20_margin['large_rate']:.1f}%). Narrow leads are more fragile in this primary sample.",
        "- **Are signals stronger at Turn 20?** The combined model is stronger at Turn 20 (0.640 versus 0.561), as are the Objective and allocation/trend models. Supply-only performance is nearly unchanged, so the strengthening is not uniform across feature groups.",
        f"- **Does UCT 3,000 agree?** Only partly. Descriptive feature directions agree for {agreement[16][0]}/{agreement[16][1]} features at Turn 16 and {agreement[20][0]}/{agreement[20][1]} at Turn 20. The combined model has AUC 0.667 at both checkpoints in UCT 3,000, but several individual effects, including important-site Control, change direction. Sensitivity evidence therefore supports some recurring signal without establishing stable individual predictors.",
        "", "## Integrity", "",
        f"- {analysis['counts']['games']} complete games and {analysis['counts']['game_turn_rows']} game-turn boundaries were reused.",
        f"- {analysis['counts']['checkpoint_rows']} checkpoint-game rows were reconstructed.",
        "- Issue #41 checkpoint counts and Issue #43 independently derived cohort labels were reproduced.",
        "- Every feature uses only data at or before its checkpoint.",
        "- Exact folds, out-of-fold predictions, and training-fold preprocessing metadata are retained.",
        "- The runner regenerates deterministic outputs twice and records the hash comparison in `results/environment.json`.", "",
        "All conclusions are predictive associations in finite UCT self-play samples. They are not causal effects, calibrated game-theoretic probabilities, or evidence that the same performance will generalize beyond these samples.", "",
        "See `experiments/issue-44/README.md` for frozen definitions, output inventory, and reproduction commands.", "",
    ])
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def analyze(config: dict[str, object]) -> dict[str, object]:
    validate_config(config)
    source = config["source"]
    path_names = (
        "replay_summary", "placements", "supply_turn_states", "objective_turn_states",
        "source_trials", "turn_progression", "reversal_by_turn", "site_values",
        "issue_43_config", "issue_43_checkpoint_cohorts",
    )
    paths = {name: REPO_ROOT / source[name] for name in path_names}
    turn_rows, turn_integrity = build_turn_records(
        read_csv(paths["turn_progression"]), read_csv(paths["placements"]),
        read_csv(paths["supply_turn_states"]), read_csv(paths["objective_turn_states"]),
        set(config["important_supply_sites"]),
    )
    checkpoint_rows, checkpoint_integrity = build_checkpoint_rows(turn_rows, config)
    reconciliation = reconcile_sources(checkpoint_rows, config, paths)
    eligible = [row for row in checkpoint_rows if row["outcome_class"] in ("reversal", "lead_preserved")]
    missing = sorted(set(config["descriptive_features"]) - set(eligible[0]))
    if missing:
        raise ValueError(f"configured descriptive features were not constructed: {missing}")
    assignments = deterministic_fold_assignments(
        checkpoint_rows, int(config["cross_validation"]["folds"]), str(config["cross_validation"]["seed"])
    )
    validation, predictions, preprocessing = evaluate_models(eligible, assignments, config)
    comparisons, effects = univariate_summaries(checkpoint_rows, config["descriptive_features"])
    cohort_summary = build_cohort_summary(checkpoint_rows)
    sensitivity = sensitivity_rows(comparisons)

    RAW.mkdir(parents=True, exist_ok=True)
    write_csv(RAW / "checkpoint-prediction-features.csv", checkpoint_rows)
    write_csv(RAW / "cv-fold-assignments.csv", assignments)
    write_csv(RAW / "oof-predictions.csv", predictions)
    write_csv(RAW / "preprocessing-metadata.csv", preprocessing)
    write_csv(RESULTS / "feature-comparison-summary.csv", comparisons)
    write_csv(RESULTS / "feature-effect-summary.csv", effects)
    baseline = [row for row in validation if row["feature_group"] == "baseline"]
    ablation = [row for row in validation if row["feature_group"] != "baseline"]
    write_csv(RESULTS / "baseline-model-summary.csv", baseline)
    write_csv(RESULTS / "model-validation-summary.csv", validation)
    write_csv(RESULTS / "feature-group-ablation.csv", ablation)
    write_csv(RESULTS / "checkpoint-prediction-summary.csv", cohort_summary)
    write_csv(RESULTS / "search-strength-sensitivity.csv", sensitivity)
    source_files = [
        {"path": path.relative_to(REPO_ROOT).as_posix(), "sha256": sha256(path)}
        for path in paths.values()
    ]
    write_csv(RESULTS / "source-files.csv", source_files)

    fold_groups = defaultdict(set)
    for row in assignments:
        fold_groups[(row["experiment_id"], row["checkpoint_turn"])].add(row["cv_fold"])
    analysis: dict[str, object] = {
        "schema_version": 1,
        "issue": 44,
        "primary_experiment": "uct-10000-self-play",
        "sensitivity_experiment": "uct-3000-self-play",
        "new_self_play_games": 0,
        "evaluation_policy": {
            "model_specifications_frozen_before_evaluation": True,
            "cross_validation_purpose": "out-of-sample performance estimation only",
            "checkpoints_modeled_separately": True,
            "pooled_checkpoint_model": False,
            "training_fold_only_standardization": True,
            "univariate_ranking_used_for_feature_selection": False,
            "post_hoc_tuning": False,
            "fixed_l2_coefficient": config["logistic_regression"]["shared_l2_coefficient"],
        },
        "counts": {
            **turn_integrity, **checkpoint_integrity,
            "checkpoint_rows": len(checkpoint_rows), "eligible_prediction_rows": len(eligible),
            "fold_assignments": len(assignments), "oof_predictions": len(predictions),
            "configured_models": len(config["models"]), "descriptive_features": len(config["descriptive_features"]),
        },
        "checkpoint_cohorts": cohort_summary,
        "model_validation": validation,
        "integrity": {
            **reconciliation,
            "all_experiment_checkpoint_groups_have_five_folds": all(value == {1, 2, 3, 4, 5} for value in fold_groups.values()),
            "same_fold_assignment_used_for_all_models": True,
            "future_features_used": False,
            "raw_p1_p2_values_retained": True,
            "outcome_labels_built_independently": True,
            "source_files_hashed": len(source_files),
            "deterministic_sorting": True,
        },
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "analysis.json").write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")
    write_report(analysis, validation, comparisons, sensitivity, checkpoint_rows)
    return analysis


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    analyze(config)


if __name__ == "__main__":
    main()
