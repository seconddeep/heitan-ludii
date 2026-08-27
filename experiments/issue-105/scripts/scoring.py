#!/usr/bin/env python3
"""Pure terminal-board scoring reconstruction for Issue #105."""

from __future__ import annotations


VALID_STATES = {0, 1, 2, 3, 4}


def parse_final_board(value: str) -> list[dict[str, int | str]]:
    sites: list[dict[str, int | str]] = []
    seen: set[str] = set()
    for encoded in value.split("|"):
        parts = encoded.split(":")
        if len(parts) != 4:
            raise ValueError(f"invalid final_board site: {encoded!r}")
        name, state_text, p1_text, p2_text = parts
        if name in seen:
            raise ValueError(f"duplicate final_board site: {name}")
        seen.add(name)
        state, p1, p2 = int(state_text), int(p1_text), int(p2_text)
        if state not in VALID_STATES or p1 < 0 or p2 < 0:
            raise ValueError(f"invalid final_board values: {encoded!r}")
        sites.append({"name": name, "state": state, "p1": p1, "p2": p2})
    if not sites:
        raise ValueError("final_board is empty")
    return sites


def winner_and_layer(secured: tuple[int, int], advantage: tuple[int, int], pieces: tuple[int, int]) -> tuple[int, str]:
    for values, layer in (
        (secured, "secured_objectives"),
        (advantage, "advantage_objectives"),
        (pieces, "objective_pieces"),
    ):
        if values[0] != values[1]:
            return (1 if values[0] > values[1] else 2), layer
    return 0, "draw"


def audit_terminal_board(value: str) -> dict[str, int | str | bool]:
    objectives = [site for site in parse_final_board(value) if str(site["name"]).startswith("O")]
    if not objectives:
        raise ValueError("final_board contains no Objectives")

    secured = (
        sum(int(site["state"]) == 3 for site in objectives),
        sum(int(site["state"]) == 4 for site in objectives),
    )
    advantage = (
        sum(int(site["state"]) == 1 for site in objectives),
        sum(int(site["state"]) == 2 for site in objectives),
    )
    previous = (
        sum(int(site["p1"]) for site in objectives),
        sum(int(site["p2"]) for site in objectives),
    )
    corrected = (
        sum(int(site["p1"]) for site in objectives if int(site["state"]) == 1),
        sum(int(site["p2"]) for site in objectives if int(site["state"]) == 2),
    )

    categories: dict[str, tuple[int, int]] = {
        "own_secured": (
            sum(int(site["p1"]) for site in objectives if int(site["state"]) == 3),
            sum(int(site["p2"]) for site in objectives if int(site["state"]) == 4),
        ),
        "opponent_secured": (
            sum(int(site["p1"]) for site in objectives if int(site["state"]) == 4),
            sum(int(site["p2"]) for site in objectives if int(site["state"]) == 3),
        ),
        "opponent_advantage": (
            sum(int(site["p1"]) for site in objectives if int(site["state"]) == 2),
            sum(int(site["p2"]) for site in objectives if int(site["state"]) == 1),
        ),
        "neutral": (
            sum(int(site["p1"]) for site in objectives if int(site["state"]) == 0),
            sum(int(site["p2"]) for site in objectives if int(site["state"]) == 0),
        ),
    }
    for player in (0, 1):
        excluded = sum(values[player] for values in categories.values())
        if previous[player] != corrected[player] + excluded:
            raise ValueError("Objective-piece partition identity failed")
        if categories["own_secured"][player] != 3 * secured[player]:
            raise ValueError("own-Secured contribution is not exactly three per Secured Objective")

    old_winner, old_layer = winner_and_layer(secured, advantage, previous)
    corrected_winner, corrected_layer = winner_and_layer(secured, advantage, corrected)
    result: dict[str, int | str | bool] = {
        "objective_sites": len(objectives),
        "p1_secured_objectives": secured[0],
        "p2_secured_objectives": secured[1],
        "p1_advantage_objectives": advantage[0],
        "p2_advantage_objectives": advantage[1],
        "previous_p1_objective_pieces": previous[0],
        "previous_p2_objective_pieces": previous[1],
        "corrected_p1_objective_pieces": corrected[0],
        "corrected_p2_objective_pieces": corrected[1],
        "previous_objective_piece_margin": previous[0] - previous[1],
        "corrected_objective_piece_margin": corrected[0] - corrected[1],
        "old_reconstructed_winner": old_winner,
        "old_deciding_layer": old_layer,
        "corrected_winner": corrected_winner,
        "corrected_deciding_layer": corrected_layer,
        "reaches_advantage_comparison": secured[0] == secured[1],
        "reaches_objective_piece_tiebreak": secured[0] == secured[1] and advantage[0] == advantage[1],
    }
    for name, values in categories.items():
        result[f"p1_excluded_{name}"] = values[0]
        result[f"p2_excluded_{name}"] = values[1]
    return result
