#!/usr/bin/env python3
"""Regression tests for Issue #44 frozen predictive evaluation."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

import analyze_prediction as analysis


class DefinitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(analysis.CONFIG_PATH.read_text(encoding="utf-8"))

    def test_config_and_readme_agree(self) -> None:
        analysis.validate_config(self.config)

    def test_fixed_l2_is_read_from_configuration(self) -> None:
        shared = self.config["logistic_regression"]["shared_l2_coefficient"]
        logistic = [model for model in self.config["models"] if model["model_type"] == "logistic"]
        self.assertTrue(logistic)
        self.assertTrue(all(model["l2_regularization_coefficient"] == shared for model in logistic))
        self.assertFalse(self.config["logistic_regression"]["coefficient_tuning"])

    def test_feature_lists_are_explicit_and_nonempty_for_logistic_models(self) -> None:
        for model in self.config["models"]:
            self.assertIsInstance(model["included_feature_columns"], list)
            if model["model_type"] == "logistic":
                self.assertTrue(model["included_feature_columns"])

    def test_primary_checkpoint_pooling_is_disabled(self) -> None:
        self.assertFalse(self.config["checkpoints"]["pool_primary_rows"])
        self.assertFalse(self.config["cross_validation"]["primary_rows_pooled"])


class PreprocessingLeakageTests(unittest.TestCase):
    def test_validation_values_do_not_change_training_scaling(self) -> None:
        training = [{"x": 1.0}, {"x": 2.0}, {"x": 3.0}]
        first = analysis.fit_preprocessor(training, ["x"])
        validation = [{"x": 4.0}]
        analysis.transform_rows(validation, ["x"], first)
        validation[0]["x"] = 4_000_000.0
        second = analysis.fit_preprocessor(training, ["x"])
        self.assertEqual(first, second)

    def test_zero_variance_uses_training_values_only(self) -> None:
        training = [{"x": 2.0}, {"x": 2.0}, {"x": 2.0}]
        validation = [{"x": -1000.0}, {"x": 1000.0}]
        preprocessing = analysis.fit_preprocessor(training, ["x"])
        transformed, active = analysis.transform_rows(validation, ["x"], preprocessing)
        self.assertFalse(preprocessing["x"]["active"])
        self.assertEqual(active, [])
        self.assertEqual(transformed, [[], []])


class MetricAndModelTests(unittest.TestCase):
    def test_metrics_on_perfect_ranking(self) -> None:
        labels = [0, 0, 1, 1]
        scores = [0.1, 0.2, 0.8, 0.9]
        self.assertEqual(analysis.roc_auc(labels, scores), 1.0)
        self.assertEqual(analysis.balanced_accuracy(labels, scores), 1.0)
        self.assertEqual(analysis.average_precision(labels, scores), 1.0)

    def test_logistic_orders_separable_fixture(self) -> None:
        matrix = [[-2.0], [-1.0], [1.0], [2.0]]
        labels = [0, 0, 1, 1]
        beta = analysis.fit_logistic(matrix, labels, 0.1, 100, 1e-10)
        scores = analysis.predict_logistic(matrix, beta)
        self.assertEqual(analysis.roc_auc(labels, scores), 1.0)


class FullPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(analysis.CONFIG_PATH.read_text(encoding="utf-8"))
        source = cls.config["source"]
        root = analysis.REPO_ROOT
        cls.turn_rows, _ = analysis.build_turn_records(
            analysis.read_csv(root / source["turn_progression"]),
            analysis.read_csv(root / source["placements"]),
            analysis.read_csv(root / source["supply_turn_states"]),
            analysis.read_csv(root / source["objective_turn_states"]),
            set(cls.config["important_supply_sites"]),
        )
        cls.checkpoint_rows, _ = analysis.build_checkpoint_rows(cls.turn_rows, cls.config)
        cls.eligible = [row for row in cls.checkpoint_rows if row["outcome_class"] in ("reversal", "lead_preserved")]
        cls.assignments = analysis.deterministic_fold_assignments(
            cls.checkpoint_rows,
            cls.config["cross_validation"]["folds"],
            cls.config["cross_validation"]["seed"],
        )

    def test_changing_post_checkpoint_turns_does_not_change_features(self) -> None:
        selected = next(
            row for row in self.checkpoint_rows
            if row["checkpoint_turn"] == 16 and row["checkpoint_leader"] != ""
        )
        key = selected["experiment_id"], int(selected["game_index"])
        rows = {
            int(row["turn_number"]): copy.deepcopy(row)
            for row in self.turn_rows
            if row["experiment_id"] == key[0] and int(row["game_index"]) == key[1]
        }
        before = analysis.build_checkpoint_feature(
            rows, 16, int(selected["checkpoint_leader"]), str(selected["outcome_class"]), self.config
        )
        for turn in range(17, 25):
            for field, value in list(rows[turn].items()):
                if isinstance(value, (int, float)):
                    rows[turn][field] = value + 99999
        after = analysis.build_checkpoint_feature(
            rows, 16, int(selected["checkpoint_leader"]), str(selected["outcome_class"]), self.config
        )
        self.assertEqual(before, after)

    def test_univariate_ranking_does_not_mutate_model_features(self) -> None:
        before = [copy.deepcopy(model["included_feature_columns"]) for model in self.config["models"]]
        analysis.univariate_summaries(self.checkpoint_rows, self.config["descriptive_features"])
        after = [model["included_feature_columns"] for model in self.config["models"]]
        self.assertEqual(before, after)

    def test_fold_assignments_are_deterministic(self) -> None:
        repeated = analysis.deterministic_fold_assignments(
            self.checkpoint_rows,
            self.config["cross_validation"]["folds"],
            self.config["cross_validation"]["seed"],
        )
        self.assertEqual(self.assignments, repeated)

    def test_all_models_share_the_same_checkpoint_folds(self) -> None:
        summaries, predictions, _ = analysis.evaluate_models(self.eligible, self.assignments, self.config)
        self.assertTrue(summaries)
        groups = {}
        for row in predictions:
            key = row["experiment_id"], row["checkpoint_turn"], row["model_name"]
            groups.setdefault(key, {})[row["game_index"]] = row["cv_fold"]
        for experiment, checkpoint in {(key[0], key[1]) for key in groups}:
            models = [mapping for key, mapping in groups.items() if key[:2] == (experiment, checkpoint)]
            self.assertTrue(all(mapping == models[0] for mapping in models[1:]))

    def test_turn_16_and_turn_20_are_evaluated_independently(self) -> None:
        summaries, predictions, _ = analysis.evaluate_models(self.eligible, self.assignments, self.config)
        for row in summaries:
            self.assertIn(row["checkpoint_turn"], (8, 12, 16, 20))
        for row in predictions:
            assignment = next(
                item for item in self.assignments
                if item["experiment_id"] == row["experiment_id"]
                and item["checkpoint_turn"] == row["checkpoint_turn"]
                and item["game_index"] == row["game_index"]
            )
            self.assertEqual(row["cv_fold"], assignment["cv_fold"])
        pairs = {(row["checkpoint_turn"], row["model_name"]) for row in summaries}
        self.assertIn((16, "combined"), pairs)
        self.assertIn((20, "combined"), pairs)

    def test_repeated_evaluation_produces_identical_predictions(self) -> None:
        _, first, _ = analysis.evaluate_models(self.eligible, self.assignments, self.config)
        _, second, _ = analysis.evaluate_models(self.eligible, self.assignments, self.config)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
