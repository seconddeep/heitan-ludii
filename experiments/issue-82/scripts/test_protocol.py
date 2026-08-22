#!/usr/bin/env python3
"""Regression tests for Issue #82 identities, resume, and validation gates."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import protocol
import run_experiments


class ConfigurationTests(unittest.TestCase):
    def test_primary_and_optional_budget_are_separate(self) -> None:
        config = protocol.load_config()
        self.assertEqual(config["primary_budgets"], [10000, 30000, 100000])
        self.assertEqual(config["optional_budget"]["iteration_limit"], 300000)
        self.assertFalse(config["optional_budget"]["primary"])
        protocol.validate_all_namespaces(config)

    def test_primary_tasks_have_independent_fixed_seeds(self) -> None:
        tasks = protocol.tasks_from_config(protocol.load_config(), "production")
        self.assertEqual(len(tasks), 300)
        self.assertEqual(len({task.seed for task in tasks}), 300)
        self.assertEqual(Counter(task.iteration_limit for task in tasks), Counter({10000: 100, 30000: 100, 100000: 100}))

    def test_issue_47_thresholds_are_declared_as_reused(self) -> None:
        policy = protocol.load_config()["stability_classification"]
        self.assertEqual(policy["stable_absolute_delta_max"], 0.03)
        self.assertEqual(policy["directionally_stabilizing_latest_delta_max"], 0.07)
        self.assertIn("Issue #47", policy["source"])

    def test_optional_budget_enters_production_only_when_included(self) -> None:
        config = protocol.load_config()
        self.assertFalse(any(task.iteration_limit == 300000 for task in protocol.tasks_from_config(config, "production")))
        config["optional_budget"]["adoption_status"] = "included"
        optional = [task for task in protocol.tasks_from_config(config, "production") if task.iteration_limit == 300000]
        self.assertEqual(len(optional), 100)
        self.assertTrue(all(task.optional_budget for task in optional))


class ManifestResumeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.results = self.root / "results"
        self.task = protocol.Task("task", "v", "production", "exp", 10000, 1, 123)
        self.patches = [mock.patch.object(protocol, "REPO_ROOT", self.repo), mock.patch.object(protocol, "RESULTS_ROOT", self.results)]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temporary.cleanup()

    def write_manifest(self, state: str, **updates) -> None:
        manifest = protocol.empty_manifest("production", [self.task], "hash")
        manifest["tasks"]["task"].update({"state": state, **updates})
        protocol.atomic_write_json(protocol.manifest_path("production"), manifest)

    def test_stale_running_becomes_interrupted_without_identity_change(self) -> None:
        self.write_manifest("running", run_owner={"pid": 987654321, "host": "old-host"})
        manifest = protocol.reconcile_manifest("production", [self.task], "hash")
        row = manifest["tasks"]["task"]
        self.assertEqual(row["state"], "interrupted")
        self.assertEqual((row["game_index"], row["seed"]), (1, 123))
        self.assertTrue(any(event["state"] == "interrupted" for event in row["events"]))

    def test_live_local_running_task_is_not_retried(self) -> None:
        import os, socket
        self.write_manifest("running", run_owner={"pid": os.getpid(), "host": socket.gethostname()})
        with mock.patch.object(protocol, "process_owner_active", return_value=True):
            manifest = protocol.reconcile_manifest("production", [self.task], "hash")
        self.assertEqual(manifest["tasks"]["task"]["state"], "running")

    def test_live_java_keeps_task_active_after_runner_stops(self) -> None:
        owner = {"host": "host", "pid": 1, "java_pid": 2, "java_command_marker": "Heitan3x3Experiment.java"}
        with mock.patch.object(protocol.socket, "gethostname", return_value="host"), mock.patch.object(protocol, "pid_matches", side_effect=[False, True]):
            self.assertTrue(protocol.process_owner_active(owner))

    def test_completed_requires_all_hashed_artifacts(self) -> None:
        artifacts = {}
        for name in ("trial", "result", "validation"):
            path = self.repo / f"{name}.dat"
            path.write_text(name, encoding="utf-8")
            artifacts[name] = path.name
            artifacts[f"{name}_sha256"] = protocol.sha256(path)
        self.write_manifest("completed", artifacts=artifacts)
        manifest = protocol.reconcile_manifest("production", [self.task], "hash")
        self.assertEqual(manifest["tasks"]["task"]["state"], "completed")

    def test_completed_missing_result_becomes_corrupt(self) -> None:
        trial = self.repo / "trial"
        trial.write_text("trial", encoding="utf-8")
        self.write_manifest("completed", artifacts={"trial": "trial", "trial_sha256": protocol.sha256(trial)})
        manifest = protocol.reconcile_manifest("production", [self.task], "hash")
        self.assertEqual(manifest["tasks"]["task"]["state"], "corrupt")

    def test_atomic_write_leaves_no_temporary_file(self) -> None:
        path = self.results / "value.json"
        protocol.atomic_write_json(path, {"ok": True})
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"ok": True})
        self.assertEqual(list(path.parent.glob(".value.json.*")), [])


class ValidationTests(unittest.TestCase):
    def board(self) -> str:
        sites = [f"S{row}{column}:0:0:0" for row in range(4) for column in range(4)]
        sites += [f"O{row}{column}:0:0:0" for row in range(3) for column in range(3)]
        return "|".join(sites)

    def test_board_is_supply_16_plus_objective_9(self) -> None:
        winner, metrics = run_experiments.reconstruct_final_board(self.board())
        self.assertEqual(winner, 0)
        self.assertEqual(metrics["p1_score"], 0)

    def test_missing_site_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "25"):
            run_experiments.reconstruct_final_board("|".join(self.board().split("|")[:-1]))

    def test_lexicographic_score_uses_280_and_28(self) -> None:
        values = self.board().split("|")
        values[16] = "O00:3:1:0"
        values[17] = "O01:2:0:27"
        winner, metrics = run_experiments.reconstruct_final_board("|".join(values))
        self.assertEqual(winner, 1)
        self.assertEqual(metrics["p1_score"], 281)
        self.assertEqual(metrics["p2_score"], 55)

    def test_peak_rss_parses_macos_and_linux(self) -> None:
        self.assertEqual(run_experiments.parse_peak_rss("12345  maximum resident set size"), 12345)
        self.assertEqual(run_experiments.parse_peak_rss("Maximum resident set size (kbytes): 10"), 10240)

    def test_process_rss_is_recorded_in_bytes(self) -> None:
        completed = mock.Mock(returncode=0, stdout="42\n")
        with mock.patch.object(run_experiments.subprocess, "run", return_value=completed):
            self.assertEqual(run_experiments.process_rss_bytes(123), 42 * 1024)

    def test_failures_are_classified_per_game(self) -> None:
        self.assertEqual(run_experiments.failure_kind(RuntimeError("Java heap OutOfMemoryError")), "oom")
        self.assertEqual(run_experiments.failure_kind(ValueError("bad replay")), "validation_failure")

    def test_production_requires_tmux(self) -> None:
        with mock.patch.dict(run_experiments.os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "tmux"):
                run_experiments.require_persistent_execution()

    def test_production_accepts_caffeinate_parent(self) -> None:
        with mock.patch.dict(run_experiments.os.environ, {"TMUX": "session", "HEITAN82_CAFFEINATE": "1"}, clear=True):
            run_experiments.require_persistent_execution()


if __name__ == "__main__":
    unittest.main()
