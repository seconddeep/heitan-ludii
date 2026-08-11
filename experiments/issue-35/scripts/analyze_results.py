#!/usr/bin/env python3
"""Validate and analyze Issue #35 one-turn UCT search results."""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import random
from statistics import mean, median
from typing import Callable


SCRIPT = Path(__file__).resolve()
ISSUE_ROOT = SCRIPT.parent.parent
REPO_ROOT = ISSUE_ROOT.parent.parent
RESULTS = ISSUE_ROOT / "results"
SITE_NAMES = [f"S{r}{c}" for r in range(5) for c in range(5)] + [
    f"O{r}{c}" for r in range(4) for c in range(4)
]
FROZEN_SIGNATURE_CONFIG = {
    "version": 1,
    "encoding": "compact_sorted_key_json",
    "ignore_placement_order": True,
    "include_supply_sites": True,
    "include_supply_sources": True,
    "include_objective_sites": True,
    "include_secured_supply_transition": True,
    "include_unresolved_supply_transition": True,
    "include_spatial_category": True,
    "include_resulting_state_summary": False,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_raw() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted((RESULTS / "raw").glob("*.csv")):
        with path.open(newline="", encoding="utf-8-sig") as handle:
            rows.extend(csv.DictReader(handle))
    if not rows:
        raise ValueError("no Issue #35 raw rows found")
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty output: {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def split(value: str) -> list[str]:
    return [] if not value else value.split(";")


def parse_board(value: str) -> dict[str, tuple[int, int, int]]:
    board: dict[str, tuple[int, int, int]] = {}
    for item in value.split("|"):
        name, state, p1, p2 = item.split(":")
        board[name] = int(state), int(p1), int(p2)
    if list(board) != SITE_NAMES:
        raise ValueError("board does not contain the canonical 41-site sequence")
    return board


def serialize_position_board(position: dict[str, object]) -> str:
    board = position["complete_starting_board_state"]
    assert isinstance(board, dict)
    return "|".join(
        f"{name}:{board[name]['state']}:{board[name]['p1_pieces']}:{board[name]['p2_pieces']}"
        for name in SITE_NAMES
    )


def state_from_counts(p1: int, p2: int) -> int:
    if p1 == 3:
        return 3
    if p2 == 3:
        return 4
    return 1 if p1 > p2 else 2 if p2 > p1 else 0


def plan_signature(row: dict[str, str], signature_config: dict[str, object]) -> str:
    if signature_config != FROZEN_SIGNATURE_CONFIG:
        raise ValueError("config.json does not match frozen plan_signature version 1")
    supply_sites = sorted(split(row["supply_placement_sites"]))
    objective_sites = sorted(split(row["objective_placement_sites"]))
    spatial_counts = Counter(split(row["spatial_categories"]))
    signature = {
        "version": 1,
        "placement_target_category": {
            "supply_placements": len(supply_sites),
            "objective_placements": len(objective_sites),
        },
        "supply_strategy": {
            "placement_sites": supply_sites,
            "source_sites": sorted(split(row["supply_source_sites"])),
            "secured_transitions": sorted(split(row["secured_supply_transitions"])),
            "unresolved_transitions": sorted(split(row["unresolved_supply_transitions"])),
        },
        "objective_strategy": {
            "placement_sites": objective_sites,
            "piece_count": len(objective_sites),
        },
        "spatial_strategy": {
            "central": spatial_counts["central"],
            "edge": spatial_counts["edge"],
            "corner": spatial_counts["corner"],
        },
    }
    return json.dumps(signature, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def validate(
    rows: list[dict[str, str]],
    config: dict[str, object],
    positions_document: dict[str, object],
) -> dict[str, int]:
    if config["plan_signature"] != FROZEN_SIGNATURE_CONFIG:
        raise ValueError("frozen plan_signature configuration mismatch")
    positions = {item["position_id"]: item for item in positions_document["positions"]}
    allowed_budgets = set(int(value) for value in config["required_iteration_budgets"])
    allowed_budgets.add(int(config["optional_iteration_budget"]))
    unique_repetitions: set[tuple[str, int, int]] = set()
    unique_trials: set[str] = set()
    source_hashes_checked: set[str] = set()
    groups: defaultdict[tuple[str, int], set[int]] = defaultdict(set)

    for row in rows:
        position_id = row["position_id"]
        if position_id not in positions:
            raise ValueError(f"unknown position: {position_id}")
        position = positions[position_id]
        prefix = int(row["prefix_placement_count"])
        mover = int(row["mover"])
        budget = int(row["requested_iteration_budget"])
        repetition = int(row["repetition_id"])
        if prefix <= 0 or prefix % 3 or prefix != int(position["prefix_placement_count"]):
            raise ValueError(f"invalid turn-boundary prefix: {position_id}")
        if mover != int(position["mover"]) or int(row["ending_mover"]) == mover:
            raise ValueError(f"mover transition failed: {position_id} repetition {repetition}")
        if budget not in allowed_budgets or int(row["effective_iteration_budget"]) != budget:
            raise ValueError(f"iteration budget mismatch: {position_id} repetition {repetition}")
        key = position_id, budget, repetition
        if key in unique_repetitions:
            raise ValueError(f"duplicate repetition ID: {key}")
        unique_repetitions.add(key)
        groups[(position_id, budget)].add(repetition)

        source = REPO_ROOT / row["source_trial"]
        if row["source_trial"] != position["source_trl_path"] or not source.is_file():
            raise ValueError(f"source trial mismatch: {position_id}")
        if row["source_trial"] not in source_hashes_checked:
            if sha256(source) != position["source_trial_hash"]:
                raise ValueError(f"source trial hash mismatch: {source}")
            source_hashes_checked.add(row["source_trial"])
        trial = REPO_ROOT / row["trial_path"]
        if row["trial_path"] in unique_trials or not trial.is_file():
            raise ValueError(f"duplicate or missing generated trial: {trial}")
        unique_trials.add(row["trial_path"])

        ordered = split(row["ordered_sequence"])
        targets = split(row["placement_targets"])
        if len(ordered) != 3 or len(targets) != 3:
            raise ValueError(f"turn does not contain three placements: {key}")
        if row["starting_board_state"] != serialize_position_board(position):
            raise ValueError(f"starting board differs from positions.json: {key}")
        before = parse_board(row["starting_board_state"])
        after = parse_board(row["resulting_turn_state"])
        before_pieces = sum(p1 + p2 for _, p1, p2 in before.values())
        after_pieces = sum(p1 + p2 for _, p1, p2 in after.values())
        if after_pieces != before_pieces + 3:
            raise ValueError(f"turn did not add exactly three Pieces: {key}")

        sources = split(row["supply_source_sites"])
        if len(sources) != len(split(row["objective_placement_sites"])) or len(set(sources)) != len(sources):
            raise ValueError(f"invalid Supply source multiplicity: {key}")
        for source_site in sources:
            if before[source_site][0] not in (mover, mover + 2):
                raise ValueError(f"Objective used illegal Supply source {source_site}: {key}")
        for target in set(targets):
            state, p1, p2 = after[target]
            if state != state_from_counts(p1, p2):
                raise ValueError(f"Point state was not updated after third placement: {target} {key}")

        move_lines = [line for line in trial.read_text(encoding="utf-8").splitlines()
                      if line.startswith("Move=")]
        if len(move_lines) != prefix + 3:
            raise ValueError(f"generated trial length mismatch: {key}")
        expected_marker = f"Move=[Move:mover={mover},"
        if any(not line.startswith(expected_marker) for line in move_lines[-3:]):
            raise ValueError(f"three placements were not made by one player: {key}")
        if any("[SetNextPlayer:player=" not in line for line in move_lines[-3:-1]):
            raise ValueError(f"mover was not retained for first two placements: {key}")
        if "[SetState:type=Vertex" not in move_lines[-1]:
            raise ValueError(f"third placement lacks Point-state update: {key}")

        # Construction itself validates that every raw row can produce the frozen key.
        plan_signature(row, config["plan_signature"])

    for group, repetitions in groups.items():
        if repetitions != set(range(1, max(repetitions) + 1)):
            raise ValueError(f"non-contiguous repetition IDs: {group}")
    return {
        "raw_rows": len(rows),
        "source_trials_hash_verified": len(source_hashes_checked),
        "legal_turn_prefixes_replayed_by_runner": len(rows),
        "turn_boundaries_verified": len(rows),
        "three_piece_increments_verified": len(rows),
        "same_player_three_placements_verified": len(rows),
        "opponent_turn_transitions_verified": len(rows),
        "third_placement_state_updates_verified": len(rows),
        "objective_supply_sources_verified": len(rows),
        "unique_repetition_ids": len(unique_repetitions),
        "unique_trial_paths": len(unique_trials),
        "plan_signatures_regenerated": len(rows),
    }


def grouped(rows: list[dict[str, str]]) -> dict[tuple[str, int], list[dict[str, str]]]:
    result: defaultdict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        result[(row["position_id"], int(row["requested_iteration_budget"]))].append(row)
    return dict(result)


def frequency_rows(
    groups: dict[tuple[str, int], list[dict[str, str]]],
    key_name: str,
    key_function: Callable[[dict[str, str]], str],
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for (position, budget), samples in sorted(groups.items()):
        counts = Counter(key_function(row) for row in samples)
        for rank, (value, count) in enumerate(counts.most_common(), start=1):
            result.append({
                "position_id": position, "iteration_budget": budget,
                "rank": rank, key_name: value, "count": count,
                "frequency": round(count / len(samples), 6),
            })
    return result


def distribution(values: list[str]) -> dict[str, float]:
    counts = Counter(values)
    return {key: count / len(values) for key, count in counts.items()}


def total_variation(left: dict[str, float], right: dict[str, float]) -> float:
    return 0.5 * sum(abs(left.get(key, 0.0) - right.get(key, 0.0))
                     for key in set(left) | set(right))


def js_divergence(left: dict[str, float], right: dict[str, float]) -> float:
    keys = set(left) | set(right)
    middle = {key: (left.get(key, 0.0) + right.get(key, 0.0)) / 2 for key in keys}
    def kl(values: dict[str, float]) -> float:
        return sum(value * math.log2(value / middle[key])
                   for key, value in values.items() if value > 0)
    return 0.5 * (kl(left) + kl(right))


def entropy(values: list[str]) -> float:
    return -sum(probability * math.log(probability)
                for probability in distribution(values).values())


def ranks(values: list[float]) -> list[float]:
    result = [0.0] * len(values)
    ordered = sorted(range(len(values)), key=lambda index: values[index])
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[cursor]]:
            end += 1
        average_rank = (cursor + 1 + end) / 2
        for index in ordered[cursor:end]:
            result[index] = average_rank
        cursor = end
    return result


def correlation(left: list[float], right: list[float]) -> float:
    left_mean, right_mean = mean(left), mean(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    denominator = math.sqrt(
        sum((value - left_mean) ** 2 for value in left)
        * sum((value - right_mean) ** 2 for value in right)
    )
    return 0.0 if not denominator else numerator / denominator


def site_profile(samples: list[dict[str, str]]) -> list[float]:
    counts = Counter(target for row in samples for target in split(row["placement_targets"]))
    return [counts[name] / len(samples) for name in SITE_NAMES]


def bootstrap_tv(
    left: list[str], right: list[str], samples: int, generator: random.Random
) -> tuple[float, float]:
    estimates: list[float] = []
    for _ in range(samples):
        left_sample = generator.choices(left, k=len(left))
        right_sample = generator.choices(right, k=len(right))
        estimates.append(total_variation(distribution(left_sample), distribution(right_sample)))
    estimates.sort()
    low = estimates[int(0.025 * (samples - 1))]
    high = estimates[int(0.975 * (samples - 1))]
    return low, high


def compare_budgets(
    groups: dict[tuple[str, int], list[dict[str, str]]], config: dict[str, object]
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    signature_config = config["plan_signature"]
    classification_config = config["convergence_classification"]
    bootstrap_samples = int(classification_config["bootstrap_samples"])
    generator = random.Random(int(classification_config["bootstrap_seed"]))
    key_functions: dict[str, Callable[[dict[str, str]], str]] = {
        "ordered_sequence": lambda row: row["ordered_sequence"],
        "plan_signature": lambda row: plan_signature(row, signature_config),
        "resulting_turn_state": lambda row: row["resulting_turn_state"],
    }
    comparisons: list[dict[str, object]] = []
    positions = sorted({position for position, _ in groups})
    for position in positions:
        budgets = sorted(budget for candidate, budget in groups if candidate == position)
        for lower, higher in zip(budgets, budgets[1:]):
            lower_rows, higher_rows = groups[(position, lower)], groups[(position, higher)]
            for key_type, function in key_functions.items():
                left = [function(row) for row in lower_rows]
                right = [function(row) for row in higher_rows]
                left_distribution, right_distribution = distribution(left), distribution(right)
                tv = total_variation(left_distribution, right_distribution)
                low, high = bootstrap_tv(left, right, bootstrap_samples, generator)
                top_k = int(classification_config["top_k"])
                left_top = {key for key, _ in Counter(left).most_common(top_k)}
                right_top = {key for key, _ in Counter(right).most_common(top_k)}
                union = left_top | right_top
                comparisons.append({
                    "position_id": position, "key_type": key_type,
                    "lower_budget": lower, "higher_budget": higher,
                    "lower_repetitions": len(left), "higher_repetitions": len(right),
                    "top_k": top_k, "top_k_common": len(left_top & right_top),
                    "top_k_agreement_jaccard": round(len(left_top & right_top) / len(union), 6),
                    "total_variation": round(tv, 6),
                    "total_variation_bootstrap_95ci_low": round(low, 6),
                    "total_variation_bootstrap_95ci_high": round(high, 6),
                    "jensen_shannon_divergence": round(js_divergence(left_distribution, right_distribution), 6),
                    "lower_shannon_entropy": round(entropy(left), 6),
                    "higher_shannon_entropy": round(entropy(right), 6),
                    "lower_effective_number_of_plans": round(math.exp(entropy(left)), 6),
                    "higher_effective_number_of_plans": round(math.exp(entropy(right)), 6),
                    "site_usage_spearman": round(correlation(
                        ranks(site_profile(lower_rows)), ranks(site_profile(higher_rows))
                    ), 6),
                })

    classifications: list[dict[str, object]] = []
    recommendations: list[dict[str, object]] = []
    recommendation_lower = int(config["optional_budget_selection"]["comparison_lower_budget"])
    recommendation_higher = int(config["optional_budget_selection"]["comparison_higher_budget"])
    optional_budget = int(config["optional_iteration_budget"])
    optional_threshold = float(config["optional_budget_selection"]["plan_total_variation_threshold"])
    for position in positions:
        available_budgets = {budget for candidate, budget in groups if candidate == position}
        if optional_budget in available_budgets:
            lower, higher = recommendation_higher, optional_budget
        else:
            lower, higher = recommendation_lower, recommendation_higher
        match = next((row for row in comparisons
                      if row["position_id"] == position and row["key_type"] == "plan_signature"
                      and row["lower_budget"] == lower and row["higher_budget"] == higher), None)
        if match is None:
            continue
        high_rows = groups[(position, higher)]
        high_plans = [plan_signature(row, signature_config) for row in high_rows]
        top_rate = Counter(high_plans).most_common(1)[0][1] / len(high_plans)
        effective = math.exp(entropy(high_plans))
        tv = float(match["total_variation"])
        if tv >= float(classification_config["unstable_plan_total_variation_min"]):
            classification = "search_instability"
        elif tv <= float(classification_config["stable_plan_total_variation_max"]):
            if top_rate >= float(classification_config["dominant_plan_rate_min"]):
                classification = "convergence_toward_a_small_plan_set"
            elif effective >= float(classification_config["diverse_effective_plan_count_min"]):
                classification = "strategic_diversity"
            else:
                classification = "inconclusive"
        else:
            classification = "inconclusive"
        classifications.append({
            "position_id": position, "lower_budget": lower, "higher_budget": higher,
            "plan_total_variation": round(tv, 6),
            "higher_budget_top_plan_rate": round(top_rate, 6),
            "higher_budget_effective_number_of_plans": round(effective, 6),
            "classification": classification,
        })
        recommendation_match = next((row for row in comparisons
                                     if row["position_id"] == position
                                     and row["key_type"] == "plan_signature"
                                     and row["lower_budget"] == recommendation_lower
                                     and row["higher_budget"] == recommendation_higher), None)
        if recommendation_match is None:
            continue
        recommendation_tv = float(recommendation_match["total_variation"])
        recommended = recommendation_tv >= optional_threshold
        recommendations.append({
            "position_id": position,
            "comparison": f"{recommendation_lower}-{recommendation_higher}",
            "plan_total_variation": round(recommendation_tv, 6), "threshold": optional_threshold,
            "recommend_300000": str(recommended).lower(),
            "reason": "plan distribution still changes materially" if recommended
                      else "required budgets do not meet the optional-depth threshold",
        })
    return comparisons, classifications, recommendations


def main() -> None:
    config = json.loads((ISSUE_ROOT / "config.json").read_text(encoding="utf-8"))
    positions = json.loads((ISSUE_ROOT / "positions.json").read_text(encoding="utf-8"))
    rows = read_raw()
    validation = validate(rows, config, positions)
    groups = grouped(rows)
    signature_config = config["plan_signature"]

    output_names = (
        "ordered-sequence-frequencies.csv", "plan-signature-frequencies.csv",
        "resulting-state-frequencies.csv", "site-statistics.csv",
        "supply-transitions.csv", "budget-comparison.csv",
        "convergence-classification.csv", "recommend-300k.csv", "analysis.json",
        "turn-summary.csv", "search-timings.csv",
    )
    for name in output_names:
        path = RESULTS / name
        if path.is_file():
            path.unlink()

    ordered_frequencies = frequency_rows(
        groups, "ordered_sequence", lambda row: row["ordered_sequence"]
    )
    plan_frequencies = frequency_rows(
        groups, "plan_signature", lambda row: plan_signature(row, signature_config)
    )
    resulting_frequencies = frequency_rows(
        groups, "resulting_turn_state", lambda row: row["resulting_turn_state"]
    )

    site_rows: list[dict[str, object]] = []
    transition_rows: list[dict[str, object]] = []
    turn_summaries: list[dict[str, object]] = []
    search_timings: list[dict[str, object]] = []
    for (position, budget), samples in sorted(groups.items()):
        targets = Counter(target for row in samples for target in split(row["placement_targets"]))
        sources = Counter(source for row in samples for source in split(row["supply_source_sites"]))
        supply_counts = [len(split(row["supply_placement_sites"])) for row in samples]
        objective_counts = [len(split(row["objective_placement_sites"])) for row in samples]
        secured_counts = [len(split(row["secured_supply_transitions"])) for row in samples]
        unresolved_counts = [len(split(row["unresolved_supply_transitions"])) for row in samples]
        spatial = Counter(value for row in samples for value in split(row["spatial_categories"]))
        ordered_values = [row["ordered_sequence"] for row in samples]
        plan_values = [plan_signature(row, signature_config) for row in samples]
        resulting_values = [row["resulting_turn_state"] for row in samples]
        runtime_seconds = [float(row["turn_runtime_ms"]) / 1000 for row in samples]
        turn_summaries.append({
            "position_id": position, "iteration_budget": budget,
            "repetitions": len(samples),
            "average_supply_placements": round(mean(supply_counts), 6),
            "average_objective_placements": round(mean(objective_counts), 6),
            "turns_securing_supply": sum(value > 0 for value in secured_counts),
            "supply_securing_turn_rate": round(sum(value > 0 for value in secured_counts) / len(samples), 6),
            "average_newly_secured_supply_points": round(mean(secured_counts), 6),
            "average_unresolved_supply_transitions": round(mean(unresolved_counts), 6),
            "central_target_rate": round(spatial["central"] / (3 * len(samples)), 6),
            "edge_target_rate": round(spatial["edge"] / (3 * len(samples)), 6),
            "corner_target_rate": round(spatial["corner"] / (3 * len(samples)), 6),
            "unique_ordered_sequences": len(set(ordered_values)),
            "unique_plan_signatures": len(set(plan_values)),
            "unique_resulting_turn_states": len(set(resulting_values)),
            "top_ordered_sequence_rate": round(Counter(ordered_values).most_common(1)[0][1] / len(samples), 6),
            "top_plan_signature_rate": round(Counter(plan_values).most_common(1)[0][1] / len(samples), 6),
            "top_resulting_turn_state_rate": round(Counter(resulting_values).most_common(1)[0][1] / len(samples), 6),
            "plan_shannon_entropy": round(entropy(plan_values), 6),
            "effective_number_of_plans": round(math.exp(entropy(plan_values)), 6),
        })
        search_timings.append({
            "position_id": position, "requested_iteration_budget": budget,
            "effective_iteration_budget": budget, "repetitions": len(samples),
            "total_recorded_search_seconds": round(sum(runtime_seconds), 6),
            "mean_search_seconds_per_turn": round(mean(runtime_seconds), 6),
            "median_search_seconds_per_turn": round(median(runtime_seconds), 6),
            "minimum_search_seconds_per_turn": round(min(runtime_seconds), 6),
            "maximum_search_seconds_per_turn": round(max(runtime_seconds), 6),
        })
        for site in SITE_NAMES:
            site_rows.append({
                "position_id": position, "iteration_budget": budget, "site": site,
                "site_type": "supply" if site[0] == "S" else "objective",
                "target_count": targets[site],
                "target_rate_per_turn": round(targets[site] / len(samples), 6),
                "supply_source_count": sources[site],
                "supply_source_rate_per_turn": round(sources[site] / len(samples), 6),
            })
        secured = Counter(value for row in samples for value in split(row["secured_supply_transitions"]))
        unresolved = Counter(value for row in samples for value in split(row["unresolved_supply_transitions"]))
        for kind, values in (("secured", secured), ("unresolved", unresolved)):
            for transition, count in sorted(values.items()):
                transition_rows.append({
                    "position_id": position, "iteration_budget": budget,
                    "transition_type": kind, "transition": transition,
                    "count": count, "rate_per_turn": round(count / len(samples), 6),
                })

    comparisons, classifications, recommendations = compare_budgets(groups, config)
    RESULTS.mkdir(parents=True, exist_ok=True)
    write_csv(RESULTS / "ordered-sequence-frequencies.csv", ordered_frequencies)
    write_csv(RESULTS / "plan-signature-frequencies.csv", plan_frequencies)
    write_csv(RESULTS / "resulting-state-frequencies.csv", resulting_frequencies)
    write_csv(RESULTS / "site-statistics.csv", site_rows)
    write_csv(RESULTS / "turn-summary.csv", turn_summaries)
    write_csv(RESULTS / "search-timings.csv", search_timings)
    if transition_rows:
        write_csv(RESULTS / "supply-transitions.csv", transition_rows)
    if comparisons:
        write_csv(RESULTS / "budget-comparison.csv", comparisons)
    if classifications:
        write_csv(RESULTS / "convergence-classification.csv", classifications)
    if recommendations:
        write_csv(RESULTS / "recommend-300k.csv", recommendations)
    analysis = {
        "schema_version": 1,
        "plan_signature_version": signature_config["version"],
        "positions_analyzed": len({row["position_id"] for row in rows}),
        "position_budget_groups": len(groups),
        "raw_rows": len(rows),
        "validation": validation,
        "aggregate_outputs_regenerated_from_raw": True,
    }
    (RESULTS / "analysis.json").write_text(
        json.dumps(analysis, indent=2) + "\n", encoding="utf-8"
    )
    print(f"validated and analyzed {len(rows)} one-turn searches in {len(groups)} groups")


if __name__ == "__main__":
    main()
