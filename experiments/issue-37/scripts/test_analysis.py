#!/usr/bin/env python3
"""Regression tests for the frozen Issue #37 analysis definitions."""

from __future__ import annotations

import json
import unittest

import analyze_results


class SecurableOpportunityTests(unittest.TestCase):
    def row(self, state: int, own: int, opponent: int, legal: int) -> dict[str, str]:
        return {
            "mover": "1", "state_at_turn_start": str(state),
            "p1_pieces_at_turn_start": str(own),
            "p2_pieces_at_turn_start": str(opponent),
            "legal_max_additional_placements_this_turn": str(legal),
        }

    def test_capacity_not_piece_count_alone_determines_securable(self) -> None:
        possible = analyze_results.securable_values(self.row(1, 1, 0, 2), 3)
        blocked = analyze_results.securable_values(self.row(1, 1, 0, 1), 3)
        self.assertTrue(possible[0])
        self.assertFalse(blocked[0])
        self.assertEqual(possible[3], 2)

    def test_secured_point_is_not_securable(self) -> None:
        self.assertFalse(analyze_results.securable_values(self.row(3, 2, 1, 2), 3)[0])

    def test_zero_own_pieces_needs_more_than_current_legal_capacity(self) -> None:
        securable, own, opponent, needed = analyze_results.securable_values(
            self.row(0, 0, 2, 2), 3
        )
        self.assertFalse(securable)
        self.assertEqual((own, opponent, needed), (0, 2, 3))


class SpatialDefinitionTests(unittest.TestCase):
    def test_frozen_category_membership_and_sizes(self) -> None:
        categories = {
            site: analyze_results.spatial_category(site)
            for site in analyze_results.SUPPLY_POINTS
        }
        self.assertEqual(categories["S00"], "corner")
        self.assertEqual(categories["S02"], "edge")
        self.assertEqual(categories["S11"], "interior")
        self.assertEqual(categories["S22"], "interior")
        self.assertEqual(
            {category: list(categories.values()).count(category)
             for category in ("corner", "edge", "interior")},
            {"corner": 4, "edge": 12, "interior": 9},
        )

    def test_readme_config_and_analyzer_share_frozen_definitions(self) -> None:
        config = json.loads(analyze_results.CONFIG_PATH.read_text(encoding="utf-8"))
        analyze_results.validate_frozen_definitions(config)
        readme = (analyze_results.ISSUE_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Ludii `Context`", readme)
        self.assertIn("the four corner Supply Points", readme)
        self.assertIn("non-corner Supply Points on the outer boundary", readme)
        self.assertIn("the 3x3 non-edge interior Supply Points", readme)
        self.assertIn("central (interior 3x3)", readme)
        self.assertNotIn("own_count in (1, 2)", readme)


if __name__ == "__main__":
    unittest.main()
