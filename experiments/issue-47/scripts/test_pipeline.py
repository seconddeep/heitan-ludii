#!/usr/bin/env python3
"""Regression tests for Issue #47 aggregation and frozen classifications."""

from __future__ import annotations

import json
import csv
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import protocol
import run_analysis


class ConvergenceRuleTests(unittest.TestCase):
    def test_insufficient_evidence_has_first_precedence(self) -> None:
        label, _ = run_analysis.classify([0.1, 0.5, 0.1], [100, 100, 24])
        self.assertEqual(label, "insufficient evidence")

    def test_non_monotonic_rule_is_mechanical(self) -> None:
        label, evidence = run_analysis.classify([0.1, 0.2, 0.1], [100, 100, 100])
        self.assertEqual(label, "non-monotonic")
        self.assertAlmostEqual(evidence["delta_30k_100k"], -0.1)

    def test_stable_and_stabilizing_rules(self) -> None:
        self.assertEqual(run_analysis.classify([0.10, 0.12, 0.13], [100] * 3)[0], "stable / converged-looking")
        self.assertEqual(run_analysis.classify([0.10, 0.20, 0.25], [100] * 3)[0], "directionally stabilizing")


class PilotExclusionTests(unittest.TestCase):
    def test_staged_replay_path_is_normalized_to_immutable_source_trial(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            replay = Path(temporary) / "replay.csv"
            with replay.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["experiment_id", "game_index", "trial_file"])
                writer.writeheader()
                writer.writerow({"experiment_id": "exp", "game_index": "1", "trial_file": "validation-copy.trl"})
            run_analysis.normalize_replay_trial_paths(replay, [{
                "experiment_id": "exp", "game_index": "1", "trial_file": "immutable-source.trl",
            }])
            self.assertEqual(run_analysis.read_csv(replay)[0]["trial_file"], "immutable-source.trl")

    def test_production_reader_rejects_nonproduction_manifest_entry(self) -> None:
        config = protocol.load_config()
        config["production"]["tasks"] = [{
            "id": "uct-30000-self-play", "iteration_limit": 30000,
            "budget_seed_offset": 30000000, "target_games": 1,
            "count_status": "test",
        }]
        task = protocol.tasks_from_config(config, "production")[0]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = root / "production/manifest.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text(json.dumps({"tasks": {task.task_id: {
                **task.__dict__, "namespace": "pilot", "state": "completed",
                "artifacts": {"result": "pilot/result.csv"},
            }}}), encoding="utf-8")
            finalization = root / "production/finalization.json"
            finalization.write_text(json.dumps({
                "planned_games_by_budget": {"30000": 1},
                "analyzed_games_by_budget": {"30000": 1},
                "additional_production_execution_forbidden": True,
                "excluded_tasks": [],
            }), encoding="utf-8")
            with mock.patch.object(protocol, "RESULTS_ROOT", root), mock.patch.object(run_analysis, "FINALIZATION", finalization):
                with self.assertRaisesRegex(ValueError, "non-production"):
                    run_analysis.production_rows(config)

    def test_finalization_accepts_only_exact_recorded_failed_identity(self) -> None:
        config = protocol.load_config()
        config["production"]["tasks"] = [{
            "id": "uct-100000-self-play", "iteration_limit": 100000,
            "budget_seed_offset": 100000000, "target_games": 2,
            "count_status": "test",
        }]
        first, second = protocol.tasks_from_config(config, "production")
        manifest = {"tasks": {
            first.task_id: {**first.__dict__, "state": "completed", "attempts": 1},
            second.task_id: {**second.__dict__, "state": "failed", "attempts": 2},
        }}
        with tempfile.TemporaryDirectory() as temporary:
            finalization = Path(temporary) / "finalization.json"
            finalization.write_text(json.dumps({
                "planned_games_by_budget": {"100000": 2},
                "analyzed_games_by_budget": {"100000": 1},
                "additional_production_execution_forbidden": True,
                "excluded_tasks": [{
                    "task_id": second.task_id, "game_index": second.game_index,
                    "seed": second.seed, "final_state": "failed", "attempts": 2,
                }],
            }), encoding="utf-8")
            with mock.patch.object(run_analysis, "FINALIZATION", finalization):
                value = run_analysis.load_finalization(config, manifest)
                self.assertEqual(value["analyzed_games_by_budget"]["100000"], 1)
                value["excluded_tasks"][0]["seed"] += 1
                finalization.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "does not match manifest"):
                    run_analysis.load_finalization(config, manifest)

    def test_required_outputs_are_frozen_before_production(self) -> None:
        config = protocol.load_config()
        self.assertEqual(len(config["required_outputs"]), 10)
        self.assertIn("strategic-convergence-summary.csv", config["required_outputs"])
        self.assertFalse(config["convergence_classification"]["manual_override_allowed"])


if __name__ == "__main__":
    unittest.main()
