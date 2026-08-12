#!/usr/bin/env python3
"""Reconstruct and describe checkpoint reversal mechanisms for Issue #43."""

from __future__ import annotations

import csv
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from statistics import mean
from typing import Iterable, Sequence


SCRIPT = Path(__file__).resolve()
ISSUE_ROOT = SCRIPT.parent.parent
REPO_ROOT = ISSUE_ROOT.parent.parent
RESULTS = ISSUE_ROOT / "results"
RAW = RESULTS / "raw"
CONFIG_PATH = ISSUE_ROOT / "config.json"
README_PATH = ISSUE_ROOT / "README.md"
REPORT_PATH = REPO_ROOT / "experiments" / "issue-43.md"
COMPONENTS = [
    "secured_objective_difference",
    "advantage_objective_difference",
    "objective_piece_difference",
]
LAYERS = ["secured_objectives", "advantage_objectives", "objective_pieces"]
IMPORTANT = {"S23", "S21", "S12", "S13", "S22"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, object]]) -> None:
    values = list(rows)
    if not values:
        raise ValueError(f"refusing to write empty output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(values[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(values)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sign(value: int | float) -> int:
    return 1 if value > 0 else -1 if value < 0 else 0


def lex_sign(values: Sequence[int]) -> int:
    return next((sign(value) for value in values if value), 0)


def decisive_layer(values: Sequence[int], perspective: int = 1) -> str | None:
    for name, value in zip(LAYERS, values):
        if int(value) * perspective:
            return name
    return None


def global_strict_persistence_turn(signs: Sequence[int], winner: int) -> int | None:
    if winner not in (1, 2):
        return None
    direction = 1 if winner == 1 else -1
    for index in range(len(signs)):
        if all(value * direction > 0 for value in signs[index:]):
            return index + 1
    return None


def post_checkpoint_takeover_turn(
    signs: Sequence[int], winner: int, checkpoint: int, cohort: str
) -> int | None:
    if cohort != "reversal" or winner not in (1, 2):
        return None
    direction = 1 if winner == 1 else -1
    for turn in range(checkpoint + 1, len(signs) + 1):
        if all(value * direction > 0 for value in signs[turn - 1:]):
            return turn
    raise ValueError("decisive reversal has no strict post-checkpoint takeover")


def objective_adjacencies(objective: str) -> tuple[str, str, str, str]:
    row, column = int(objective[1]), int(objective[2])
    return (
        f"S{row}{column}", f"S{row}{column + 1}",
        f"S{row + 1}{column}", f"S{row + 1}{column + 1}",
    )


def usable_supply_support_edges(
    supply_states: dict[str, int], objective_states: dict[str, int], player: int
) -> int:
    """Count usable Supply x adjacent live Objective pairs, without deduplication."""
    usable = {site for site, state in supply_states.items() if state in (player, player + 2)}
    return sum(
        supply in usable
        for objective, state in objective_states.items() if state in (0, 1, 2)
        for supply in objective_adjacencies(objective)
    )


def add_relative_fields(
    target: dict[str, object], prefix: str, p1: int | float, p2: int | float,
    checkpoint_leader: int | None, winner: int,
) -> None:
    """Append perspectives and leave caller-owned raw values untouched."""
    target[f"{prefix}_p1"] = p1
    target[f"{prefix}_p2"] = p2
    target[f"{prefix}_p1_minus_p2"] = p1 - p2
    target[f"{prefix}_checkpoint_leader_relative"] = (
        p1 - p2 if checkpoint_leader == 1 else p2 - p1 if checkpoint_leader == 2 else ""
    )
    target[f"{prefix}_eventual_winner_relative"] = (
        p1 - p2 if winner == 1 else p2 - p1 if winner == 2 else ""
    )


def mixed_mechanism_flag(mechanisms: dict[str, object]) -> int:
    names = (
        "mechanism_secured_objective_reversal",
        "mechanism_advantage_conversion_reversal",
        "mechanism_objective_piece_tiebreak_reversal",
        "mechanism_supply_degradation", "mechanism_supply_reinvestment",
    )
    return int(sum(int(mechanisms.get(name, 0)) for name in names) >= 2)


def controlled(state: int, player: int) -> bool:
    return state in (player, player + 2)


def state_from_counts(p1: int, p2: int) -> int:
    if p1 == 3:
        return 3
    if p2 == 3:
        return 4
    return 1 if p1 > p2 else 2 if p2 > p1 else 0


def validate_config(config: dict[str, object]) -> None:
    if config["checkpoints"] != {"primary": [16, 20], "reference": [8, 12]}:
        raise ValueError("checkpoint definition changed")
    if config["comparison_components"] != COMPONENTS:
        raise ValueError("lexicographic comparison changed")
    if set(config["important_supply_sites"]) != IMPORTANT:
        raise ValueError("important Supply set changed")
    supply = config["supply_mechanisms"]
    expected = {
        "lookback_turns": 4, "baseline_turns": 4, "minimum_indicators": 2,
        "usage_mean_change_threshold": 0.5,
        "placement_mean_change_threshold": 0.5,
        "support_edge_change_threshold": 1,
    }
    if any(supply[key] != value for key, value in expected.items()):
        raise ValueError("Supply mechanism threshold changed")
    edge = config["usable_supply_support_edges"]
    if not edge["count_each_adjacency_pair"] or edge["deduplicate_by_supply_point"] or edge["deduplicate_by_objective"]:
        raise ValueError("usable support-edge definition changed")
    phrase = "A usable Supply-support edge is one player-controlled-or-secured Supply Point × adjacent live Objective pair. Shared Objectives are counted once for each usable Supply adjacency."
    if phrase not in README_PATH.read_text(encoding="utf-8"):
        raise ValueError("README lacks frozen support-edge definition")


def window_mean(rows: dict[int, dict[str, object]], turns: range, field: str) -> float:
    return mean(float(rows[turn][field]) for turn in turns)


def own_turn_mean(
    rows: dict[int, dict[str, object]], turns: range, player: int, field: str
) -> float:
    values = [float(rows[turn][field]) for turn in turns if int(rows[turn]["mover"]) == player]
    if not values:
        raise ValueError("Supply mechanism window contains no player turn")
    return mean(values)


def supply_mechanism_evidence(
    rows: dict[int, dict[str, object]], takeover: int, checkpoint_leader: int,
    winner: int, settings: dict[str, object],
) -> dict[str, object]:
    lookback = int(settings["lookback_turns"])
    baseline = int(settings["baseline_turns"])
    look_turns = range(takeover - lookback, takeover)
    base_turns = range(takeover - lookback - baseline, takeover - lookback)
    edge_threshold = float(settings["support_edge_change_threshold"])
    usage_threshold = float(settings["usage_mean_change_threshold"])
    placement_threshold = float(settings["placement_mean_change_threshold"])

    def total(player: int, stem: str) -> int:
        return sum(int(rows[turn][f"{stem}_p{player}"]) for turn in look_turns)

    leader_edge_base = window_mean(rows, base_turns, f"usable_supply_support_edges_p{checkpoint_leader}")
    leader_edge_look = window_mean(rows, look_turns, f"usable_supply_support_edges_p{checkpoint_leader}")
    leader_edge_delta = leader_edge_look - leader_edge_base
    winner_edge_base = window_mean(rows, base_turns, f"usable_supply_support_edges_p{winner}")
    winner_edge_look = window_mean(rows, look_turns, f"usable_supply_support_edges_p{winner}")
    winner_edge_delta = winner_edge_look - winner_edge_base
    leader_usage_base = own_turn_mean(rows, base_turns, checkpoint_leader, f"supply_source_uses_p{checkpoint_leader}")
    leader_usage_look = own_turn_mean(rows, look_turns, checkpoint_leader, f"supply_source_uses_p{checkpoint_leader}")
    winner_placement_base = own_turn_mean(rows, base_turns, winner, f"supply_placements_p{winner}")
    winner_placement_look = own_turn_mean(rows, look_turns, winner, f"supply_placements_p{winner}")

    degradation_flags = {
        "indicator_degradation_unsecured_control_loss": total(checkpoint_leader, "unsecured_control_losses") >= 1,
        "indicator_degradation_important_control_loss": total(checkpoint_leader, "important_control_losses") >= 1,
        "indicator_degradation_support_edge_decline": leader_edge_delta <= -edge_threshold,
        "indicator_degradation_source_usage_decline": leader_usage_look - leader_usage_base <= -usage_threshold,
    }
    reinvestment_flags = {
        "indicator_reinvestment_supply_placement_increase": winner_placement_look - winner_placement_base >= placement_threshold,
        "indicator_reinvestment_new_secured_supply": total(winner, "new_secured_supply") >= 1,
        "indicator_reinvestment_important_control_gain": total(winner, "important_control_gains") >= 1,
        "indicator_reinvestment_support_edge_increase": winner_edge_delta >= edge_threshold,
    }
    minimum = int(settings["minimum_indicators"])
    return {
        "supply_baseline_start_turn": base_turns.start,
        "supply_baseline_end_turn": base_turns.stop - 1,
        "supply_lookback_start_turn": look_turns.start,
        "supply_lookback_end_turn": look_turns.stop - 1,
        "leader_baseline_usable_support_edges": round(leader_edge_base, 6),
        "leader_lookback_usable_support_edges": round(leader_edge_look, 6),
        "leader_usable_support_edge_delta": round(leader_edge_delta, 6),
        "winner_baseline_usable_support_edges": round(winner_edge_base, 6),
        "winner_lookback_usable_support_edges": round(winner_edge_look, 6),
        "winner_usable_support_edge_delta": round(winner_edge_delta, 6),
        "configured_support_edge_change_threshold": edge_threshold,
        "leader_baseline_supply_source_usage_mean": round(leader_usage_base, 6),
        "leader_lookback_supply_source_usage_mean": round(leader_usage_look, 6),
        "configured_usage_mean_change_threshold": usage_threshold,
        "winner_baseline_supply_placement_mean": round(winner_placement_base, 6),
        "winner_lookback_supply_placement_mean": round(winner_placement_look, 6),
        "configured_placement_mean_change_threshold": placement_threshold,
        **{key: int(value) for key, value in degradation_flags.items()},
        **{key: int(value) for key, value in reinvestment_flags.items()},
        "degradation_indicator_count": sum(degradation_flags.values()),
        "reinvestment_indicator_count": sum(reinvestment_flags.values()),
        "configured_minimum_indicators": minimum,
        "mechanism_supply_degradation": int(sum(degradation_flags.values()) >= minimum),
        "mechanism_supply_reinvestment": int(sum(reinvestment_flags.values()) >= minimum),
    }


def build_turn_features(
    progression: list[dict[str, str]], placements: list[dict[str, str]],
    supply_rows: list[dict[str, str]], objective_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], dict[str, int]]:
    place_index: dict[tuple[str, int, int], list[dict[str, str]]] = defaultdict(list)
    supply_index: dict[tuple[str, int, int], list[dict[str, str]]] = defaultdict(list)
    objective_index: dict[tuple[str, int, int], list[dict[str, str]]] = defaultdict(list)
    for row in placements:
        place_index[(row["experiment_id"], int(row["game_index"]), int(row["turn_number"]))].append(row)
    for row in supply_rows:
        supply_index[(row["experiment_id"], int(row["game_index"]), int(row["turn_number"]))].append(row)
    for row in objective_rows:
        objective_index[(row["experiment_id"], int(row["game_index"]), int(row["turn_number"]))].append(row)

    output: list[dict[str, object]] = []
    edge_checks = source_checks = 0
    previous_supply_allocation: dict[tuple[str, int, int], int] = {}
    continuity: dict[tuple[str, int, str], tuple[int, int, int]] = {}
    state_checks = adjacency_checks = ownership_checks = 0
    for source in progression:
        key = source["experiment_id"], int(source["game_index"]), int(source["turn_number"])
        supplies, objectives, moves = supply_index[key], objective_index[key], place_index[key]
        if len(supplies) != 25 or len(objectives) != 16 or len(moves) != 3:
            raise ValueError(f"invalid turn dimensions: {key}")
        mover = int(source["mover"])
        sources = [row["supply_source"] for row in moves if row["supply_source"]]
        if len(sources) != len(set(sources)):
            raise ValueError(f"Supply source reused: {key}")
        source_checks += len(sources)
        supply_states = {row["supply_point"]: int(row["state_at_turn_end"]) for row in supplies}
        objective_states = {row["objective"]: int(row["state_at_turn_end"]) for row in objectives}
        for item, site_field in [
            *[(item, "supply_point") for item in supplies],
            *[(item, "objective") for item in objectives],
        ]:
            site = item[site_field]
            start = (int(item["state_at_turn_start"]), int(item["p1_pieces_at_turn_start"]), int(item["p2_pieces_at_turn_start"]))
            end = (int(item["state_at_turn_end"]), int(item["p1_pieces_at_turn_end"]), int(item["p2_pieces_at_turn_end"]))
            if end[0] != state_from_counts(end[1], end[2]):
                raise ValueError(f"state/count mismatch: {key} {site}")
            prior = continuity.get((key[0], key[1], site))
            if prior is not None and prior != start:
                raise ValueError(f"state continuity mismatch: {key} {site}")
            continuity[(key[0], key[1], site)] = end
            state_checks += 1
        for move in moves:
            if move["target_type"] != "objective":
                continue
            supplied_by = move["supply_source"]
            if supplied_by not in objective_adjacencies(move["target"]):
                raise ValueError(f"non-adjacent Supply source: {key} {move}")
            adjacency_checks += 1
            if not controlled(supply_states[supplied_by], mover):
                raise ValueError(f"uncontrolled Supply source: {key} {move}")
            ownership_checks += 1
        row: dict[str, object] = {}
        for name, value in source.items():
            if name in ("experiment_id", "final_result"):
                row[name] = value
            elif value == "":
                row[name] = ""
            else:
                try:
                    row[name] = int(value)
                except ValueError:
                    row[name] = value
        row["turn_number"] = key[2]
        row["game_index"] = key[1]
        row["live_objectives"] = sum(state in (0, 1, 2) for state in objective_states.values())
        values = [int(row[field]) for field in COMPONENTS]
        row["full_lexicographic_leader"] = lex_sign(values)
        row["current_decisive_layer"] = decisive_layer(values) or ""
        total_supply_placements = sum(item["target_type"] == "supply" for item in moves)
        row["turn_allocation_type"] = (
            "all_supply" if total_supply_placements == 3
            else "all_objective" if total_supply_placements == 0 else "mixed"
        )
        prior_key = key[0], key[1], mover
        prior_supply = previous_supply_allocation.get(prior_key)
        row["supply_placement_change_from_prior_own_turn"] = "" if prior_supply is None else total_supply_placements - prior_supply
        previous_supply_allocation[prior_key] = total_supply_placements
        for player in (1, 2):
            edges = usable_supply_support_edges(supply_states, objective_states, player)
            row[f"usable_supply_support_edges_p{player}"] = edges
            row[f"unsecured_control_losses_p{player}"] = sum(
                int(item["state_at_turn_start"]) == player and int(item["state_at_turn_end"]) != player
                for item in supplies
            )
            row[f"important_control_losses_p{player}"] = sum(
                item["supply_point"] in IMPORTANT
                and controlled(int(item["state_at_turn_start"]), player)
                and not controlled(int(item["state_at_turn_end"]), player)
                for item in supplies
            )
            row[f"important_control_gains_p{player}"] = sum(
                item["supply_point"] in IMPORTANT
                and not controlled(int(item["state_at_turn_start"]), player)
                and controlled(int(item["state_at_turn_end"]), player)
                for item in supplies
            )
            row[f"new_secured_supply_p{player}"] = sum(
                int(item["state_at_turn_start"]) < 3 and int(item["state_at_turn_end"]) == player + 2
                for item in supplies
            )
            row[f"contested_supply_points_p{player}"] = sum(
                int(item["p1_pieces_at_turn_end"]) > 0 and int(item["p2_pieces_at_turn_end"]) > 0
                for item in supplies
            )
            row[f"supply_placements_p{player}"] = sum(
                mover == player and item["target_type"] == "supply" for item in moves
            )
            row[f"objective_placements_p{player}"] = sum(
                mover == player and item["target_type"] == "objective" for item in moves
            )
            row[f"supply_source_uses_p{player}"] = len(sources) if mover == player else 0
            row[f"important_supply_source_uses_p{player}"] = (
                sum(site in IMPORTANT for site in sources) if mover == player else 0
            )
            source_states = {item["supply_point"]: int(item["state_at_turn_start"]) for item in supplies}
            row[f"supply_source_uses_after_securing_p{player}"] = (
                sum(source_states[site] == player + 2 for site in sources) if mover == player else 0
            )
            row[f"objective_advantage_to_neutral_p{player}"] = sum(
                int(item["state_at_turn_start"]) == player and int(item["state_at_turn_end"]) == 0
                for item in objectives
            )
            row[f"objective_advantage_to_opponent_p{player}"] = sum(
                int(item["state_at_turn_start"]) == player and int(item["state_at_turn_end"]) == 3 - player
                for item in objectives
            )
        edge_checks += 2
        output.append(row)
    return output, {
        "usable_support_edge_player_turns_verified": edge_checks,
        "point_turn_states_verified": state_checks,
        "point_state_chains_verified": len(continuity),
        "supply_sources_verified": source_checks,
        "supply_source_adjacencies_verified": adjacency_checks,
        "supply_source_ownerships_verified": ownership_checks,
    }


def classify_objective_mechanisms(
    rows: dict[int, dict[str, object]], checkpoint: int, takeover: int, winner: int
) -> dict[str, object]:
    direction = 1 if winner == 1 else -1
    flags = [False, False, False]
    event_turns: list[list[int]] = [[], [], []]
    previous = [int(rows[checkpoint][field]) * direction for field in COMPONENTS]
    for turn in range(checkpoint + 1, takeover + 1):
        current = [int(rows[turn][field]) * direction for field in COMPONENTS]
        conditions = [
            previous[0] < 0 <= current[0] or previous[0] <= 0 < current[0],
            current[0] == 0 and (previous[1] < 0 <= current[1] or previous[1] <= 0 < current[1]),
            current[0] == current[1] == 0 and (previous[2] <= 0 < current[2]),
        ]
        for index, condition in enumerate(conditions):
            if condition:
                flags[index] = True
                event_turns[index].append(turn)
        previous = current
    return {
        "mechanism_secured_objective_reversal": int(flags[0]),
        "mechanism_advantage_conversion_reversal": int(flags[1]),
        "mechanism_objective_piece_tiebreak_reversal": int(flags[2]),
        "secured_objective_reversal_event_turns": ";".join(map(str, event_turns[0])),
        "advantage_conversion_event_turns": ";".join(map(str, event_turns[1])),
        "objective_piece_tiebreak_event_turns": ";".join(map(str, event_turns[2])),
    }


def make_feature_row(
    source: dict[str, object], checkpoint_leader: int | None, winner: int
) -> dict[str, object]:
    row = dict(source)
    pairs = {
        "secured_objectives": (int(source["p1_secured_objectives"]), int(source["p2_secured_objectives"])),
        "advantage_objectives": (int(source["p1_advantage_objectives"]), int(source["p2_advantage_objectives"])),
        "objective_pieces": (int(source["p1_objective_pieces"]), int(source["p2_objective_pieces"])),
        "secured_supply": (int(source["p1_secured_supply"]), int(source["p2_secured_supply"])),
        "unsecured_controlled_supply": (int(source["p1_unsecured_controlled_supply"]), int(source["p2_unsecured_controlled_supply"])),
        "usable_supply_support_edges": (int(source["usable_supply_support_edges_p1"]), int(source["usable_supply_support_edges_p2"])),
    }
    for name, (p1, p2) in pairs.items():
        add_relative_fields(row, name, p1, p2, checkpoint_leader, winner)
    return row


def analyze(config: dict[str, object]) -> tuple[dict[str, object], list[dict[str, str]]]:
    source = config["source"]
    paths = {name: REPO_ROOT / source[name] for name in (
        "turn_progression", "lead_change_summary", "reversal_by_turn", "placements", "supply_turn_states",
        "objective_turn_states", "source_trials", "site_values",
    )}
    progression = read_csv(paths["turn_progression"])
    turns, integrity = build_turn_features(
        progression, read_csv(paths["placements"]), read_csv(paths["supply_turn_states"]),
        read_csv(paths["objective_turn_states"]),
    )
    by_game: dict[tuple[str, int], dict[int, dict[str, object]]] = defaultdict(dict)
    for row in turns:
        by_game[(str(row["experiment_id"]), int(row["game_index"]))][int(row["turn_number"])] = row
    if any(len(rows) != 24 for rows in by_game.values()):
        raise ValueError("not every game has 24 turns")

    issue_41_persistence = {
        (row["experiment_id"], int(row["game_index"])): row["strict_persistent_lead_turn"]
        for row in read_csv(paths["lead_change_summary"])
        if row["comparison_layer"] == "full_lexicographic"
    }

    checkpoints = config["checkpoints"]["reference"] + config["checkpoints"]["primary"]
    cohort_rows: list[dict[str, object]] = []
    window_rows: list[dict[str, object]] = []
    aligned_rows: list[dict[str, object]] = []
    for (experiment, game), rows in sorted(by_game.items()):
        winner = int(rows[1]["winner"])
        signs = [lex_sign([int(rows[t][field]) for field in COMPONENTS]) for t in range(1, 25)]
        global_turn = global_strict_persistence_turn(signs, winner)
        expected_global = issue_41_persistence[(experiment, game)]
        if ("" if global_turn is None else str(global_turn)) != expected_global:
            raise ValueError(f"Issue #41 strict persistence mismatch: {(experiment, game)}")
        final_values = [int(rows[24][field]) for field in COMPONENTS]
        final_layer = decisive_layer(final_values)
        for checkpoint in checkpoints:
            checkpoint_sign = signs[checkpoint - 1]
            leader = 1 if checkpoint_sign > 0 else 2 if checkpoint_sign < 0 else None
            if leader is None:
                cohort = "tied_at_checkpoint"
            elif winner == 0:
                cohort = "eventual_draw"
            elif winner == leader:
                cohort = "lead_preserved"
            else:
                cohort = "reversal"
            takeover = post_checkpoint_takeover_turn(signs, winner, checkpoint, cohort)
            base: dict[str, object] = {
                "experiment_id": experiment, "game_index": game,
                "checkpoint_turn": checkpoint, "cohort": cohort,
                "checkpoint_leader": "" if leader is None else leader,
                "winner": winner,
                "global_strict_persistence_turn": "" if global_turn is None else global_turn,
                "post_checkpoint_takeover_turn": "" if takeover is None else takeover,
                "takeover_decisive_layer": "" if takeover is None else decisive_layer(
                    [int(rows[takeover][field]) for field in COMPONENTS], 1 if winner == 1 else -1
                ),
                "final_decisive_layer": "" if winner == 0 else final_layer,
            }
            checkpoint_features = make_feature_row(rows[checkpoint], leader, winner)
            for name, value in checkpoint_features.items():
                if name not in ("experiment_id", "game_index", "winner", "final_result"):
                    base[f"checkpoint_{name}"] = value
            mechanisms = {
                "mechanism_secured_objective_reversal": 0,
                "mechanism_advantage_conversion_reversal": 0,
                "mechanism_objective_piece_tiebreak_reversal": 0,
                "mechanism_supply_degradation": 0,
                "mechanism_supply_reinvestment": 0,
                "mechanism_mixed": 0,
            }
            if takeover is not None:
                mechanisms.update(classify_objective_mechanisms(rows, checkpoint, takeover, winner))
                mechanisms.update(supply_mechanism_evidence(
                    rows, takeover, int(leader), winner, config["supply_mechanisms"]
                ))
                mechanisms["mechanism_mixed"] = mixed_mechanism_flag(mechanisms)
            base.update(mechanisms)
            cohort_rows.append(base)

            for turn in range(checkpoint, 25):
                item = make_feature_row(rows[turn], leader, winner)
                prefix = {
                    "experiment_id": experiment, "game_index": game,
                    "checkpoint_turn": checkpoint, "cohort": cohort,
                    "checkpoint_leader": "" if leader is None else leader, "winner": winner,
                    "global_strict_persistence_turn": "" if global_turn is None else global_turn,
                    "post_checkpoint_takeover_turn": "" if takeover is None else takeover,
                    "absolute_turn": turn,
                    "relative_to_checkpoint": turn - checkpoint,
                    "relative_to_takeover": "" if takeover is None else turn - takeover,
                    "takeover_decisive_layer": base["takeover_decisive_layer"],
                    "final_decisive_layer": base["final_decisive_layer"],
                }
                prefix.update(mechanisms)
                prefix.update({key: value for key, value in item.items() if key not in ("experiment_id", "game_index")})
                window_rows.append(prefix)
            if takeover is not None:
                for relative in config["aligned_window_relative_turns"]:
                    turn = takeover + int(relative)
                    if not 1 <= turn <= 24:
                        continue
                    item = make_feature_row(rows[turn], leader, winner)
                    aligned = {
                        "experiment_id": experiment, "game_index": game,
                        "checkpoint_turn": checkpoint, "cohort": cohort,
                        "checkpoint_leader": leader, "winner": winner,
                        "global_strict_persistence_turn": global_turn,
                        "post_checkpoint_takeover_turn": takeover,
                        "relative_turn": relative, "absolute_turn": turn,
                        "takeover_decisive_layer": base["takeover_decisive_layer"],
                        "final_decisive_layer": base["final_decisive_layer"],
                    }
                    aligned.update(mechanisms)
                    aligned.update({key: value for key, value in item.items() if key not in ("experiment_id", "game_index")})
                    aligned_rows.append(aligned)

    # Reproduce Issue #41 full-lexicographic checkpoint counts.
    prior = read_csv(paths["reversal_by_turn"])
    reconciled = 0
    for experiment in {row["experiment_id"] for row in prior}:
        for checkpoint in checkpoints:
            expected = next(row for row in prior if row["experiment_id"] == experiment and row["comparison_layer"] == "full_lexicographic" and int(row["turn_number"]) == checkpoint)
            selected = [row for row in cohort_rows if row["experiment_id"] == experiment and int(row["checkpoint_turn"]) == checkpoint]
            actual = {
                "current_leader_eventually_wins": sum(row["cohort"] == "lead_preserved" for row in selected),
                "current_leader_eventually_loses": sum(row["cohort"] == "reversal" for row in selected),
                "eventual_draws_from_current_lead": sum(row["cohort"] == "eventual_draw" for row in selected),
                "games_tied_at_turn": sum(row["cohort"] == "tied_at_checkpoint" for row in selected),
            }
            if any(actual[key] != int(expected[key]) for key in actual):
                raise ValueError(f"Issue #41 checkpoint mismatch: {experiment} Turn {checkpoint}")
            reconciled += 1

    RAW.mkdir(parents=True, exist_ok=True)
    write_csv(RAW / "checkpoint-cohorts.csv", cohort_rows)
    write_csv(RAW / "reversal-windows.csv", window_rows)
    write_csv(RAW / "aligned-reversal-windows.csv", aligned_rows)

    def aggregate(groups: dict[tuple[object, ...], list[dict[str, object]]], names: list[str], fields: list[str]) -> list[dict[str, object]]:
        result = []
        for key, values in sorted(groups.items()):
            row = {name: value for name, value in zip(names, key)}
            row["games"] = len(values)
            for field in fields:
                available = [float(value[field]) for value in values if value[field] != ""]
                row[f"mean_{field}"] = round(mean(available), 6) if available else ""
            result.append(row)
        return result

    cohort_groups: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for row in cohort_rows:
        cohort_groups[(row["experiment_id"], row["checkpoint_turn"], row["cohort"])].append(row)
    cohort_summary = aggregate(cohort_groups, ["experiment_id", "checkpoint_turn", "cohort"], [
        "checkpoint_secured_objectives_checkpoint_leader_relative",
        "checkpoint_advantage_objectives_checkpoint_leader_relative",
        "checkpoint_objective_pieces_checkpoint_leader_relative",
        "checkpoint_usable_supply_support_edges_checkpoint_leader_relative",
    ])
    write_csv(RESULTS / "reversal-cohort-summary.csv", cohort_summary)

    reversals = [row for row in cohort_rows if row["cohort"] == "reversal"]
    mech_rows = []
    mechanism_names = [
        "mechanism_secured_objective_reversal", "mechanism_advantage_conversion_reversal",
        "mechanism_objective_piece_tiebreak_reversal", "mechanism_supply_degradation",
        "mechanism_supply_reinvestment", "mechanism_mixed",
    ]
    for experiment in sorted({row["experiment_id"] for row in reversals}):
        for checkpoint in checkpoints:
            selected = [row for row in reversals if row["experiment_id"] == experiment and row["checkpoint_turn"] == checkpoint]
            for mechanism in mechanism_names:
                count = sum(int(row[mechanism]) for row in selected)
                mech_rows.append({"experiment_id": experiment, "checkpoint_turn": checkpoint, "mechanism": mechanism, "reversal_games": len(selected), "flagged_games": count, "share": round(count / len(selected), 6) if selected else ""})
    write_csv(RESULTS / "reversal-mechanism-summary.csv", mech_rows)

    objective_groups: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for row in reversals:
        objective_groups[(row["experiment_id"], row["checkpoint_turn"], row["takeover_decisive_layer"], row["final_decisive_layer"])].append(row)
    objective_summary = aggregate(objective_groups, ["experiment_id", "checkpoint_turn", "takeover_decisive_layer", "final_decisive_layer"], [
        "mechanism_secured_objective_reversal", "mechanism_advantage_conversion_reversal", "mechanism_objective_piece_tiebreak_reversal"
    ])
    write_csv(RESULTS / "objective-reversal-summary.csv", objective_summary)

    supply_groups: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for row in reversals:
        supply_groups[(row["experiment_id"], row["checkpoint_turn"])].append(row)
    supply_summary = aggregate(supply_groups, ["experiment_id", "checkpoint_turn"], [
        "mechanism_supply_degradation", "mechanism_supply_reinvestment",
        "leader_usable_support_edge_delta", "winner_usable_support_edge_delta",
        "degradation_indicator_count", "reinvestment_indicator_count",
    ])
    write_csv(RESULTS / "supply-reversal-summary.csv", supply_summary)

    allocation_rows = []
    for (experiment, checkpoint), selected in sorted(supply_groups.items()):
        aligned = [row for row in aligned_rows if row["experiment_id"] == experiment and row["checkpoint_turn"] == checkpoint and -3 <= row["relative_turn"] <= 0]
        allocation_rows.append({
            "experiment_id": experiment, "checkpoint_turn": checkpoint,
            "reversal_games": len(selected),
            "mean_eventual_winner_supply_placements_pre_takeover": round(mean(
                float(row[f"supply_placements_p{int(row['winner'])}"]) for row in aligned
            ), 6),
            "mean_eventual_winner_objective_placements_pre_takeover": round(mean(
                float(row[f"objective_placements_p{int(row['winner'])}"]) for row in aligned
            ), 6),
            "mean_important_supply_source_uses_pre_takeover": round(mean(
                float(row[f"important_supply_source_uses_p{int(row['winner'])}"]) for row in aligned
            ), 6),
        })
    write_csv(RESULTS / "allocation-reversal-summary.csv", allocation_rows)

    comparison_groups: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for row in cohort_rows:
        if row["cohort"] in ("reversal", "lead_preserved"):
            comparison_groups[(row["experiment_id"], row["checkpoint_turn"], row["cohort"])].append(row)
    comparison = aggregate(comparison_groups, ["experiment_id", "checkpoint_turn", "cohort"], [
        "checkpoint_secured_objectives_checkpoint_leader_relative",
        "checkpoint_advantage_objectives_checkpoint_leader_relative",
        "checkpoint_objective_pieces_checkpoint_leader_relative",
        "checkpoint_secured_supply_checkpoint_leader_relative",
        "checkpoint_unsecured_controlled_supply_checkpoint_leader_relative",
        "checkpoint_usable_supply_support_edges_checkpoint_leader_relative",
        "checkpoint_live_objectives",
    ])
    write_csv(RESULTS / "lead-preserved-comparison.csv", comparison)

    margin_rows = []
    for row in cohort_rows:
        if row["cohort"] == "tied_at_checkpoint":
            continue
        values = [int(row[f"checkpoint_{field}"]) for field in COMPONENTS]
        index = next(index for index, value in enumerate(values) if value)
        magnitude = abs(values[index])
        margin_rows.append({**row, "checkpoint_decisive_layer": LAYERS[index], "margin_tier": "narrow" if magnitude == 1 else "large"})
    margin_groups: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for row in margin_rows:
        margin_groups[(row["experiment_id"], row["checkpoint_turn"], row["checkpoint_decisive_layer"], row["margin_tier"])].append(row)
    stability = []
    for key, selected in sorted(margin_groups.items()):
        denominator = len(selected)
        stability.append({
            "experiment_id": key[0], "checkpoint_turn": key[1], "checkpoint_decisive_layer": key[2], "margin_tier": key[3],
            "games": denominator, "lead_preserved": sum(row["cohort"] == "lead_preserved" for row in selected),
            "reversals": sum(row["cohort"] == "reversal" for row in selected),
            "eventual_draws": sum(row["cohort"] == "eventual_draw" for row in selected),
            "reversal_rate": round(sum(row["cohort"] == "reversal" for row in selected) / denominator, 6),
        })
    write_csv(RESULTS / "checkpoint-margin-stability.csv", stability)

    source_files = [{"path": path.relative_to(REPO_ROOT).as_posix(), "sha256": sha256(path)} for path in paths.values()]
    write_csv(RESULTS / "source-files.csv", source_files)
    primary_reversals = [row for row in reversals if row["experiment_id"] == "uct-10000-self-play"]
    decisive_agreement = sum(row["takeover_decisive_layer"] == row["final_decisive_layer"] for row in primary_reversals)
    headline: dict[str, object] = {}
    for experiment in ("uct-10000-self-play", "uct-3000-self-play"):
        headline[experiment] = {}
        for checkpoint in checkpoints:
            all_rows = [row for row in cohort_rows if row["experiment_id"] == experiment and row["checkpoint_turn"] == checkpoint]
            reversal_set = [row for row in all_rows if row["cohort"] == "reversal"]
            preserved = [row for row in all_rows if row["cohort"] == "lead_preserved"]
            layer_counts = {layer: sum(row["takeover_decisive_layer"] == layer for row in reversal_set) for layer in LAYERS}
            important = sum(
                int(row.get("indicator_degradation_important_control_loss", 0))
                or int(row.get("indicator_reinvestment_important_control_gain", 0))
                for row in reversal_set
            )
            headline[experiment][str(checkpoint)] = {
                "reversals": len(reversal_set), "lead_preserved": len(preserved),
                "eventual_draws": sum(row["cohort"] == "eventual_draw" for row in all_rows),
                "tied_at_checkpoint": sum(row["cohort"] == "tied_at_checkpoint" for row in all_rows),
                "mean_turns_to_takeover": round(mean(int(row["post_checkpoint_takeover_turn"]) - checkpoint for row in reversal_set), 6),
                "one_turn_takeover_share": round(sum(int(row["post_checkpoint_takeover_turn"]) - checkpoint == 1 for row in reversal_set) / len(reversal_set), 6),
                "supply_degradation_share": round(mean(int(row["mechanism_supply_degradation"]) for row in reversal_set), 6),
                "supply_reinvestment_share": round(mean(int(row["mechanism_supply_reinvestment"]) for row in reversal_set), 6),
                "important_site_involvement_share": round(important / len(reversal_set), 6),
                "takeover_decisive_layer_counts": layer_counts,
            }
    analysis = {
        "schema_version": 1,
        "primary_experiment": "uct-10000-self-play",
        "sensitivity_experiment": "uct-3000-self-play",
        "new_self_play_games": 0,
        "definitions": {
            "checkpoints": config["checkpoints"],
            "timing": {
                "global_strict_persistence_turn": "Issue #41 whole-game strict persistence",
                "post_checkpoint_takeover_turn": "first strict permanent eventual-winner lead strictly after a reversal checkpoint",
            },
            "usable_supply_support_edges": config["usable_supply_support_edges"],
            "supply_mechanisms": config["supply_mechanisms"],
            "important_supply_sites": config["important_supply_sites"],
        },
        "counts": {
            "games": len(by_game), "game_turns": len(turns),
            "checkpoint_rows": len(cohort_rows), "reversal_rows": len(reversals),
            "primary_reversals": len(primary_reversals),
        },
        "takeover_vs_final_decisive_layer": {
            "primary_agreement_games": decisive_agreement,
            "primary_reversal_games": len(primary_reversals),
            "primary_agreement_rate": round(decisive_agreement / len(primary_reversals), 6),
        },
        "checkpoint_findings": headline,
        "integrity": {
            **integrity, "issue_41_checkpoint_cells_reconciled": reconciled,
            "source_files_hashed": len(source_files), "raw_perspectives_retained": True,
            "deterministic_sorting": True,
        },
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "analysis.json").write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")
    return analysis, source_files


def write_report(analysis: dict[str, object]) -> None:
    counts = analysis["counts"]
    relation = analysis["takeover_vs_final_decisive_layer"]
    primary = analysis["checkpoint_findings"]["uct-10000-self-play"]["20"]
    sensitivity = analysis["checkpoint_findings"]["uct-3000-self-play"]["20"]
    layers = primary["takeover_decisive_layer_counts"]
    text = f"""# Issue 43: Reversal mechanisms in Heitan

## Summary

This analysis compares checkpoint reversals with preserved leads in the 100-game UCT 10,000 primary sample and reports the 100-game UCT 3,000 sample separately as sensitivity evidence. It reuses validated Issues #37, #39, and #41 records and generates no new self-play.

Across both search strengths and all four checkpoints, {counts['reversal_rows']} checkpoint-game rows are reversals; {counts['primary_reversals']} are in the primary sample. Results are descriptive temporal associations, not causal estimates.

## Timing and scoring layers

Global strict persistence and post-checkpoint takeover are stored separately. Reversal-aligned Turn 0 is always the post-checkpoint strict permanent takeover; preserved leads are not assigned an artificial takeover.

In the primary reversal rows, takeover and final decisive layers agree in {relation['primary_agreement_games']} of {relation['primary_reversal_games']} cases ({100 * relation['primary_agreement_rate']:.1f}%). The full cross-tabulation is in `results/objective-reversal-summary.csv`.

At Turn 20, {primary['reversals']} leaders were reversed, {primary['lead_preserved']} preserved their lead, {primary['eventual_draws']} led games drew, and {primary['tied_at_checkpoint']} games were tied. Permanent takeover followed after a mean {primary['mean_turns_to_takeover']:.2f} turns; {100 * primary['one_turn_takeover_share']:.1f}% completed in one turn, so the sample contains both sudden and multi-turn reversals. Takeover was decided by Secured Objectives in {layers['secured_objectives']} cases, Advantage Objectives in {layers['advantage_objectives']}, and Objective Pieces in {layers['objective_pieces']}.

## Supply mechanisms

Supply degradation and reinvestment use pre-frozen four-turn baseline and lookback windows and require at least two configured indicators. The usable-support measure counts every controlled-or-secured Supply Point × adjacent live Objective pair, including separate edges to a shared Objective. See `results/supply-reversal-summary.csv` and the supporting raw cohort columns.

For primary Turn-20 reversals, {100 * primary['supply_degradation_share']:.1f}% meet the pre-frozen degradation rule and {100 * primary['supply_reinvestment_share']:.1f}% meet the reinvestment rule. A primary important-site gain or loss occurs in {100 * primary['important_site_involvement_share']:.1f}%. These are sequence associations, not evidence that Supply changes caused the later Objective result.

The UCT 3,000 Turn-20 sensitivity cohort has {sensitivity['reversals']} reversals; degradation and reinvestment flags occur in {100 * sensitivity['supply_degradation_share']:.1f}% and {100 * sensitivity['supply_reinvestment_share']:.1f}%, respectively. Differences between search strengths are reported descriptively rather than pooled.

## Outputs and integrity

- {counts['games']} complete games and {counts['game_turns']} game-turns were reused.
- All configured checkpoint cells reconcile with Issue #41.
- Raw P1/P2, checkpoint-leader-relative, and eventual-winner-relative values are retained separately.
- Source paths and SHA-256 hashes are recorded.

See `experiments/issue-43/README.md` for frozen definitions and reproduction commands.
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    validate_config(config)
    analysis, _ = analyze(config)
    write_report(analysis)


if __name__ == "__main__":
    main()
