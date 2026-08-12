#!/usr/bin/env python3
"""Regression tests for Issue #41 frozen progression definitions."""

from __future__ import annotations

import json
import unittest

import analyze_progression as analysis


class PersistenceTests(unittest.TestCase):
    def test_lead_tie_relead_separates_strict_and_nonlosing(self) -> None:
        signs = [1, 0, 1]
        self.assertEqual(analysis.strict_persistent_lead_turn(signs, 1), 3)
        self.assertEqual(analysis.nonlosing_persistence_turn(signs, 1), 1)
        self.assertIsNone(analysis.last_lead_change_turn(signs))

    def test_lead_opponent_lead_final_win(self) -> None:
        signs = [1, -1, 1]
        self.assertEqual(analysis.strict_persistent_lead_turn(signs, 1), 3)
        self.assertEqual(analysis.nonlosing_persistence_turn(signs, 1), 3)
        self.assertEqual(analysis.last_lead_change_turn(signs), 3)
        self.assertEqual(analysis.lead_change_count(signs), 2)

    def test_lead_is_strictly_persistent_from_first_turn(self) -> None:
        signs = [1, 1, 1, 1]
        self.assertEqual(analysis.strict_persistent_lead_turn(signs, 1), 1)
        self.assertEqual(analysis.nonlosing_persistence_turn(signs, 1), 1)

    def test_late_reversal(self) -> None:
        signs = [-1, -1, -1, 1]
        self.assertEqual(analysis.strict_persistent_lead_turn(signs, 1), 4)
        self.assertEqual(analysis.nonlosing_persistence_turn(signs, 1), 4)
        self.assertEqual(analysis.last_lead_change_turn(signs), 4)

    def test_draw_has_no_winner_based_persistence(self) -> None:
        signs = [1, 0, -1, 0]
        self.assertIsNone(analysis.strict_persistent_lead_turn(signs, 0))
        self.assertIsNone(analysis.nonlosing_persistence_turn(signs, 0))
        self.assertEqual(analysis.last_lead_change_turn(signs), 3)
        self.assertEqual(analysis.equality_period_count(signs), 2)
        self.assertEqual(analysis.final_return_to_equality_turn(signs), 4)


class LexicographicLayerTests(unittest.TestCase):
    def row(self, secured: int, advantage: int, pieces: int) -> dict[str, object]:
        return {
            "secured_objective_difference": secured,
            "advantage_objective_difference": advantage,
            "objective_piece_difference": pieces,
        }

    def test_secured_lead_then_advantage_layer_reversal_after_secured_ties(self) -> None:
        secured_components = ["secured_objective_difference"]
        two_components = ["secured_objective_difference", "advantage_objective_difference"]
        first = self.row(1, -5, -20)
        second = self.row(0, -1, 20)
        self.assertEqual(analysis.layer_sign(first, secured_components), 1)
        self.assertEqual(analysis.layer_sign(first, two_components), 1)
        self.assertEqual(analysis.layer_sign(second, secured_components), 0)
        self.assertEqual(analysis.layer_sign(second, two_components), -1)

    def test_objective_pieces_break_tie_after_secured_and_advantage(self) -> None:
        row = self.row(0, 0, -2)
        self.assertEqual(analysis.layer_sign(row, [
            "secured_objective_difference", "advantage_objective_difference",
        ]), 0)
        self.assertEqual(analysis.layer_sign(row, [
            "secured_objective_difference", "advantage_objective_difference",
            "objective_piece_difference",
        ]), -1)


class ReversalDenominatorTests(unittest.TestCase):
    def test_tied_games_are_excluded_from_leader_denominator(self) -> None:
        config = {
            "comparison_layers": [{
                "id": "full_lexicographic",
                "components": ["secured_objective_difference", "advantage_objective_difference", "objective_piece_difference"],
            }]
        }
        base = {
            "experiment_id": "fixture", "turn_number": 1,
            "secured_objective_difference": 0, "advantage_objective_difference": 0,
        }
        rows = [
            {**base, "game_index": 1, "objective_piece_difference": 1, "winner": 1},
            {**base, "game_index": 2, "objective_piece_difference": 1, "winner": 2},
            {**base, "game_index": 3, "objective_piece_difference": -1, "winner": 0},
            {**base, "game_index": 4, "objective_piece_difference": 0, "winner": 1},
        ]
        result = analysis.build_reversal_rows(config, rows)[0]
        self.assertEqual(result["games_with_current_leader"], 3)
        self.assertEqual(result["current_leader_eventually_wins"], 1)
        self.assertEqual(result["current_leader_eventually_loses"], 1)
        self.assertEqual(result["eventual_draws_from_current_lead"], 1)
        self.assertEqual(result["games_tied_at_turn"], 1)
        self.assertAlmostEqual(result["reversal_rate_current_leader_eventually_loses"], 1 / 3, places=6)


class FrozenDefinitionTests(unittest.TestCase):
    def test_readme_config_and_analyzer_definitions_match(self) -> None:
        config = json.loads(analysis.CONFIG_PATH.read_text(encoding="utf-8"))
        analysis.validate_definitions(config)

    def test_primary_and_sensitivity_sets_are_separate(self) -> None:
        config = json.loads(analysis.CONFIG_PATH.read_text(encoding="utf-8"))
        important = config["important_supply_sites"]
        self.assertEqual(important["primary"]["sites"], ["S23", "S21", "S12", "S13", "S22"])
        self.assertFalse(important["primary"]["is_composite_value_ranking"])
        self.assertEqual(len(important["sensitivity"]), 4)

    def test_turning_window_is_frozen(self) -> None:
        config = json.loads(analysis.CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(config["turning_point_window"]["relative_turns"], [-2, -1, 0, 1, 2])


if __name__ == "__main__":
    unittest.main()
