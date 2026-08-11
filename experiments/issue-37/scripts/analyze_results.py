#!/usr/bin/env python3
"""Validate Issue #37 replay data and analyze Supply Point securing timing."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from statistics import mean, median
from typing import Iterable


SCRIPT = Path(__file__).resolve()
ISSUE_ROOT = SCRIPT.parent.parent
REPO_ROOT = ISSUE_ROOT.parent.parent
RESULTS = ISSUE_ROOT / "results"
RAW = RESULTS / "raw"
CONFIG_PATH = ISSUE_ROOT / "config.json"
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


def read_csv_directory(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in sorted(path.glob("*.csv")):
        rows.extend(read_csv(item))
    return rows


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


def validate_frozen_definitions(config: dict[str, object]) -> None:
    opportunity = config["securable_opportunity"]
    assert isinstance(opportunity, dict)
    if opportunity != {
        "version": 1,
        "unit": "player_supply_point_turn",
        "evaluation_point": "start_of_turn",
        "definition": "A Supply Point is securable when it is not Secured, the mover has fewer than the securing Piece count, and placements_needed_to_secure is no greater than the maximum number of additional placements that Ludii permits on that Supply Point during the current turn.",
        "secure_piece_count": 3,
        "legal_capacity_source": "ludii_context_clone_repeated_legal_supply_placement",
        "required_raw_fields": [
            "securable", "own_piece_count_at_turn_start",
            "opponent_piece_count_at_turn_start", "placements_needed_to_secure",
            "legal_max_additional_placements_this_turn",
        ],
        "current_rule_expectation": "Under the current 4x4 rules, own_count 1 or 2 is normally securable; this observation is not the analyzer predicate.",
    }:
        raise ValueError("securable-opportunity definition differs from frozen version 1")
    spatial = config["supply_spatial_categories"]
    assert isinstance(spatial, dict)
    if spatial != {
        "version": 1,
        "internal_ids": ["corner", "edge", "interior"],
        "report_labels": {
            "corner": "corner", "edge": "edge",
            "interior": "central (interior 3x3)",
        },
        "definitions": {
            "corner": "the four corner Supply Points",
            "edge": "non-corner Supply Points on the outer boundary",
            "interior": "the 3x3 non-edge interior Supply Points",
        },
        "expected_counts": {"corner": 4, "edge": 12, "interior": 9},
        "applies_to": [
            "securing_rate", "securing_timing", "future_usage",
            "securable_opportunity_rate", "winner_loser_comparison",
        ],
    }:
        raise ValueError("Supply spatial definition differs from frozen version 1")


def spatial_category(site: str) -> str:
    row, column = int(site[1]), int(site[2])
    boundaries = int(row in (0, 4)) + int(column in (0, 4))
    return "corner" if boundaries == 2 else "edge" if boundaries == 1 else "interior"


def phase(turn: int, config: dict[str, object]) -> str:
    phases = config["turn_phases"]
    assert isinstance(phases, list)
    for item in phases:
        if int(item["first_turn"]) <= turn <= int(item["last_turn"]):
            return str(item["id"])
    raise ValueError(f"turn outside configured phases: {turn}")


def result_status(player: int, winner: int) -> str:
    return "draw" if winner == 0 else "winner" if player == winner else "loser"


def adjacent_objectives(supply: str) -> list[str]:
    row, column = int(supply[1]), int(supply[2])
    result = []
    for objective_row in (row - 1, row):
        for objective_column in (column - 1, column):
            if 0 <= objective_row < 4 and 0 <= objective_column < 4:
                result.append(f"O{objective_row}{objective_column}")
    return sorted(result)


def adjacent_objectives_inverse(objective: str) -> list[str]:
    row, column = int(objective[1]), int(objective[2])
    return [
        f"S{row}{column}", f"S{row}{column + 1}",
        f"S{row + 1}{column}", f"S{row + 1}{column + 1}",
    ]


def securable_values(row: dict[str, str], secure_count: int) -> tuple[bool, int, int, int]:
    mover = int(row["mover"])
    p1 = int(row["p1_pieces_at_turn_start"])
    p2 = int(row["p2_pieces_at_turn_start"])
    own, opponent = (p1, p2) if mover == 1 else (p2, p1)
    needed = secure_count - own
    legal_capacity = int(row["legal_max_additional_placements_this_turn"])
    securable = (
        int(row["state_at_turn_start"]) < 3
        and own < secure_count
        and needed > 0
        and needed <= legal_capacity
    )
    return securable, own, opponent, needed


def average_or_zero(values: list[int]) -> float:
    return round(mean(values), 3) if values else 0.0


def median_or_zero(values: list[int]) -> float:
    return round(median(values), 3) if values else 0.0


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


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    validate_frozen_definitions(config)
    configured = {item["id"]: item for item in config["source"]["experiments"]}
    expected_ids = set(configured)
    secure_count = int(config["securable_opportunity"]["secure_piece_count"])

    issue32_rows = [
        row for row in read_csv_directory(REPO_ROOT / config["source"]["raw_results"])
        if row["experiment_id"] in expected_ids
    ]
    metadata = {(row["experiment_id"], int(row["game_index"])): row for row in issue32_rows}
    expected_games = sum(int(item["games"]) for item in configured.values())
    if len(metadata) != expected_games:
        raise ValueError(f"Issue #32 metadata count {len(metadata)} != {expected_games}")

    replay_rows = read_csv(RAW / "replay-summary.csv")
    if len(replay_rows) != expected_games:
        raise ValueError(f"replay count {len(replay_rows)} != {expected_games}")
    source_rows: list[dict[str, object]] = []
    for row in replay_rows:
        key = row["experiment_id"], int(row["game_index"])
        source = metadata.get(key)
        if source is None:
            raise ValueError(f"unexpected replay game: {key}")
        if row["winner"] != source["winner"] or row["final_board"] != source["final_board"]:
            raise ValueError(f"replay result mismatch: {key}")
        if row["moves"] != "72" or row["turns"] != "24" or row["end_type"] != "NaturalEnd":
            raise ValueError(f"replay invariant failed: {key}")
        trial = REPO_ROOT / row["trial_file"]
        if not trial.is_file() or row["trial_file"] != source["trial_file"]:
            raise ValueError(f"source trial mismatch: {key}")
        source_rows.append({
            "experiment_id": key[0], "iteration_limit": source["iteration_limit"],
            "game_index": key[1], "trial_file": row["trial_file"],
            "trial_sha256": sha256(trial),
        })
    write_csv(RESULTS / "source-trials.csv", source_rows)

    supply_rows = read_csv(RAW / "supply-turn-states.csv")
    objective_rows = read_csv(RAW / "objective-turn-states.csv")
    placement_rows = read_csv(RAW / "placements.csv")
    if len(supply_rows) != expected_games * 24 * 25:
        raise ValueError("per-turn Supply row count mismatch")
    if len(objective_rows) != expected_games * 24 * 16:
        raise ValueError("per-turn Objective row count mismatch")
    if len(placement_rows) != expected_games * 72:
        raise ValueError("placement row count mismatch")

    all_turn_rows = supply_rows + objective_rows
    continuity: dict[tuple[str, int, str], list[dict[str, str]]] = defaultdict(list)
    for row in all_turn_rows:
        site = row.get("supply_point", row.get("objective", ""))
        p1_end = int(row["p1_pieces_at_turn_end"])
        p2_end = int(row["p2_pieces_at_turn_end"])
        if int(row["state_at_turn_end"]) != state_from_counts(p1_end, p2_end):
            raise ValueError(
                f"Point-state mismatch: {row['experiment_id']} #{row['game_index']} "
                f"turn {row['turn_number']} {site}"
            )
        continuity[(row["experiment_id"], int(row["game_index"]), site)].append(row)
    for key, turns in continuity.items():
        turns.sort(key=lambda item: int(item["turn_number"]))
        if len(turns) != 24:
            raise ValueError(f"Point does not have 24 turn records: {key}")
        for before, after in zip(turns, turns[1:]):
            for value in ("state", "p1_pieces", "p2_pieces"):
                if before[f"{value}_at_turn_end"] != after[f"{value}_at_turn_start"]:
                    raise ValueError(f"Turn-state continuity mismatch: {key}")

    spatial_counts = Counter(spatial_category(site) for site in SUPPLY_POINTS)
    if dict(spatial_counts) != config["supply_spatial_categories"]["expected_counts"]:
        raise ValueError(f"spatial category sizes mismatch: {spatial_counts}")

    objective_index = {
        (row["experiment_id"], int(row["game_index"]), int(row["turn_number"]), row["objective"]): row
        for row in objective_rows
    }
    placements_by_game: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in placement_rows:
        placements_by_game[(row["experiment_id"], int(row["game_index"]))].append(row)

    supply_start_index = {
        (row["experiment_id"], int(row["game_index"]), int(row["turn_number"]), row["supply_point"]): row
        for row in supply_rows
    }
    used_sources: dict[tuple[str, int, int], set[str]] = defaultdict(set)
    objective_source_placements = 0
    for row in placement_rows:
        source_site = row["supply_source"]
        if not source_site:
            continue
        objective_source_placements += 1
        experiment, game_index = row["experiment_id"], int(row["game_index"])
        turn, mover = int(row["turn_number"]), int(row["mover"])
        if source_site not in adjacent_objectives_inverse(row["target"]):
            raise ValueError(f"non-adjacent Objective Supply source: {row}")
        source_state = int(supply_start_index[(experiment, game_index, turn, source_site)]["state_at_turn_start"])
        if source_state not in (mover, mover + 2):
            raise ValueError(f"uncontrolled Objective Supply source: {row}")
        used_key = experiment, game_index, turn
        if source_site in used_sources[used_key]:
            raise ValueError(f"Supply source reused in one turn: {row}")
        used_sources[used_key].add(source_site)

    per_turn_rows: list[dict[str, object]] = []
    opportunity_rows: list[dict[str, object]] = []
    supply_by_game_site: dict[tuple[str, int, str], list[dict[str, str]]] = defaultdict(list)
    for row in supply_rows:
        experiment = row["experiment_id"]
        game_index = int(row["game_index"])
        mover = int(row["mover"])
        turn = int(row["turn_number"])
        source = metadata[(experiment, game_index)]
        winner = int(source["winner"])
        category = spatial_category(row["supply_point"])
        securable, own, opponent, needed = securable_values(row, secure_count)
        secured_this_turn = (
            int(row["state_at_turn_start"]) < 3
            and int(row["state_at_turn_end"]) == mover + 2
        )
        common = {
            **row, "iteration_limit": int(source["iteration_limit"]),
            "turn_phase": phase(turn, config), "spatial_category": category,
            "spatial_report_label": config["supply_spatial_categories"]["report_labels"][category],
            "mover_result_status": result_status(mover, winner),
        }
        per_turn_rows.append(common)
        opportunity_rows.append({
            "experiment_id": experiment, "iteration_limit": int(source["iteration_limit"]),
            "game_index": game_index, "turn_number": turn, "turn_phase": phase(turn, config),
            "player": mover, "player_result_status": result_status(mover, winner),
            "supply_point": row["supply_point"], "spatial_category": category,
            "securable": str(securable).lower(),
            "own_piece_count_at_turn_start": own,
            "opponent_piece_count_at_turn_start": opponent,
            "placements_needed_to_secure": needed,
            "legal_max_additional_placements_this_turn": int(row["legal_max_additional_placements_this_turn"]),
            "secured_this_turn": str(secured_this_turn).lower(),
            "securable_but_left_unsecured": str(securable and not secured_this_turn).lower(),
        })
        supply_by_game_site[(experiment, game_index, row["supply_point"])].append(row)
        expected_current = int(row["state_at_turn_start"]) < 3 and own in (1, 2)
        if securable != expected_current:
            raise ValueError(
                f"current-rule securable expectation mismatch: {experiment} #{game_index} "
                f"turn {turn} {row['supply_point']}"
            )
    write_csv(RESULTS / "per-turn-supply-state.csv", per_turn_rows)

    event_rows: list[dict[str, object]] = []
    event_lookup: dict[tuple[str, int, str, int], int] = {}
    for (experiment, game_index, site), turns in sorted(supply_by_game_site.items()):
        source = metadata[(experiment, game_index)]
        winner = int(source["winner"])
        game_placements = placements_by_game[(experiment, game_index)]
        for row in turns:
            start_state, end_state = int(row["state_at_turn_start"]), int(row["state_at_turn_end"])
            if not (start_state < 3 <= end_state):
                continue
            player = end_state - 2
            turn = int(row["turn_number"])
            event_lookup[(experiment, game_index, site, player)] = turn
            p1_start, p2_start = int(row["p1_pieces_at_turn_start"]), int(row["p2_pieces_at_turn_start"])
            p1_end, p2_end = int(row["p1_pieces_at_turn_end"]), int(row["p2_pieces_at_turn_end"])
            objectives = [
                objective_index[(experiment, game_index, turn, objective)]
                for objective in adjacent_objectives(site)
            ]
            live = sum(int(item["state_at_turn_start"]) < 3 for item in objectives)
            placeable = 0
            capacity = 0
            objective_states = Counter()
            objective_state_records: list[str] = []
            for item in objectives:
                state = int(item["state_at_turn_start"])
                own_objective = int(item[f"p{player}_pieces_at_turn_start"])
                objective_state_records.append(
                    f"{item['objective']}:{state}:{item['p1_pieces_at_turn_start']}:"
                    f"{item['p2_pieces_at_turn_start']}"
                )
                objective_states["secured" if state >= 3 else "empty" if int(item["p1_pieces_at_turn_start"]) + int(item["p2_pieces_at_turn_start"]) == 0 else "live"] += 1
                if state < 3 and own_objective < 3:
                    placeable += 1
                    capacity += 3 - own_objective
            future_uses = [
                placement for placement in game_placements
                if placement["supply_source"] == site and int(placement["turn_number"]) > turn
            ]
            prior_turns = [item for item in turns if int(item["turn_number"]) < turn]
            controlled = [
                int(item["turn_number"]) for item in prior_turns
                if int(item["state_at_turn_end"]) in (player, player + 2)
            ]
            first_controlled = min(controlled) if controlled else turn
            opponent_placements = [
                placement for placement in game_placements
                if placement["target"] == site
                and int(placement["mover"]) != player
                and first_controlled < int(placement["turn_number"]) <= turn
            ]
            opportunity_values = securable_values(row, secure_count)
            if player != int(row["mover"]) or not opportunity_values[0]:
                raise ValueError(
                    f"Securing event did not begin as a legal opportunity: "
                    f"{experiment} #{game_index} turn {turn} {site}"
                )
            event_rows.append({
                "experiment_id": experiment, "iteration_limit": int(source["iteration_limit"]),
                "game_index": game_index, "player": player,
                "player_result_status": result_status(player, winner), "supply_point": site,
                "spatial_category": spatial_category(site), "securing_turn": turn,
                "securing_phase": phase(turn, config),
                "p1_piece_count_at_turn_start": p1_start,
                "p2_piece_count_at_turn_start": p2_start,
                "previous_unresolved_pattern": f"{p1_start}-{p2_start}",
                "securable_at_turn_start": "true",
                "placements_needed_to_secure": opportunity_values[3],
                "legal_max_additional_placements_this_turn": int(row["legal_max_additional_placements_this_turn"]),
                "p1_piece_count_immediately_before_securing": p1_end,
                "p2_piece_count_immediately_before_securing": p2_end,
                "first_controlled_turn": first_controlled,
                "opponent_placements_after_first_control_before_securing": len(opponent_placements),
                "contested_after_becoming_relevant": str(bool(opponent_placements)).lower(),
                "adjacent_objectives": len(objectives),
                "adjacent_objective_states_at_securing": ";".join(objective_state_records),
                "adjacent_live_objectives_at_securing": live,
                "adjacent_future_placeable_objectives_at_securing": placeable,
                "adjacent_future_placement_capacity_at_securing": capacity,
                "adjacent_empty_objectives_at_securing": objective_states["empty"],
                "adjacent_secured_objectives_at_securing": objective_states["secured"],
                "future_turns_used_as_supply": len({int(item["turn_number"]) for item in future_uses}),
                "future_objective_placements_supported": len(future_uses),
                "future_objectives_supported": ";".join(item["target"] for item in future_uses),
            })
    write_csv(RAW / "supply-events.csv", event_rows)

    for row in opportunity_rows:
        key = (row["experiment_id"], int(row["game_index"]), row["supply_point"], int(row["player"]))
        event_turn = event_lookup.get(key)
        row["eventually_secured_by_player"] = str(event_turn is not None).lower()
        row["eventual_securing_turn"] = "" if event_turn is None else event_turn
    write_csv(RAW / "securable-opportunities.csv", opportunity_rows)

    timing_rows: list[dict[str, object]] = []
    events_by_experiment: dict[str, list[dict[str, object]]] = defaultdict(list)
    for event in event_rows:
        events_by_experiment[str(event["experiment_id"])].append(event)
    for experiment in sorted(expected_ids):
        iteration_limit = int(configured[experiment]["iteration_limit"])
        events = events_by_experiment[experiment]
        first_by_game: dict[int, int] = {}
        for event in events:
            game = int(event["game_index"])
            first_by_game[game] = min(first_by_game.get(game, 25), int(event["securing_turn"]))
        for turn in range(1, 25):
            timing_rows.append({
                "experiment_id": experiment, "iteration_limit": iteration_limit,
                "scope": "first_securing_per_game", "turn_number": turn,
                "turn_phase": phase(turn, config),
                "count": sum(value == turn for value in first_by_game.values()),
                "cumulative_count": sum(value <= turn for value in first_by_game.values()),
            })
            timing_rows.append({
                "experiment_id": experiment, "iteration_limit": iteration_limit,
                "scope": "all_securing_events", "turn_number": turn,
                "turn_phase": phase(turn, config),
                "count": sum(int(event["securing_turn"]) == turn for event in events),
                "cumulative_count": sum(int(event["securing_turn"]) <= turn for event in events),
            })
            for player in (1, 2):
                player_events = [event for event in events if int(event["player"]) == player]
                timing_rows.append({
                    "experiment_id": experiment, "iteration_limit": iteration_limit,
                    "scope": f"player_{player}_securing_events", "turn_number": turn,
                    "turn_phase": phase(turn, config),
                    "count": sum(int(event["securing_turn"]) == turn for event in player_events),
                    "cumulative_count": sum(int(event["securing_turn"]) <= turn for event in player_events),
                })
        timing_rows.append({
            "experiment_id": experiment, "iteration_limit": iteration_limit,
            "scope": "first_securing_per_game", "turn_number": "never",
            "turn_phase": "never", "count": int(configured[experiment]["games"]) - len(first_by_game),
            "cumulative_count": len(first_by_game),
        })
    write_csv(RESULTS / "securing-timing-summary.csv", timing_rows)

    winner_rows: list[dict[str, object]] = []
    for experiment in sorted(expected_ids):
        source_games = [row for row in issue32_rows if row["experiment_id"] == experiment]
        for status in ("winner", "loser", "draw"):
            for category in ("all", "corner", "edge", "interior"):
                player_units = [
                    (int(game["game_index"]), player)
                    for game in source_games for player in (1, 2)
                    if result_status(player, int(game["winner"])) == status
                ]
                selected_events = [
                    event for event in event_rows
                    if event["experiment_id"] == experiment
                    and event["player_result_status"] == status
                    and (category == "all" or event["spatial_category"] == category)
                ]
                selected_opportunities = [
                    row for row in opportunity_rows
                    if row["experiment_id"] == experiment
                    and row["player_result_status"] == status
                    and row["securable"] == "true"
                    and (category == "all" or row["spatial_category"] == category)
                ]
                turns = [int(event["securing_turn"]) for event in selected_events]
                winner_rows.append({
                    "experiment_id": experiment,
                    "iteration_limit": int(configured[experiment]["iteration_limit"]),
                    "player_result_status": status, "spatial_category": category,
                    "player_games": len(player_units), "securing_events": len(selected_events),
                    "mean_securing_turn": average_or_zero(turns),
                    "median_securing_turn": median_or_zero(turns),
                    "securable_opportunities": len(selected_opportunities),
                    "opportunities_taken": sum(row["secured_this_turn"] == "true" for row in selected_opportunities),
                    "opportunity_take_rate": round(
                        sum(row["secured_this_turn"] == "true" for row in selected_opportunities)
                        / len(selected_opportunities), 6
                    ) if selected_opportunities else 0.0,
                })
    write_csv(RESULTS / "winner-loser-comparison.csv", winner_rows)

    spatial_rows: list[dict[str, object]] = []
    opportunity_summary: list[dict[str, object]] = []
    for experiment in sorted(expected_ids):
        for category in ("corner", "edge", "interior"):
            selected_events = [event for event in event_rows if event["experiment_id"] == experiment and event["spatial_category"] == category]
            selected_opportunities = [row for row in opportunity_rows if row["experiment_id"] == experiment and row["spatial_category"] == category and row["securable"] == "true"]
            turns = [int(event["securing_turn"]) for event in selected_events]
            uses = [int(event["future_objective_placements_supported"]) for event in selected_events]
            taken = sum(row["secured_this_turn"] == "true" for row in selected_opportunities)
            eventually_secured = sum(
                row["eventually_secured_by_player"] == "true" for row in selected_opportunities
            )
            spatial_rows.append({
                "experiment_id": experiment,
                "iteration_limit": int(configured[experiment]["iteration_limit"]),
                "spatial_category": category,
                "report_label": config["supply_spatial_categories"]["report_labels"][category],
                "points_per_board": config["supply_spatial_categories"]["expected_counts"][category],
                "securing_events": len(selected_events), "mean_securing_turn": average_or_zero(turns),
                "median_securing_turn": median_or_zero(turns),
                "securable_opportunities": len(selected_opportunities),
                "opportunities_taken": taken,
                "securing_rate_per_opportunity": round(taken / len(selected_opportunities), 6) if selected_opportunities else 0.0,
                "mean_future_objective_placements_supported": average_or_zero(uses),
                "events_with_future_usage_rate": round(sum(value > 0 for value in uses) / len(uses), 6) if uses else 0.0,
            })
            opportunity_summary.append({
                "experiment_id": experiment,
                "iteration_limit": int(configured[experiment]["iteration_limit"]),
                "spatial_category": category, "securable_opportunities": len(selected_opportunities),
                "secured_same_turn": taken, "left_unsecured": len(selected_opportunities) - taken,
                "left_unsecured_rate": round((len(selected_opportunities) - taken) / len(selected_opportunities), 6) if selected_opportunities else 0.0,
                "eventually_secured": eventually_secured,
                "never_secured": len(selected_opportunities) - eventually_secured,
                "never_secured_rate": round((len(selected_opportunities) - eventually_secured) / len(selected_opportunities), 6) if selected_opportunities else 0.0,
            })
    write_csv(RESULTS / "spatial-comparison.csv", spatial_rows)
    write_csv(RESULTS / "securable-opportunities.csv", opportunity_summary)
    write_csv(RESULTS / "future-usage-summary.csv", event_rows)

    event_patterns = Counter(str(event["previous_unresolved_pattern"]) for event in event_rows)
    primary_events = events_by_experiment["uct-10000-self-play"]
    analysis = {
        "schema_version": 1,
        "primary_experiment": "uct-10000-self-play",
        "games": len(metadata),
        "securing_events": len(event_rows),
        "primary_securing_events": len(primary_events),
        "primary_phase_counts": dict(Counter(str(event["securing_phase"]) for event in primary_events)),
        "pre_securing_pattern_counts": dict(sorted(event_patterns.items())),
        "definitions": {
            "securable_opportunity": config["securable_opportunity"],
            "supply_spatial_categories": config["supply_spatial_categories"],
        },
        "integrity": {
            "source_trials_hashed": len(source_rows),
            "trials_legally_replayed_to_natural_end": len(replay_rows),
            "moves_72_turns_24": len(replay_rows),
            "final_boards_and_winners_match_issue_32": len(replay_rows),
            "supply_turn_rows": len(supply_rows),
            "objective_turn_rows": len(objective_rows),
            "placement_rows": len(placement_rows),
            "point_turn_states_match_piece_counts": len(all_turn_rows),
            "point_turn_state_chains_verified": len(continuity),
            "objective_supply_sources_verified": objective_source_placements,
            "current_rule_securable_expectation_verified": len(opportunity_rows),
            "spatial_category_counts_verified": dict(spatial_counts),
        },
    }
    (RESULTS / "analysis.json").write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")
    print(
        f"validated {len(replay_rows)} games; analyzed {len(event_rows)} Securing events "
        f"and {sum(row['securable'] == 'true' for row in opportunity_rows)} legal opportunities"
    )


if __name__ == "__main__":
    main()
