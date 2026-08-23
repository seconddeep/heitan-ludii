#!/usr/bin/env python3
"""Regression tests for the frozen Issue #83 analysis policy."""

from __future__ import annotations

import math
import unittest
from collections import Counter

import common
import run_analysis


class ClassificationTests(unittest.TestCase):
    def test_invalid_has_highest_priority(self) -> None:
        self.assertEqual(run_analysis.classify(None, 0.05)["classification_internal"], "unresolved-invalid")

    def test_non_monotonic_precedes_consistent(self) -> None:
        result = run_analysis.classify([0.08, -0.07, 0.09], 0.05)
        self.assertEqual(result["classification_internal"], "non-monotonic")
        self.assertEqual(result["rule_number"], 2)

    def test_consistent_positive_requires_two_budgets(self) -> None:
        result = run_analysis.classify([0.06, 0.05, 0.08], 0.05)
        self.assertEqual(result["classification_internal"], "consistent")
        self.assertIn("4x4", result["subclassification"])

    def test_margin_is_inclusive(self) -> None:
        result = run_analysis.classify([-0.05, 0.0, 0.05], 0.05)
        self.assertEqual(result["classification_internal"], "consistent")
        self.assertIn("similar", result["subclassification"])

    def test_single_material_budget_is_search_dependent(self) -> None:
        result = run_analysis.classify([0.06, 0.04, 0.01], 0.05)
        self.assertEqual(result["classification_internal"], "search-dependent")


class BootstrapTests(unittest.TestCase):
    def test_difference_is_deterministic_and_directional(self) -> None:
        left, right = [1, 1, 1, 0], [0, 0, 0, 1]
        first = run_analysis.bootstrap_difference(left, right, 100, 83)
        second = run_analysis.bootstrap_difference(left, right, 100, 83)
        self.assertEqual(first, second)
        self.assertGreater(sum(first), 0)

    def test_did_resamples_four_conditions_directly(self) -> None:
        interval = run_analysis.bootstrap_did(
            [0, 0, 0], [1, 1, 1], [0, 0, 0], [0, 0, 0], 50, 83,
        )
        self.assertEqual(interval, (1.0, 1.0))


class CheckpointTests(unittest.TestCase):
    def test_progress_checkpoints(self) -> None:
        self.assertEqual(math.ceil(18 * 0.75), 14)
        self.assertEqual(math.ceil(18 * 0.90), 17)
        self.assertEqual(math.ceil(24 * 0.75), 18)
        self.assertEqual(math.ceil(24 * 0.90), 22)


class FrozenSourceIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not common.SOURCE_LOCK.is_file():
            raise unittest.SkipTest("source lock has not been generated")
        cls.config = common.load_json(common.CONFIG_PATH)
        cls.source = common.load_json(common.SOURCE_LOCK)
        run_analysis.verify_locks(cls.config, cls.source)
        cls.games = run_analysis.load_games(cls.source)

    def test_source_counts_and_original_winners_reproduce(self) -> None:
        counts = Counter((row["board"], row["budget"], row["winner"]) for row in self.games)
        expected = {
            ("3x3", 10000): (71, 26, 3), ("3x3", 30000): (70, 28, 2),
            ("3x3", 100000): (43, 48, 9), ("4x4", 10000): (49, 41, 10),
            ("4x4", 30000): (56, 38, 6), ("4x4", 100000): (58, 35, 4),
        }
        for condition, winners in expected.items():
            self.assertEqual(tuple(counts[(*condition, winner)] for winner in (1, 2, 0)), winners)

    def test_failed_4x4_100k_identities_remain_excluded(self) -> None:
        actual = {row["game_index"] for row in self.games if row["board"] == "4x4" and row["budget"] == 100000}
        self.assertEqual(len(actual), 97)
        self.assertTrue({61, 78, 93}.isdisjoint(actual))

    def test_every_deciding_layer_is_normalized(self) -> None:
        allowed = {"secured_objectives", "advantage_objectives", "objective_pieces", "draw"}
        self.assertEqual({row["deciding_layer"] for row in self.games} - allowed, set())


if __name__ == "__main__":
    unittest.main()
