#!/usr/bin/env python3
"""Regression tests for Issue #82 confidence intervals and frozen classification."""

from __future__ import annotations

import unittest
from pathlib import Path
import tempfile
from unittest import mock

import protocol
import run_analysis


class IntervalTests(unittest.TestCase):
    def test_wilson_interval_contains_observed_rate(self) -> None:
        low, high = run_analysis.wilson(56, 100)
        self.assertLess(low, 0.56)
        self.assertGreater(high, 0.56)

    def test_newcombe_difference_contains_point_difference(self) -> None:
        low, high = run_analysis.newcombe_difference(60, 100, 50, 100)
        self.assertLess(low, 0.10)
        self.assertGreater(high, 0.10)

    def test_bootstrap_is_deterministic(self) -> None:
        values = [1, 0, 1, 1, 0]
        self.assertEqual(run_analysis.bootstrap_rate(values, 100, 82), run_analysis.bootstrap_rate(values, 100, 82))


class ClassificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = protocol.load_config()["stability_classification"]

    def test_stable_at_three_point_boundary(self) -> None:
        label, _ = run_analysis.classify_stability([0.50, 0.53, 0.50], [100, 100, 100], self.policy)
        self.assertEqual(label, "stable / converged-looking")

    def test_non_monotonic_precedes_fallback(self) -> None:
        label, _ = run_analysis.classify_stability([0.50, 0.56, 0.51], [100, 100, 100], self.policy)
        self.assertEqual(label, "non-monotonic")

    def test_directionally_stabilizing(self) -> None:
        label, _ = run_analysis.classify_stability([0.40, 0.50, 0.56], [100, 100, 100], self.policy)
        self.assertEqual(label, "directionally stabilizing")

    def test_small_sample_is_unresolved(self) -> None:
        label, evidence = run_analysis.classify_stability([0.40, 0.50, 0.56], [100, 24, 100], self.policy)
        self.assertEqual(label, "unresolved")
        self.assertIn("insufficient", evidence["reason"])


class OutputTests(unittest.TestCase):
    def test_primary_balance_outputs_are_generated_without_optional_budget(self) -> None:
        config = protocol.load_config()
        config["analysis"]["bootstrap_samples"] = 20
        tasks = [
            protocol.Task(f"t{budget}", "v", "production", f"e{budget}", budget, 1, budget)
            for budget in config["primary_budgets"]
        ]
        manifest = {"tasks": {task.task_id: {"state": "completed"} for task in tasks}}
        rows = [
            {"iteration_limit": str(10000), "winner": "1"},
            {"iteration_limit": str(30000), "winner": "0"},
            {"iteration_limit": str(100000), "winner": "2"},
        ]
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(run_analysis, "FINAL", Path(directory)):
            analysis = run_analysis.build_outputs(config, rows, tasks, manifest)
            self.assertEqual(len(analysis["balance"]), 3)
            self.assertEqual(analysis["classification"]["classification"], "unresolved")
            self.assertTrue((Path(directory) / "balance-by-depth.csv").is_file())
            self.assertTrue((Path(directory) / "failures.csv").is_file())


if __name__ == "__main__":
    unittest.main()
