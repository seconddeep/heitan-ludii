#!/usr/bin/env python3
"""Regression tests for Issue #47 protocol, identity, and resume semantics."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import protocol
import run_experiments


class TaskIdentityTests(unittest.TestCase):
    def test_frozen_tasks_repeat_with_identical_identity(self) -> None:
        config = protocol.load_config()
        first = protocol.tasks_from_config(config, "pilot")
        second = protocol.tasks_from_config(config, "pilot")
        self.assertEqual(first, second)
        self.assertEqual(len({task.seed for task in first}), len(first))

    def test_duplicate_index_is_rejected(self) -> None:
        task = protocol.Task("a", "v", "production", "e", 30000, 1, 1)
        duplicate_index = protocol.Task("b", "v", "production", "e", 30000, 1, 2)
        with self.assertRaisesRegex(ValueError, "duplicate identity"):
            protocol.validate_unique_tasks([task, duplicate_index])

    def test_duplicate_seed_identity_is_rejected(self) -> None:
        one = protocol.Task("a", "v", "production", "e1", 30000, 1, 9)
        two = protocol.Task("b", "v", "production", "e2", 100000, 1, 9)
        with self.assertRaisesRegex(ValueError, "duplicate seed identity"):
            protocol.validate_unique_tasks([one, two])

    def test_pilot_and_production_namespaces_do_not_collide(self) -> None:
        config = protocol.load_config()
        pilot = protocol.tasks_from_config(config, "pilot")
        production_30k = protocol.tasks_from_config(config, "production", 30000)
        self.assertFalse({task.task_id for task in pilot} & {task.task_id for task in production_30k})
        self.assertTrue(all(task.namespace == "pilot" for task in pilot))
        self.assertTrue(all(task.namespace == "production" for task in production_30k))


class ManifestResumeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.results = self.root / "results"
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.task = protocol.Task("task", "v", "production", "exp", 30000, 1, 123)
        self.patches = [
            mock.patch.object(protocol, "RESULTS_ROOT", self.results),
            mock.patch.object(protocol, "REPO_ROOT", self.repo),
        ]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temporary.cleanup()

    def write_manifest(self, state: str, artifacts: dict | None = None) -> None:
        manifest = protocol.empty_manifest("production", [self.task], "config")
        manifest["tasks"]["task"]["state"] = state
        manifest["tasks"]["task"]["artifacts"] = artifacts or {}
        protocol.atomic_write_json(protocol.manifest_path("production"), manifest)

    def test_interrupted_running_task_becomes_retryable_without_identity_change(self) -> None:
        self.write_manifest("running")
        before = self.task
        manifest = protocol.reconcile_manifest("production", [self.task], "config")
        self.assertEqual(manifest["tasks"]["task"]["state"], "failed")
        self.assertEqual(before, self.task)
        self.assertEqual(self.task.seed, 123)

    def test_uninterrupted_and_resumed_runs_have_same_final_task_set(self) -> None:
        tasks = [
            protocol.Task(f"t{i}", "v", "production", "exp", 30000, i, 100 + i)
            for i in range(1, 4)
        ]
        manifest = protocol.empty_manifest("production", tasks, "config")
        manifest["tasks"]["t1"]["state"] = "completed"
        manifest["tasks"]["t2"]["state"] = "running"
        protocol.atomic_write_json(protocol.manifest_path("production"), manifest)
        resumed = protocol.reconcile_manifest("production", tasks, "config")
        self.assertEqual(set(resumed["tasks"]), {task.task_id for task in tasks})
        self.assertEqual(
            [(row["game_index"], row["seed"]) for row in resumed["tasks"].values()],
            [(task.game_index, task.seed) for task in tasks],
        )

    def test_completed_valid_game_is_skipped_safely(self) -> None:
        trial = self.repo / "trial.trl"
        trial.write_text("valid", encoding="utf-8")
        self.write_manifest("completed", {"trial": "trial.trl", "trial_sha256": protocol.sha256(trial)})
        manifest = protocol.reconcile_manifest("production", [self.task], "config")
        self.assertEqual(manifest["tasks"]["task"]["state"], "completed")

    def test_missing_trial_marks_completed_entry_corrupt(self) -> None:
        self.write_manifest("completed", {"trial": "missing.trl", "trial_sha256": "0" * 64})
        manifest = protocol.reconcile_manifest("production", [self.task], "config")
        self.assertEqual(manifest["tasks"]["task"]["state"], "corrupt")

    def test_existing_final_file_hash_mismatch_is_corrupt(self) -> None:
        trial = self.repo / "trial.trl"
        trial.write_text("changed", encoding="utf-8")
        self.write_manifest("completed", {"trial": "trial.trl", "trial_sha256": "0" * 64})
        manifest = protocol.reconcile_manifest("production", [self.task], "config")
        self.assertEqual(manifest["tasks"]["task"]["state"], "corrupt")

    def test_atomic_manifest_write_leaves_no_partial_file(self) -> None:
        target = self.results / "atomic.json"
        protocol.atomic_write_json(target, {"ok": True})
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"ok": True})
        self.assertEqual(list(target.parent.glob(".atomic.json.*")), [])


class ValidationGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.task = protocol.Task("task", "v", "pilot", "pilot-exp", 30000, 1, 123)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_metadata(self, malformed: bool = False) -> None:
        path = self.root / "result.csv"
        fields = ["bad"] if malformed else [
            "experiment_id", "game_index", "seed", "iteration_limit", "completed",
            "end_type", "winner", "moves", "turns", "final_board",
        ]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerow({"bad": "x"} if malformed else {
                "experiment_id": "pilot-exp", "game_index": "1", "seed": "123",
                "iteration_limit": "30000", "completed": "true", "end_type": "NaturalEnd",
                "winner": "0", "moves": "72", "turns": "24", "final_board": "x",
            })

    def test_missing_trial_is_rejected(self) -> None:
        self.write_metadata()
        with self.assertRaisesRegex(FileNotFoundError, "trial"):
            run_experiments.validate_generated(self.task, self.root, Path("jar"), Path("game"))

    def test_malformed_metadata_is_rejected(self) -> None:
        (self.root / "pilot-exp-0001.trl").write_text("trial", encoding="utf-8")
        self.write_metadata(malformed=True)
        with self.assertRaisesRegex(ValueError, "malformed metadata"):
            run_experiments.validate_generated(self.task, self.root, Path("jar"), Path("game"))

    def test_truncated_trial_parse_failure_is_rejected(self) -> None:
        (self.root / "pilot-exp-0001.trl").write_text("truncated", encoding="utf-8")
        self.write_metadata()
        failure = subprocess.CompletedProcess([], 1, "", "parse error")
        with mock.patch.object(run_experiments.subprocess, "run", return_value=failure):
            with self.assertRaisesRegex(ValueError, "parse/legal replay failed"):
                run_experiments.validate_generated(self.task, self.root, Path("jar"), Path("game"))

    def test_valid_final_without_manifest_completion_can_be_recovered(self) -> None:
        final_dir = self.root / "final"
        final_dir.mkdir()
        expected = {"validated": True, "trial_sha256": "abc"}
        with mock.patch.object(run_experiments, "validate_generated", return_value=expected):
            self.assertEqual(
                run_experiments.recover_final_if_valid(self.task, final_dir, Path("jar"), Path("game")),
                expected,
            )

    def test_validation_failure_is_not_recoverable(self) -> None:
        final_dir = self.root / "final"
        final_dir.mkdir()
        with mock.patch.object(run_experiments, "validate_generated", side_effect=ValueError("bad")):
            self.assertIsNone(
                run_experiments.recover_final_if_valid(self.task, final_dir, Path("jar"), Path("game"))
            )

    def test_objective_adjacency(self) -> None:
        self.assertTrue(run_experiments.adjacent("O00", "S11"))
        self.assertFalse(run_experiments.adjacent("O00", "S22"))

    def test_winner_reconstruction_uses_lexicographic_order(self) -> None:
        supplies = [f"S{row}{column}:0:0:0" for row in range(5) for column in range(5)]
        objectives = [f"O{row}{column}:0:0:0" for row in range(4) for column in range(4)]
        objectives[0] = "O00:3:3:0"
        objectives[1] = "O01:2:0:3"
        winner, _ = run_experiments.reconstruct_winner("|".join(supplies + objectives))
        self.assertEqual(winner, 1)


if __name__ == "__main__":
    unittest.main()
