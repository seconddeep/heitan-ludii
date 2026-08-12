#!/usr/bin/env python3
"""Regression tests for Issue #43 frozen reversal definitions."""

from __future__ import annotations

import copy
import json
import unittest

import analyze_reversals as analysis


class TimingTests(unittest.TestCase):
    def test_global_persistence_can_precede_checkpoint(self) -> None:
        signs = [-1, 1, 1, 1, 1]
        self.assertEqual(analysis.global_strict_persistence_turn(signs, 1), 2)
        self.assertIsNone(analysis.post_checkpoint_takeover_turn(signs, 1, 3, "lead_preserved"))

    def test_checkpoint_reversal_takeover_is_later(self) -> None:
        signs = [-1, -1, -1, 1, 1]
        self.assertEqual(analysis.post_checkpoint_takeover_turn(signs, 1, 2, "reversal"), 4)

    def test_temporary_takeover_then_tie_is_not_permanent(self) -> None:
        signs = [-1, -1, 1, 0, 1, 1]
        self.assertEqual(analysis.post_checkpoint_takeover_turn(signs, 1, 2, "reversal"), 5)

    def test_preserved_lead_has_no_post_checkpoint_takeover(self) -> None:
        self.assertIsNone(analysis.post_checkpoint_takeover_turn([1, 1, 1], 1, 1, "lead_preserved"))


class LayerAndPerspectiveTests(unittest.TestCase):
    def test_takeover_and_final_layers_can_differ(self) -> None:
        self.assertEqual(analysis.decisive_layer([0, 1, 4]), "advantage_objectives")
        self.assertEqual(analysis.decisive_layer([1, -3, -9]), "secured_objectives")

    def test_relative_transform_does_not_mutate_raw_values(self) -> None:
        raw = {"p1": 7, "p2": 4}
        original = copy.deepcopy(raw)
        result = {}
        analysis.add_relative_fields(result, "value", raw["p1"], raw["p2"], 2, 1)
        self.assertEqual(raw, original)
        self.assertEqual(result["value_p1"], 7)
        self.assertEqual(result["value_p2"], 4)
        self.assertEqual(result["value_checkpoint_leader_relative"], -3)
        self.assertEqual(result["value_eventual_winner_relative"], 3)


class SupportEdgeTests(unittest.TestCase):
    def test_pair_edges_are_not_deduplicated(self) -> None:
        objectives = {"O11": 0, "O12": 0, "O21": 0, "O22": 0}
        # S22 touches all four; S23 touches O12 and O22. Shared Objectives count twice.
        supplies = {"S22": 1, "S23": 1}
        self.assertEqual(analysis.usable_supply_support_edges(supplies, objectives, 1), 6)

    def test_one_supply_supports_multiple_live_objectives(self) -> None:
        supplies = {"S22": 1}
        objectives = {"O11": 0, "O12": 1, "O21": 2, "O22": 0}
        self.assertEqual(analysis.usable_supply_support_edges(supplies, objectives, 1), 4)

    def test_one_objective_accepts_multiple_supply_edges(self) -> None:
        supplies = {"S11": 1, "S12": 3, "S21": 2, "S22": 4}
        self.assertEqual(analysis.usable_supply_support_edges(supplies, {"O11": 0}, 1), 2)

    def test_secured_counts_opponent_and_resolved_do_not(self) -> None:
        supplies = {"S11": 3, "S12": 2}
        self.assertEqual(analysis.usable_supply_support_edges(supplies, {"O11": 0}, 1), 1)
        self.assertEqual(analysis.usable_supply_support_edges(supplies, {"O11": 3}, 1), 0)


def fixture_rows() -> dict[int, dict[str, object]]:
    rows = {}
    for turn in range(1, 17):
        mover = 1 if turn % 2 else 2
        row: dict[str, object] = {"mover": mover}
        for player in (1, 2):
            row[f"usable_supply_support_edges_p{player}"] = 10
            row[f"supply_source_uses_p{player}"] = 1 if mover == player else 0
            row[f"supply_placements_p{player}"] = 1 if mover == player else 0
            for stem in ("unsecured_control_losses", "important_control_losses", "important_control_gains", "new_secured_supply"):
                row[f"{stem}_p{player}"] = 0
        rows[turn] = row
    return rows


class SupplyMechanismTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.settings = json.loads(analysis.CONFIG_PATH.read_text(encoding="utf-8"))["supply_mechanisms"]

    def test_edge_delta_exactly_at_threshold(self) -> None:
        rows = fixture_rows()
        for turn in range(9, 13):
            rows[turn]["usable_supply_support_edges_p1"] = 9
        evidence = analysis.supply_mechanism_evidence(rows, 13, 1, 2, self.settings)
        self.assertEqual(evidence["leader_usable_support_edge_delta"], -1)
        self.assertEqual(evidence["indicator_degradation_support_edge_decline"], 1)

    def test_edge_delta_just_below_threshold(self) -> None:
        rows = fixture_rows()
        rows[9]["usable_supply_support_edges_p1"] = 9
        rows[10]["usable_supply_support_edges_p1"] = 9
        rows[11]["usable_supply_support_edges_p1"] = 9
        evidence = analysis.supply_mechanism_evidence(rows, 13, 1, 2, self.settings)
        self.assertEqual(evidence["leader_usable_support_edge_delta"], -0.75)
        self.assertEqual(evidence["indicator_degradation_support_edge_decline"], 0)

    def test_degradation_event_inside_and_outside_lookback(self) -> None:
        inside = fixture_rows()
        inside[9]["unsecured_control_losses_p1"] = 1
        result = analysis.supply_mechanism_evidence(inside, 13, 1, 2, self.settings)
        self.assertEqual(result["indicator_degradation_unsecured_control_loss"], 1)
        outside = fixture_rows()
        outside[8]["unsecured_control_losses_p1"] = 1
        result = analysis.supply_mechanism_evidence(outside, 13, 1, 2, self.settings)
        self.assertEqual(result["indicator_degradation_unsecured_control_loss"], 0)

    def test_reinvestment_event_inside_and_outside_lookback(self) -> None:
        inside = fixture_rows()
        inside[10]["new_secured_supply_p2"] = 1
        result = analysis.supply_mechanism_evidence(inside, 13, 1, 2, self.settings)
        self.assertEqual(result["indicator_reinvestment_new_secured_supply"], 1)
        outside = fixture_rows()
        outside[8]["new_secured_supply_p2"] = 1
        result = analysis.supply_mechanism_evidence(outside, 13, 1, 2, self.settings)
        self.assertEqual(result["indicator_reinvestment_new_secured_supply"], 0)


class MechanismTests(unittest.TestCase):
    def test_multiple_objective_flags_can_apply(self) -> None:
        rows = {
            1: {"secured_objective_difference": -1, "advantage_objective_difference": -1, "objective_piece_difference": -1},
            2: {"secured_objective_difference": 0, "advantage_objective_difference": -1, "objective_piece_difference": -1},
            3: {"secured_objective_difference": 0, "advantage_objective_difference": 1, "objective_piece_difference": 1},
        }
        result = analysis.classify_objective_mechanisms(rows, 1, 3, 1)
        self.assertEqual(result["mechanism_secured_objective_reversal"], 1)
        self.assertEqual(result["mechanism_advantage_conversion_reversal"], 1)

    def test_mixed_retains_multiple_substantive_flags(self) -> None:
        mechanisms = {
            "mechanism_secured_objective_reversal": 1,
            "mechanism_advantage_conversion_reversal": 0,
            "mechanism_objective_piece_tiebreak_reversal": 0,
            "mechanism_supply_degradation": 1,
            "mechanism_supply_reinvestment": 0,
        }
        self.assertEqual(analysis.mixed_mechanism_flag(mechanisms), 1)
        self.assertEqual(mechanisms["mechanism_secured_objective_reversal"], 1)
        self.assertEqual(mechanisms["mechanism_supply_degradation"], 1)


class FrozenDefinitionTests(unittest.TestCase):
    def test_config_and_readme_are_consistent(self) -> None:
        config = json.loads(analysis.CONFIG_PATH.read_text(encoding="utf-8"))
        analysis.validate_config(config)


if __name__ == "__main__":
    unittest.main()
