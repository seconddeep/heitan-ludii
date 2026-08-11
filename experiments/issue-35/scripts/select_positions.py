#!/usr/bin/env python3
"""Mechanically select five early Heitan turn-boundary positions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


SCRIPT = Path(__file__).resolve()
ISSUE_ROOT = SCRIPT.parent.parent
REPO_ROOT = ISSUE_ROOT.parent.parent
CONFIG = ISSUE_ROOT / "config.json"
POSITIONS = ISSUE_ROOT / "positions.json"
SITE_NAMES = [f"S{r}{c}" for r in range(5) for c in range(5)] + [
    f"O{r}{c}" for r in range(4) for c in range(4)
]
NAME_TO_SITE = {name: index for index, name in enumerate(SITE_NAMES)}
MOVE_RE = re.compile(r"^Move=\[Move:mover=(\d+),")
ADD_RE = re.compile(r"\[Add:type=Vertex,to=(\d+),level=\d+,what=(\d+),state=(\d+)")
STATE_RE = re.compile(r"\[SetState:type=Vertex,to=(\d+),state=(\d+)\]")
OBJECTIVE_SUPPLY_RE = re.compile(r"^Move=\[Move:mover=\d+,from=(\d+)(?:,levelFrom=\d+)?,to=(\d+)")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def point_state(stack: list[dict[str, int]]) -> int:
    return stack[-1]["state"] if stack else 0


def counts(stack: list[dict[str, int]]) -> tuple[int, int]:
    return (
        sum(piece["owner"] == 1 for piece in stack),
        sum(piece["owner"] == 2 for piece in stack),
    )


def spatial(name: str) -> str:
    size = 5 if name[0] == "S" else 4
    row, column = int(name[1]), int(name[2])
    boundaries = int(row in (0, size - 1)) + int(column in (0, size - 1))
    return "corner" if boundaries == 2 else "edge" if boundaries == 1 else "central"


def adjacent_supply(objective: str) -> list[str]:
    row, column = int(objective[1]), int(objective[2])
    return [f"S{row}{column}", f"S{row}{column + 1}",
            f"S{row + 1}{column}", f"S{row + 1}{column + 1}"]


def parse_moves(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines()
            if MOVE_RE.match(line)]


def apply_move(board: list[list[dict[str, int]]], line: str) -> None:
    addition = ADD_RE.search(line)
    if addition is None:
        raise ValueError(f"missing Add action in {line}")
    site, owner, state = map(int, addition.groups())
    board[site].append({"owner": owner, "state": state})
    for match in STATE_RE.finditer(line):
        changed_site, changed_state = map(int, match.groups())
        if not board[changed_site]:
            raise ValueError(f"SetState on empty site {changed_site}")
        board[changed_site][-1]["state"] = changed_state


def board_payload(board: list[list[dict[str, int]]]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for site, name in enumerate(SITE_NAMES):
        p1, p2 = counts(board[site])
        result[name] = {
            "state": point_state(board[site]),
            "p1_pieces": p1,
            "p2_pieces": p2,
            "stack": [piece["owner"] for piece in board[site]],
        }
    return result


def features(board: list[list[dict[str, int]]], mover: int) -> dict[str, object]:
    states = {name: point_state(board[index]) for index, name in enumerate(SITE_NAMES)}
    piece_counts = {name: counts(board[index]) for index, name in enumerate(SITE_NAMES)}
    legal_supply: list[str] = []
    securable_supply: list[str] = []
    unresolved: list[str] = []
    for name in SITE_NAMES[:25]:
        state = states[name]
        p1, p2 = piece_counts[name]
        own = p1 if mover == 1 else p2
        if state < 3:
            unresolved.append(f"{name}:{state}:{p1}:{p2}")
            if own < 3:
                legal_supply.append(name)
                if own in (1, 2):
                    securable_supply.append(name)
    controlled = {
        name for name in SITE_NAMES[:25]
        if states[name] in (mover, mover + 2)
    }
    legal_objectives: list[str] = []
    for name in SITE_NAMES[25:]:
        own = piece_counts[name][mover - 1]
        if states[name] < 3 and own < 3 and controlled.intersection(adjacent_supply(name)):
            legal_objectives.append(name)
    legal_targets = legal_supply + legal_objectives
    spatial_counts = {category: sum(spatial(name) == category for name in legal_targets)
                      for category in ("central", "edge", "corner")}
    return {
        "p1_supply_pieces": sum(piece_counts[name][0] for name in SITE_NAMES[:25]),
        "p2_supply_pieces": sum(piece_counts[name][1] for name in SITE_NAMES[:25]),
        "p1_objective_pieces": sum(piece_counts[name][0] for name in SITE_NAMES[25:]),
        "p2_objective_pieces": sum(piece_counts[name][1] for name in SITE_NAMES[25:]),
        "unresolved_supply_points": unresolved,
        "securable_supply_points": securable_supply,
        "legal_supply_targets": legal_supply,
        "available_objectives": legal_objectives,
        "legal_target_spatial_counts": spatial_counts,
    }


def selection_score(candidate: dict[str, object], classification: str) -> tuple[int, ...]:
    values = candidate["features"]
    assert isinstance(values, dict)
    spatial_counts = values["legal_target_spatial_counts"]
    assert isinstance(spatial_counts, dict)
    objective_pieces = int(values["p1_objective_pieces"]) + int(values["p2_objective_pieces"])
    if classification == "supply-expansion":
        return (len(values["legal_supply_targets"]), len(values["available_objectives"]))
    if classification == "supply-securing-choice":
        return (len(values["securable_supply_points"]), len(values["unresolved_supply_points"]))
    if classification == "central-peripheral-competition":
        peripheral = int(spatial_counts["edge"]) + int(spatial_counts["corner"])
        return (min(int(spatial_counts["central"]), peripheral), int(spatial_counts["central"]), peripheral)
    if classification == "objective-supply-tradeoff":
        return (len(values["available_objectives"]), len(values["legal_supply_targets"]), objective_pieces)
    return (objective_pieces, len(values["available_objectives"]), len(values["securable_supply_points"]))


def main() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    source_dir = REPO_ROOT / config["source_trials"]
    trials = sorted(source_dir.glob("*.trl"))
    if not trials:
        raise ValueError(f"no source trials found in {source_dir}")

    by_completed_turn: dict[int, list[dict[str, object]]] = {turn: [] for turn in range(1, 6)}
    for path in trials:
        lines = parse_moves(path)
        if len(lines) < 18:
            raise ValueError(f"source trial is too short: {path}")
        board: list[list[dict[str, int]]] = [[] for _ in SITE_NAMES]
        for placement_index, line in enumerate(lines[:15], start=1):
            apply_move(board, line)
            if placement_index % 3:
                continue
            completed_turn = placement_index // 3
            last_mover = int(MOVE_RE.match(line).group(1))  # type: ignore[union-attr]
            mover = 2 if last_mover == 1 else 1
            prefix_text = "\n".join(lines[:placement_index]) + "\n"
            relative = path.relative_to(REPO_ROOT).as_posix()
            by_completed_turn[completed_turn].append({
                "source_trl_path": relative,
                "prefix_placement_count": placement_index,
                "heitan_turn_number": completed_turn + 1,
                "mover": mover,
                "complete_starting_board_state": board_payload(board),
                "source_trial_hash": sha256_bytes(path.read_bytes()),
                "prefix_hash": sha256_bytes(prefix_text.encode("utf-8")),
                "features": features(board, mover),
            })

    classifications = {
        1: "supply-expansion",
        2: "supply-securing-choice",
        3: "central-peripheral-competition",
        4: "objective-supply-tradeoff",
        5: "early-midgame-allocation",
    }
    selected: list[dict[str, object]] = []
    used_boards: set[str] = set()
    for completed_turn, classification in classifications.items():
        candidates = sorted(
            by_completed_turn[completed_turn],
            key=lambda item: (selection_score(item, classification), item["source_trl_path"]),
            reverse=True,
        )
        chosen = next(
            (item for item in candidates
             if sha256_bytes(json.dumps(item["complete_starting_board_state"], sort_keys=True).encode())
             not in used_boards),
            candidates[0],
        )
        board_hash = sha256_bytes(json.dumps(chosen["complete_starting_board_state"], sort_keys=True).encode())
        used_boards.add(board_hash)
        chosen = dict(chosen)
        chosen["position_id"] = f"turn-{completed_turn + 1}-{classification}"
        chosen["classification"] = classification
        chosen["selection_reason"] = (
            f"Deterministic maximum for {classification} among Issue #32 "
            f"10,000-iteration positions after completed turn {completed_turn}."
        )
        selected.append(chosen)

    output = {
        "schema_version": 1,
        "selection_method": "deterministic feature ranking over all Issue #32 10000-iteration trials",
        "source_trial_count": len(trials),
        "positions": selected,
    }
    POSITIONS.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"selected {len(selected)} positions from {len(trials)} source trials")


if __name__ == "__main__":
    main()
