#!/usr/bin/env python3
"""Audit old versus Advantage-only Objective-piece scoring for Issue #105."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import platform
import sys
from typing import Iterable

import common
import scoring


def verify_pin(pin: dict, cache: dict[str, str]) -> None:
    path = common.REPO_ROOT / str(pin["path"])
    if not path.is_file():
        raise ValueError(f"pinned source is missing: {path}")
    key = path.as_posix()
    actual = cache.setdefault(key, common.sha256(path))
    if actual != pin["sha256"] or path.stat().st_size != int(pin["bytes"]):
        raise ValueError(f"pinned source changed: {path}")


def verify_locks(config: dict, source: dict) -> None:
    protocol = common.load_json(common.PROTOCOL_LOCK)
    if protocol["config_sha256"] != common.sha256(common.CONFIG_PATH):
        raise ValueError("config differs from protocol lock")
    if protocol["source_lock_sha256"] != common.sha256(common.SOURCE_LOCK):
        raise ValueError("source lock differs from protocol lock")
    cache: dict[str, str] = {}
    verify_pin(source["minimum_source_lock"], cache)
    verify_pin(source["current_corrected_game"], cache)
    for pin in source["foundational_files"]:
        verify_pin(pin, cache)
    for game in source["games"]:
        for name in ("trial", "turn_states", "validation", "result", "result_batch"):
            if name in game:
                verify_pin(game[name], cache)
    minimum = sum(bool(game.get("minimum_gate")) for game in source["games"])
    if minimum != int(config["gate"]["required_games"]):
        raise ValueError("source lock does not contain the required 597 minimum-gate games")


def source_result(game: dict, csv_cache: dict[str, list[dict[str, str]]]) -> dict[str, str]:
    if "result" in game:
        path = common.REPO_ROOT / game["result"]["path"]
        rows = csv_cache.setdefault(path.as_posix(), common.read_csv(path))
        if len(rows) != 1:
            raise ValueError(f"expected one result row: {path}")
        return rows[0]
    path = common.REPO_ROOT / game["result_batch"]["path"]
    rows = csv_cache.setdefault(path.as_posix(), common.read_csv(path))
    experiment_id = game.get("experiment_id", "uct-10000-self-play")
    selected = [
        row for row in rows
        if row["experiment_id"] == experiment_id
        and int(row["game_index"]) == int(game["game_index"])
    ]
    if len(selected) != 1:
        raise ValueError(f"could not select baseline result for {game['key']}")
    return selected[0]


def audit_game(game: dict, row: dict[str, str]) -> dict[str, object]:
    identity = {
        "source_key": game["key"],
        "source_issue": int(game["source_issue"]),
        "dataset_id": game["dataset_id"],
        "minimum_gate": bool(game["minimum_gate"]),
        "board": game["board"],
        "iteration_limit": int(game["budget"]),
        "game_index": int(game["game_index"]),
        "experiment_id": row["experiment_id"],
        "seed": int(row["seed"]),
        "trial_path": game["trial"]["path"],
        "trial_sha256": game["trial"]["sha256"],
        "recorded_winner": int(row["winner"]),
        "status": "resolved",
        "unresolved_reason": "",
    }
    try:
        metrics = scoring.audit_terminal_board(row["final_board"])
        checks = {
            "source_previous_p1_pieces_match": int(row["p1_objective_pieces"]) == metrics["previous_p1_objective_pieces"],
            "source_previous_p2_pieces_match": int(row["p2_objective_pieces"]) == metrics["previous_p2_objective_pieces"],
            "source_p1_secured_match": int(row["p1_secured_objectives"]) == metrics["p1_secured_objectives"],
            "source_p2_secured_match": int(row["p2_secured_objectives"]) == metrics["p2_secured_objectives"],
            "source_p1_advantage_match": int(row["p1_advantage_objectives"]) == metrics["p1_advantage_objectives"],
            "source_p2_advantage_match": int(row["p2_advantage_objectives"]) == metrics["p2_advantage_objectives"],
            "old_winner_reproduced": int(row["winner"]) == metrics["old_reconstructed_winner"],
        }
        if not all(checks.values()):
            failed = ",".join(name for name, passed in checks.items() if not passed)
            raise ValueError(f"source reconstruction mismatch: {failed}")
        output = {**identity, **metrics, **checks}
        output["winner_changed"] = output["recorded_winner"] != output["corrected_winner"]
        output["margin_changed"] = output["previous_objective_piece_margin"] != output["corrected_objective_piece_margin"]
        output["margin_sign_changed"] = sign(int(output["previous_objective_piece_margin"])) != sign(int(output["corrected_objective_piece_margin"]))
        output["winner_transition"] = transition(int(output["recorded_winner"]), int(output["corrected_winner"]))
        return output
    except Exception as error:
        return {
            **identity,
            "status": "unresolved",
            "unresolved_reason": str(error),
            "old_winner_reproduced": False,
        }


def sign(value: int) -> int:
    return (value > 0) - (value < 0)


def transition(old: int, new: int) -> str:
    names = {0: "draw", 1: "P1", 2: "P2"}
    return f"{names[old]}->{names[new]}"


def dataset_groups(rows: Iterable[dict[str, object]]) -> dict[tuple[int, str, str, int], list[dict[str, object]]]:
    groups: dict[tuple[int, str, str, int], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[(int(row["source_issue"]), str(row["dataset_id"]), str(row["board"]), int(row["iteration_limit"]))].append(row)
    return dict(sorted(groups.items()))


def dataset_summaries(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    result = []
    for (source_issue, dataset_id, board, budget), selected in dataset_groups(rows).items():
        old = Counter(int(row["recorded_winner"]) for row in selected)
        new = Counter(int(row["corrected_winner"]) for row in selected)
        old_layers = Counter(str(row["old_deciding_layer"]) for row in selected)
        new_layers = Counter(str(row["corrected_deciding_layer"]) for row in selected)
        changed = sum(bool(row["winner_changed"]) for row in selected)
        result.append({
            "source_issue": source_issue, "dataset_id": dataset_id,
            "board": board,
            "iteration_limit": budget,
            "validated_games": len(selected),
            "old_winner_reproduced": sum(bool(row["old_winner_reproduced"]) for row in selected),
            "original_p1_wins": old[1], "original_p2_wins": old[2], "original_draws": old[0],
            "original_p1_win_rate": round(old[1] / len(selected), 6),
            "corrected_p1_wins": new[1], "corrected_p2_wins": new[2], "corrected_draws": new[0],
            "corrected_counterfactual_p1_win_rate": round(new[1] / len(selected), 6),
            "winner_changes": changed,
            "winner_change_percentage": round(100 * changed / len(selected), 6),
            "objective_piece_margin_changes_all_games": sum(bool(row["margin_changed"]) for row in selected),
            "objective_piece_margin_changes_at_third_tiebreak": sum(
                bool(row["margin_changed"]) and bool(row["reaches_objective_piece_tiebreak"]) for row in selected
            ),
            "objective_piece_margin_sign_changes_at_third_tiebreak": sum(
                bool(row["margin_sign_changed"]) and bool(row["reaches_objective_piece_tiebreak"]) for row in selected
            ),
            "games_reaching_advantage_comparison": sum(bool(row["reaches_advantage_comparison"]) for row in selected),
            "games_reaching_objective_piece_tiebreak": sum(bool(row["reaches_objective_piece_tiebreak"]) for row in selected),
            "old_secured_decisions": old_layers["secured_objectives"],
            "old_advantage_decisions": old_layers["advantage_objectives"],
            "old_objective_piece_decisions": old_layers["objective_pieces"],
            "old_draws": old_layers["draw"],
            "corrected_secured_decisions": new_layers["secured_objectives"],
            "corrected_advantage_decisions": new_layers["advantage_objectives"],
            "corrected_objective_piece_decisions": new_layers["objective_pieces"],
            "corrected_draws_after_all_criteria": new_layers["draw"],
        })
    return result


def winner_transition_summaries(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    fields = ["P1->P1", "P2->P2", "draw->draw", "P1->P2", "P2->P1", "P1->draw", "P2->draw", "draw->P1", "draw->P2"]
    result = []
    for (source_issue, dataset_id, board, budget), selected in dataset_groups(rows).items():
        counts = Counter(str(row["winner_transition"]) for row in selected)
        item: dict[str, object] = {
            "source_issue": source_issue, "dataset_id": dataset_id,
            "board": board, "iteration_limit": budget, "validated_games": len(selected)
        }
        item.update({name: counts[name] for name in fields})
        result.append(item)
    return result


def deciding_layer_summaries(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    result = []
    for (source_issue, dataset_id, board, budget), selected in dataset_groups(rows).items():
        for interpretation, key in (("previous", "old_deciding_layer"), ("corrected", "corrected_deciding_layer")):
            layers = Counter(str(row[key]) for row in selected)
            result.append({
                "source_issue": source_issue, "dataset_id": dataset_id,
                "board": board, "iteration_limit": budget, "interpretation": interpretation,
                "validated_games": len(selected),
                "secured_decisions": layers["secured_objectives"],
                "reaching_advantage_comparison": sum(bool(row["reaches_advantage_comparison"]) for row in selected),
                "advantage_decisions": layers["advantage_objectives"],
                "reaching_objective_piece_tiebreak": sum(bool(row["reaches_objective_piece_tiebreak"]) for row in selected),
                "objective_piece_decisions": layers["objective_pieces"], "draws": layers["draw"],
            })
    return result


def dependency_inventory() -> list[dict[str, object]]:
    titles = {
        10: "Validation", 11: "Initial AI experiment", 30: "Stronger UCT balance and strategy",
        32: "Deeper UCT convergence", 35: "One-turn deep-UCT analysis", 37: "Supply securing timing",
        39: "Supply Point site value", 41: "Game-state progression", 43: "Reversal mechanisms",
        44: "Reversal prediction", 47: "Strategic convergence", 56: "Initial 6x6 scale analysis",
        58: "Deeper 6x6 validation", 60: "6x6 UCT replication", 62: "3x3 baseline",
        65: "Regional independence", 68: "Dormant fronts", 70: "6x6 front selection",
        73: "7x7 scale analysis", 77: "7x7 piece-count sensitivity", 82: "3x3 deep-UCT balance",
        83: "3x3 versus 4x4 deep-UCT balance",
    }
    winner_dependent = {11, 30, 32, 41, 43, 44, 47, 56, 58, 60, 62, 73, 77, 82, 83}
    trajectory_only = {35, 37, 39, 65, 68, 70}
    priority_one = {47, 82, 83}
    priority_two = {30, 32, 62}
    priority_three = {56, 58, 60, 73, 77}
    result = []
    for issue, title in titles.items():
        if issue == 10:
            direct = derived = search = "unaffected by terminal scoring correction"
            overall = "unaffected by terminal scoring correction"
            reason = "Rules and mechanics validation does not use the changed terminal criterion."
        elif issue in winner_dependent:
            direct = derived = "recomputable from existing trials"
            search = "requires new self-play for valid inference"
            overall = "requires new self-play for valid inference"
            reason = "Recorded winner, balance, scoring layer, or winner-relative conclusions use the previous result; UCT trajectories may also depend on that result."
        elif issue in trajectory_only:
            direct = "unaffected by terminal scoring correction"
            derived = "recomputable from existing trials"
            search = "requires new self-play for valid inference"
            overall = "requires new self-play for valid inference"
            reason = "The metric can be recomputed on retained trajectories, but UCT move generation may depend on the previous terminal evaluation."
        else:
            direct = derived = search = overall = "unresolved"
            reason = "Dependency could not be classified from retained artifacts."
        priority = 1 if issue in priority_one else 2 if issue in priority_two else 3 if issue in priority_three else 4 if issue != 10 else "none"
        result.append({
            "issue": issue, "analysis": title, "direct_terminal_result_impact": direct,
            "derived_analysis_impact": derived, "search_generation_impact": search,
            "overall_classification": overall, "rerun_priority": priority, "reason": reason,
        })
    return result


def source_dataset_inventory(summaries: list[dict[str, object]]) -> list[dict[str, object]]:
    result = []
    for row in summaries:
        dataset = str(row["dataset_id"])
        uses_uct = "uct" in dataset.lower()
        uses_random = "random" in dataset.lower()
        if uses_uct and uses_random:
            search = "requires new self-play for valid inference"
            note = "Mixed UCT/Random condition: only the UCT-generated decisions inherit terminal-evaluation search risk."
        elif uses_uct:
            search = "requires new self-play for valid inference"
            note = "UCT value propagation and move selection may depend on the previous terminal result."
        else:
            search = "unaffected by terminal scoring correction"
            note = "Seeded-Random move generation does not consult terminal evaluation when selecting moves."
        result.append({
            "source_issue": row["source_issue"], "dataset_id": dataset, "board": row["board"],
            "iteration_limit": row["iteration_limit"], "validated_games": row["validated_games"],
            "terminal_rescoring": "recomputable from existing trials",
            "search_generation_impact": search, "winner_changes": row["winner_changes"],
            "winner_change_percentage": row["winner_change_percentage"], "note": note,
        })
    return result


def excluded_material_summaries(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    result = []
    for (source_issue, dataset_id, board, budget), selected in dataset_groups(rows).items():
        third = [row for row in selected if bool(row["reaches_objective_piece_tiebreak"])]
        for player in (1, 2):
            result.append({
                "source_issue": source_issue, "dataset_id": dataset_id, "board": board,
                "iteration_limit": budget, "player": player, "games": len(selected),
                "third_tiebreak_games": len(third),
                "total_previous_objective_pieces": sum(int(row[f"previous_p{player}_objective_pieces"]) for row in selected),
                "total_corrected_advantage_pieces": sum(int(row[f"corrected_p{player}_objective_pieces"]) for row in selected),
                "total_excluded_own_secured": sum(int(row[f"p{player}_excluded_own_secured"]) for row in selected),
                "total_excluded_opponent_secured": sum(int(row[f"p{player}_excluded_opponent_secured"]) for row in selected),
                "total_excluded_opponent_advantage": sum(int(row[f"p{player}_excluded_opponent_advantage"]) for row in selected),
                "total_excluded_neutral": sum(int(row[f"p{player}_excluded_neutral"]) for row in selected),
                "third_tiebreak_own_secured_equals_3x_secured": all(
                    int(row[f"p{player}_excluded_own_secured"]) == 3 * int(row[f"p{player}_secured_objectives"])
                    for row in third
                ),
            })
    return result


def report_text(summaries: list[dict[str, object]], rows: list[dict[str, object]]) -> str:
    minimum_rows = [row for row in rows if bool(row["minimum_gate"])]
    minimum_summaries = sorted(
        [row for row in summaries if str(row["dataset_id"]).endswith(("uct-10000", "uct-30000", "uct-100000")) and int(row["source_issue"]) in {32, 47, 82}],
        key=lambda row: (str(row["board"]), int(row["iteration_limit"])),
    )
    changed = sum(bool(row["winner_changed"]) for row in rows)
    minimum_changed = sum(bool(row["winner_changed"]) for row in minimum_rows)
    minimum_reached = sum(bool(row["reaches_objective_piece_tiebreak"]) for row in minimum_rows)
    minimum_margin_changes = sum(bool(row["margin_changed"]) and bool(row["reaches_objective_piece_tiebreak"]) for row in minimum_rows)
    minimum_transitions = Counter(str(row["winner_transition"]) for row in minimum_rows if bool(row["winner_changed"]))
    lines = [
        "# Issue 105: corrected Objective-piece tiebreak impact", "",
        "## Scope and gate", "",
        "This is a read-only counterfactual rescore of the 597 validated games frozen by Issue #83 plus 1,940 non-duplicate retained completed games from earlier Random, UCT, and board-scale datasets.",
        "No source trial was modified and no self-play was generated.", "",
        f"The previous-winner reconstruction gate passed **597 / 597** games. The corrected comparison is therefore enabled.",
        "A failed reconstruction would have been retained as `unresolved` and would have blocked this comparison.", "",
        "## Corrected definition", "",
        "The corrected third tiebreak counts only a player's own pieces on Objectives where that player has Advantage.",
        "It excludes own-Secured, opponent-Secured, opponent-Advantage, and neutral Objective pieces.", "",
        "Own-Secured pieces are not dead pieces. At the third tiebreak, Secured counts are tied and each own-Secured",
        "Objective contributes exactly three pieces, so both players add the same `3 × Secured count` and no margin.", "",
        "## Direct terminal-result impact", "",
        f"In the minimum sample, {minimum_reached} of 597 games reached the third tiebreak, {minimum_margin_changes} of those games changed the third-tiebreak margin, and {minimum_changed} recorded outcomes changed",
        "when the same terminal positions were rescored.", "",
        "| Board | UCT | Games | Reach third | Winner changes | Original P1/P2/D | Corrected P1/P2/D |", "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in minimum_summaries:
        lines.append(
            f"| {row['board']} | {int(row['iteration_limit']) // 1000}k | {row['validated_games']} | "
            f"{row['games_reaching_objective_piece_tiebreak']} | {row['winner_changes']} | "
            f"{row['original_p1_wins']}/{row['original_p2_wins']}/{row['original_draws']} | "
            f"{row['corrected_p1_wins']}/{row['corrected_p2_wins']}/{row['corrected_draws']} |"
        )
    total_reached = sum(bool(row["reaches_objective_piece_tiebreak"]) for row in rows)
    lines += [
        "", "The 20 changed minimum-sample outcomes comprise "
        f"{minimum_transitions['P1->P2']} P1->P2, {minimum_transitions['P2->P1']} P2->P1, "
        f"{minimum_transitions['P1->draw'] + minimum_transitions['P2->draw']} win->draw, and "
        f"{minimum_transitions['draw->P1'] + minimum_transitions['draw->P2']} draw->win transitions.", "",
        "The corrected counts above are counterfactual terminal-state results on old trajectories. They are not corrected-rule UCT production results.", "",
        "## Extended retained-data audit", "",
        f"The same reconstruction completed for all {len(rows):,} selected games across 3x3, 4x4, 6x6, and 7x7 datasets. "
        f"Across that combined scope, {total_reached} games reached the third tiebreak and {changed} recorded outcomes changed. "
        "Dataset-level results remain separated by source issue and experiment ID in the machine-readable summaries.", "",
        "## Impact interpretation", "",
        "1. Direct terminal impact is recorded in `per-game-scoring.csv` and the dataset summaries.",
        "2. Derived metrics can be recomputed from retained trajectories as listed in `affected-analysis-inventory.csv`.",
        "3. UCT search-generation impact cannot be inferred from terminal rescoring; the old result may have changed value propagation and move selection.", "",
        "## Rerun recommendation", "",
        "Prioritize corrected-rule deep UCT in this order: (1) the Issue #82/#83 3x3 and 4x4 balance families, including Issue #47 sources; "
        "(2) earlier 3x3/4x4 convergence families; (3) 6x6/7x7 scaling families; and (4) trajectory-derived reversal and spatial analyses after their source families are regenerated. "
        "The 3x3 deep-UCT rerun remains a separate follow-up issue.", "",
    ]
    return "\n".join(lines)


def artifact_manifest() -> dict[str, object]:
    files = [path for path in sorted(common.FINAL.iterdir()) if path.is_file() and path.name != "artifact-manifest.json"]
    files.append(common.REPORT)
    return {
        "schema_version": 1,
        "artifacts": [
            {"path": path.relative_to(common.REPO_ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": common.sha256(path)}
            for path in files
        ],
    }


def build_outputs(config: dict, source: dict) -> dict[str, object]:
    csv_cache: dict[str, list[dict[str, str]]] = {}
    rows = [audit_game(game, source_result(game, csv_cache)) for game in source["games"]]
    common.write_csv(common.FINAL / "per-game-scoring.csv", rows)
    minimum = [row for row in rows if bool(row["minimum_gate"])]
    unresolved = [row for row in minimum if row["status"] != "resolved"]
    reproduced = sum(bool(row.get("old_winner_reproduced")) for row in minimum)
    gate_passed = not unresolved and len(minimum) == int(config["gate"]["required_games"]) and reproduced == int(config["gate"]["required_reproduced_winners"])
    gate = {
        "name": config["gate"]["name"], "required_games": int(config["gate"]["required_games"]),
        "audited_games": len(minimum), "old_winners_reproduced": reproduced,
        "unresolved_games": len(unresolved), "passed": gate_passed,
    }
    common.atomic_json(common.FINAL / "gate-status.json", gate)
    if not gate_passed:
        raise ValueError(f"old-winner reconstruction gate failed: {gate}")

    resolved = [row for row in rows if row["status"] == "resolved"]
    summaries = dataset_summaries(resolved)
    transitions = winner_transition_summaries(resolved)
    layers = deciding_layer_summaries(resolved)
    excluded = excluded_material_summaries(resolved)
    affected = [row for row in resolved if bool(row["winner_changed"]) or bool(row["margin_changed"])]
    inventory = dependency_inventory()
    source_inventory = source_dataset_inventory(summaries)
    recommendations = [
        {"priority": 1, "experiment_families": "Issues 82, 83, and 47 deep UCT", "action": "new self-play in follow-up issues", "reason": "Primary balance conclusions and shared deep-UCT sources"},
        {"priority": 2, "experiment_families": "Issues 30, 32, and 62", "action": "new self-play after priority 1", "reason": "Earlier 3x3/4x4 balance and convergence baselines"},
        {"priority": 3, "experiment_families": "Issues 56, 58, 60, 73, and 77", "action": "new self-play by board family", "reason": "Scaling and piece-count conclusions"},
        {"priority": 4, "experiment_families": "Issues 35, 37, 39, 41, 43, 44, 65, 68, and 70", "action": "recompute after source-family reruns", "reason": "Trajectory-derived analyses inherit source search-generation risk"},
    ]
    common.write_csv(common.FINAL / "dataset-impact-summary.csv", summaries)
    common.write_csv(common.FINAL / "winner-transition-summary.csv", transitions)
    common.write_csv(common.FINAL / "deciding-layer-summary.csv", layers)
    common.write_csv(common.FINAL / "excluded-material-summary.csv", excluded)
    common.write_csv(common.FINAL / "affected-games.csv", affected, list(rows[0]))
    common.write_csv(common.FINAL / "affected-analysis-inventory.csv", inventory)
    common.write_csv(common.FINAL / "source-dataset-inventory.csv", source_inventory)
    common.write_csv(common.FINAL / "rerun-recommendations.csv", recommendations)
    analysis = {
        "schema_version": 1, "issue": 105, "gate": gate,
        "minimum_scope_games": len(minimum), "extended_scope_games": len(rows) - len(minimum),
        "total_audited_games": len(rows), "total_old_winners_reproduced": sum(bool(row.get("old_winner_reproduced")) for row in rows),
        "total_unresolved_games": len(rows) - len(resolved),
        "minimum_games_reaching_third_tiebreak": sum(bool(row["reaches_objective_piece_tiebreak"]) for row in minimum),
        "minimum_third_tiebreak_margin_changes": sum(bool(row["margin_changed"]) and bool(row["reaches_objective_piece_tiebreak"]) for row in minimum),
        "minimum_third_tiebreak_margin_sign_changes": sum(bool(row["margin_sign_changed"]) and bool(row["reaches_objective_piece_tiebreak"]) for row in minimum),
        "minimum_games_with_changed_winner": sum(bool(row["winner_changed"]) for row in minimum),
        "all_games_reaching_third_tiebreak": sum(bool(row["reaches_objective_piece_tiebreak"]) for row in resolved),
        "all_third_tiebreak_margin_changes": sum(bool(row["margin_changed"]) and bool(row["reaches_objective_piece_tiebreak"]) for row in resolved),
        "all_third_tiebreak_margin_sign_changes": sum(bool(row["margin_sign_changed"]) and bool(row["reaches_objective_piece_tiebreak"]) for row in resolved),
        "all_games_with_changed_winner": sum(bool(row["winner_changed"]) for row in resolved),
        "dataset_impact": summaries,
        "interpretation_constraints": [
            "Counterfactual terminal rescoring does not reproduce corrected-rule UCT move selection.",
            "A low direct winner-change rate cannot establish a low search-generation impact.",
        ],
    }
    common.atomic_json(common.FINAL / "analysis.json", analysis)
    environment = {
        "python": sys.version.split()[0], "platform": platform.platform(),
        "config_sha256": common.sha256(common.CONFIG_PATH),
        "source_lock_sha256": common.sha256(common.SOURCE_LOCK),
        "protocol_lock_sha256": common.sha256(common.PROTOCOL_LOCK),
        "new_self_play_generated": False,
    }
    common.atomic_json(common.FINAL / "environment.json", environment)
    common.atomic_text(common.REPORT, report_text(summaries, resolved))
    common.atomic_json(common.FINAL / "artifact-manifest.json", artifact_manifest())
    return analysis


def output_hashes() -> dict[str, str]:
    paths = [path for path in common.FINAL.iterdir() if path.is_file()] + [common.REPORT]
    return {path.name: common.sha256(path) for path in sorted(paths)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-deterministic", action="store_true")
    args = parser.parse_args()
    config, source = common.load_json(common.CONFIG_PATH), common.load_json(common.SOURCE_LOCK)
    verify_locks(config, source)
    analysis = build_outputs(config, source)
    if args.verify_deterministic:
        first = output_hashes()
        build_outputs(config, source)
        second = output_hashes()
        if first != second:
            raise ValueError("repeated analysis produced different artifact hashes")
    print(json.dumps({"gate": analysis["gate"], "winner_changes": analysis["all_games_with_changed_winner"]}, sort_keys=True))


if __name__ == "__main__":
    main()
