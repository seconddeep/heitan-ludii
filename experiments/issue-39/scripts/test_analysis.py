#!/usr/bin/env python3
"""Regression tests for Issue #39 frozen analysis definitions."""

from __future__ import annotations

import json
import unittest

import analyze_site_value as analysis


class ControlSeparationTests(unittest.TestCase):
    def turn(self, state: int, player: int = 1) -> dict[str, object]:
        return analysis.control_flags(state, player)

    def test_unsecured_controlled_turn_is_counted(self) -> None:
        counts = analysis.count_control_turns([self.turn(1)])
        self.assertEqual(counts["unsecured_controlled_turns"], 1)
        self.assertEqual(counts["secured_turns"], 0)
        self.assertEqual(counts["controlled_or_secured_turns"], 1)

    def test_turns_after_securing_do_not_enter_unsecured_control(self) -> None:
        rows = [self.turn(1), self.turn(1), self.turn(3), self.turn(3)]
        counts = analysis.count_control_turns(rows)
        self.assertEqual(counts["unsecured_controlled_turns"], 2)
        self.assertEqual(counts["secured_turns"], 2)

    def test_combined_equals_unsecured_plus_secured(self) -> None:
        rows = [self.turn(state) for state in (0, 1, 2, 1, 3, 3)]
        counts = analysis.count_control_turns(rows)
        self.assertEqual(
            counts["controlled_or_secured_turns"],
            counts["unsecured_controlled_turns"] + counts["secured_turns"],
        )

    def test_phase_subset_preserves_control_identity(self) -> None:
        game = [self.turn(state) for state in (0, 1, 1, 3, 3, 3)]
        for phase_rows in (game[:2], game[2:4], game[4:]):
            counts = analysis.count_control_turns(phase_rows)
            self.assertEqual(
                counts["controlled_or_secured_turns"],
                counts["unsecured_controlled_turns"] + counts["secured_turns"],
            )


class FrozenDefinitionTests(unittest.TestCase):
    def test_readme_config_and_analyzer_definitions_match(self) -> None:
        config = json.loads(analysis.CONFIG_PATH.read_text(encoding="utf-8"))
        analysis.validate_definitions(config)

    def test_spatial_membership(self) -> None:
        self.assertEqual(analysis.spatial_category("S00"), "corner")
        self.assertEqual(analysis.spatial_category("S02"), "edge")
        self.assertEqual(analysis.spatial_category("S22"), "interior")
        counts = {
            category: sum(analysis.spatial_category(site) == category for site in analysis.SUPPLY_POINTS)
            for category in ("corner", "edge", "interior")
        }
        self.assertEqual(counts, {"corner": 4, "edge": 12, "interior": 9})

    def test_objective_coverage_adjacency_degree(self) -> None:
        self.assertEqual(len(analysis.adjacent_objectives("S00")), 1)
        self.assertEqual(len(analysis.adjacent_objectives("S02")), 2)
        self.assertEqual(len(analysis.adjacent_objectives("S22")), 4)

    def test_turn_phases_are_frozen(self) -> None:
        config = json.loads(analysis.CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual([analysis.phase(turn, config) for turn in (1, 8, 9, 16, 17, 24)], [
            "early", "early", "midgame", "midgame", "late", "late",
        ])


if __name__ == "__main__":
    unittest.main()
