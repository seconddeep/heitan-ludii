#!/usr/bin/env python3
"""Regression tests for the frozen plan_signature definition."""

from __future__ import annotations

import copy
import unittest

import analyze_results


class PlanSignatureTests(unittest.TestCase):
    def setUp(self) -> None:
        empty_board = "|".join(f"{site}:0:0:0" for site in analyze_results.SITE_NAMES)
        self.row = {
            "ordered_sequence": "S11;O11@S10;S12",
            "supply_placement_sites": "S11;S12",
            "objective_placement_sites": "O11",
            "supply_source_sites": "S10",
            "spatial_categories": "central;central;central",
            "secured_supply_transitions": "",
            "unresolved_supply_transitions": "S11:0:0:0>1:1:0;S12:0:0:0>1:1:0",
            "resulting_turn_state": empty_board,
        }

    def signature(self, row: dict[str, str]) -> str:
        return analyze_results.plan_signature(
            row, analyze_results.FROZEN_SIGNATURE_CONFIG
        )

    def test_placement_order_is_ignored(self) -> None:
        other = copy.deepcopy(self.row)
        other["ordered_sequence"] = "O11@S10;S12;S11"
        other["supply_placement_sites"] = "S12;S11"
        other["spatial_categories"] = "central;central;central"
        other["unresolved_supply_transitions"] = (
            "S12:0:0:0>1:1:0;S11:0:0:0>1:1:0"
        )
        self.assertNotEqual(self.row["ordered_sequence"], other["ordered_sequence"])
        self.assertEqual(self.signature(self.row), self.signature(other))

    def test_supply_source_difference_changes_plan(self) -> None:
        other = copy.deepcopy(self.row)
        other["supply_source_sites"] = "S01"
        self.assertNotEqual(self.signature(self.row), self.signature(other))

    def test_strategic_feature_difference_changes_plan(self) -> None:
        other = copy.deepcopy(self.row)
        other["objective_placement_sites"] = "O12"
        self.assertNotEqual(self.signature(self.row), self.signature(other))

    def test_resulting_board_difference_does_not_change_plan(self) -> None:
        other = copy.deepcopy(self.row)
        other["resulting_turn_state"] = other["resulting_turn_state"].replace(
            "S00:0:0:0", "S00:1:1:0", 1
        )
        self.assertNotEqual(
            self.row["resulting_turn_state"], other["resulting_turn_state"]
        )
        self.assertEqual(self.signature(self.row), self.signature(other))

    def test_configuration_is_frozen(self) -> None:
        changed = dict(analyze_results.FROZEN_SIGNATURE_CONFIG)
        changed["ignore_placement_order"] = False
        with self.assertRaises(ValueError):
            analyze_results.plan_signature(self.row, changed)


if __name__ == "__main__":
    unittest.main()
