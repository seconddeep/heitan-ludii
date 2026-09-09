#!/usr/bin/env python3
"""Protocol, corrected scoring, normalization, and resume tests."""

from collections import Counter
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import freeze_protocol, protocol, run_experiments

class ConfigurationTests(unittest.TestCase):
    def test_fixed_tasks_denominator_and_unique_seeds(self):
        config=protocol.load_config();protocol.validate_config(config);tasks=protocol.tasks_from_config(config,"production")
        self.assertEqual(len(tasks),30);self.assertEqual(len({task.seed for task in tasks}),30);self.assertEqual(Counter(task.iteration_limit for task in tasks),Counter({10000:30}))
        self.assertEqual(config["analysis"]["primary_denominator"],"validated completed games");self.assertFalse(config["constraints"]["failed_seed_replacement_allowed"])
    def test_source_gate_checks_board_and_exact_corrected_semantics(self):
        gate=freeze_protocol.game_definition_gate(protocol.load_config())
        self.assertEqual((gate["pieces_per_player"],gate["total_placements"]),(72,144));self.assertEqual((gate["advantage_weight"],gate["secured_weight"]),(73,3650))
        self.assertEqual(gate["corrected_objective_piece_semantics"],"own Pieces on own-Advantage Objectives only")

class ScoringTests(unittest.TestCase):
    def board(self):return [f"S{r}{c}:0:0:0" for r in range(8) for c in range(8)]+[f"O{r}{c}:0:0:0" for r in range(7) for c in range(7)]
    def test_only_own_pieces_on_own_advantage_score(self):
        values=self.board();values[64]="O00:1:2:1";values[65]="O01:2:1:2";metrics=run_experiments.audit_board("|".join(values))
        self.assertEqual(metrics["p1_corrected_objective_pieces"],2);self.assertEqual(metrics["p2_corrected_objective_pieces"],2)
        self.assertEqual(metrics["p1_excluded_opponent_advantage"],1);self.assertEqual(metrics["p2_excluded_opponent_advantage"],1)
    def test_secured_and_advantage_precede_pieces(self):
        values=self.board();values[64]="O00:3:3:0";values[65]="O01:2:0:3";self.assertEqual(run_experiments.audit_board("|".join(values))["winner"],1)
        values=self.board();values[64]="O00:1:1:0";values[65]="O01:2:0:3";values[66]="O02:1:1:0";self.assertEqual(run_experiments.audit_board("|".join(values))["winner"],1)
    def test_draw_requires_all_layers_tied(self):self.assertEqual(run_experiments.audit_board("|".join(self.board()))["winner"],0)
    def test_weights_preserve_lexicographic_order(self):self.assertGreater(73,72);self.assertGreater(3650,49*73+72)
    def test_secured_piece_partition_is_enforced(self):
        values=self.board();values[64]="O00:3:2:0"
        with self.assertRaises(run_experiments.ScoreWinnerMismatch):run_experiments.audit_board("|".join(values))

class TrialTests(unittest.TestCase):
    def test_normalization_is_portable(self):
        with tempfile.TemporaryDirectory() as directory:
            raw=Path(directory)/"raw.trl";normalized=Path(directory)/"normalized.trl";raw.write_bytes(b"game=/private/path/Game.lud\r\nSTART GAME OPTIONS\r\nBoard/7x7\r\n")
            run_experiments.normalize_trial(raw,normalized,"games/Heitan.lud");self.assertEqual(normalized.read_bytes(),b"game=games/Heitan.lud\nSTART GAME OPTIONS\nBoard/7x7\n")

class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.repo=self.root/"repo";self.repo.mkdir();self.results=self.root/"results";self.task=protocol.Task("task","v","production","exp",10000,1,123);self.patches=[mock.patch.object(protocol,"REPO_ROOT",self.repo),mock.patch.object(protocol,"RESULTS_ROOT",self.results)]
        for patch in self.patches:patch.start()
    def tearDown(self):
        for patch in reversed(self.patches):patch.stop()
        self.temp.cleanup()
    def test_stale_task_keeps_identity(self):
        manifest=protocol.empty_manifest("production",[self.task],"hash");manifest["tasks"]["task"].update(state="running",run_owner={"pid":999999,"runner_id":"local-runner"});protocol.atomic_write_json(protocol.manifest_path("production"),manifest)
        row=protocol.reconcile_manifest("production",[self.task],"hash")["tasks"]["task"];self.assertEqual(row["state"],"interrupted");self.assertEqual((row["game_index"],row["seed"]),(1,123))

if __name__=="__main__":unittest.main()
