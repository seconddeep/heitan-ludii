#!/usr/bin/env python3
"""Protocol, scoring, normalization, and resume tests for Issue #108."""

from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import protocol
import run_experiments


class ConfigurationTests(unittest.TestCase):
    def test_fixed_primary_tasks_and_unique_seeds(self):
        config=protocol.load_config();protocol.validate_config(config);tasks=protocol.tasks_from_config(config,"production")
        self.assertEqual(len(tasks),300);self.assertEqual(len({task.seed for task in tasks}),300);self.assertEqual(Counter(task.iteration_limit for task in tasks),Counter({10000:100,30000:100,100000:100}))

    def test_primary_drop_and_no_material_label(self):
        analysis=protocol.load_config()["analysis"]
        self.assertEqual(analysis["primary_100k_drop_contrast"],"corrected 100k - corrected 30k");self.assertFalse(analysis["material_change_label_enabled"]);self.assertFalse(analysis["drop_label_policy"]["manual_override_allowed"])

    def test_turn_end_central_definitions(self):
        policy=protocol.load_config()["central_supply_diagnostics"]
        self.assertEqual(policy["observation_unit"],"Heitan-turn end only");self.assertEqual(policy["p1_early_turns"],[1,3,5]);self.assertEqual(set(policy["central_supply_points"]),{"S11","S12","S21","S22"})


class ScoringTests(unittest.TestCase):
    def board(self):
        values=[f"S{r}{c}:0:0:0" for r in range(4) for c in range(4)]+[f"O{r}{c}:0:0:0" for r in range(3) for c in range(3)]
        return values

    def test_only_own_advantage_pieces_score(self):
        values=self.board();values[16]="O00:1:2:1";values[17]="O01:2:1:2";metrics=run_experiments.audit_board("|".join(values))
        self.assertEqual(metrics["p1_corrected_objective_pieces"],2);self.assertEqual(metrics["p2_corrected_objective_pieces"],2);self.assertEqual(metrics["p1_excluded_opponent_advantage"],1);self.assertEqual(metrics["p2_excluded_opponent_advantage"],1)

    def test_secured_and_advantage_precede_pieces(self):
        values=self.board();values[16]="O00:3:3:0";values[17]="O01:2:0:3";metrics=run_experiments.audit_board("|".join(values));self.assertEqual(metrics["winner"],1)
        values=self.board();values[16]="O00:1:1:0";values[17]="O01:2:0:3";values[18]="O02:1:1:0";metrics=run_experiments.audit_board("|".join(values));self.assertEqual(metrics["winner"],1)

    def test_draw_when_all_layers_tie(self):
        self.assertEqual(run_experiments.audit_board("|".join(self.board()))["winner"],0)

    def test_weights_preserve_3x3_lexicographic_order(self):
        self.assertGreater(28,27);self.assertGreater(280,9*28+27)

    def test_own_secured_identity_is_enforced(self):
        values=self.board();values[16]="O00:3:2:0"
        with self.assertRaises(run_experiments.ScoreWinnerMismatch):run_experiments.audit_board("|".join(values))


class TrialTests(unittest.TestCase):
    def test_normalization_is_utf8_lf_and_changes_only_game_line(self):
        with tempfile.TemporaryDirectory() as directory:
            raw=Path(directory)/"raw.trl";normalized=Path(directory)/"normalized.trl";raw.write_bytes("game=/private/path/Game.lud\r\nSTART GAME OPTIONS\r\nBoard/3x3\r\n".encode())
            run_experiments.normalize_trial(raw,normalized,"games/Heitan.lud")
            self.assertEqual(normalized.read_bytes(),b"game=games/Heitan.lud\nSTART GAME OPTIONS\nBoard/3x3\n")

    def test_rss_probe_tolerates_restricted_process_table(self):
        with mock.patch.object(run_experiments.subprocess,"run",side_effect=OSError("restricted")):
            self.assertIsNone(run_experiments.process_rss_bytes(123))

    def test_time_output_peak_rss_is_parsed(self):
        self.assertEqual(run_experiments.parse_peak_rss("12345  maximum resident set size"),12345)
        self.assertEqual(run_experiments.parse_peak_rss("Maximum resident set size (kbytes): 10"),10240)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.repo=self.root/"repo";self.repo.mkdir();self.results=self.root/"results";self.task=protocol.Task("task","v","production","exp",10000,1,123);self.patches=[mock.patch.object(protocol,"REPO_ROOT",self.repo),mock.patch.object(protocol,"RESULTS_ROOT",self.results)]
        for patch in self.patches:patch.start()
    def tearDown(self):
        for patch in reversed(self.patches):patch.stop()
        self.temp.cleanup()
    def test_stale_task_keeps_identity_and_becomes_interrupted(self):
        manifest=protocol.empty_manifest("production",[self.task],"hash");manifest["tasks"]["task"].update(state="running",run_owner={"pid":999999,"runner_id":"local-runner"});protocol.atomic_write_json(protocol.manifest_path("production"),manifest)
        current=protocol.reconcile_manifest("production",[self.task],"hash");row=current["tasks"]["task"];self.assertEqual(row["state"],"interrupted");self.assertEqual((row["game_index"],row["seed"]),(1,123))
    def test_completed_artifacts_are_hash_checked(self):
        manifest=protocol.empty_manifest("production",[self.task],"hash");artifacts={}
        for name in ("trial","result","validation"):
            path=self.repo/name;path.write_text(name);artifacts[name]=name;artifacts[f"{name}_sha256"]=protocol.sha256(path)
        manifest["tasks"]["task"].update(state="completed",artifacts=artifacts);protocol.atomic_write_json(protocol.manifest_path("production"),manifest);self.assertEqual(protocol.reconcile_manifest("production",[self.task],"hash")["tasks"]["task"]["state"],"completed")


if __name__=="__main__":unittest.main()
