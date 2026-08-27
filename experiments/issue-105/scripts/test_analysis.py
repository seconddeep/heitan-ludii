#!/usr/bin/env python3
"""Regression and integration tests for the Issue #105 audit."""

from __future__ import annotations

from collections import Counter
import unittest

import common
import run_analysis
import scoring


class AdvantageOnlyScoringTests(unittest.TestCase):
    def test_partition_and_own_secured_exclusion(self) -> None:
        board = "|".join([
            "O00:1:2:1",  # P1 Advantage
            "O01:2:1:2",  # P2 Advantage
            "O02:3:3:1",  # P1 Secured
            "O03:4:1:3",  # P2 Secured
            "O04:0:2:2",  # neutral
            "S00:0:0:0",
        ])
        result = scoring.audit_terminal_board(board)
        self.assertEqual(result["previous_p1_objective_pieces"], 9)
        self.assertEqual(result["corrected_p1_objective_pieces"], 2)
        self.assertEqual(result["p1_excluded_own_secured"], 3)
        self.assertEqual(result["p1_excluded_opponent_secured"], 1)
        self.assertEqual(result["p1_excluded_opponent_advantage"], 1)
        self.assertEqual(result["p1_excluded_neutral"], 2)
        self.assertEqual(result["previous_p2_objective_pieces"], 9)
        self.assertEqual(result["corrected_p2_objective_pieces"], 2)
        self.assertEqual(result["p2_excluded_own_secured"], 3)
        self.assertEqual(result["p2_excluded_opponent_secured"], 1)
        self.assertEqual(result["p2_excluded_opponent_advantage"], 1)
        self.assertEqual(result["p2_excluded_neutral"], 2)
        self.assertTrue(result["reaches_objective_piece_tiebreak"])

    def test_own_secured_is_exactly_three_per_secured_objective(self) -> None:
        invalid = "O00:3:2:0|O01:4:0:3"
        with self.assertRaisesRegex(ValueError, "own-Secured"):
            scoring.audit_terminal_board(invalid)

    def test_only_own_advantage_pieces_decide_corrected_tiebreak(self) -> None:
        board = "|".join([
            "O00:1:1:2",
            "O01:2:2:2",
            "O02:3:3:0",
            "O03:4:0:3",
            "O04:0:4:0",
        ])
        result = scoring.audit_terminal_board(board)
        self.assertEqual(result["old_reconstructed_winner"], 1)
        self.assertEqual(result["corrected_winner"], 2)
        self.assertEqual(result["corrected_deciding_layer"], "objective_pieces")

    def test_lexicographic_precedence(self) -> None:
        self.assertEqual(scoring.winner_and_layer((2, 1), (0, 9), (0, 99)), (1, "secured_objectives"))
        self.assertEqual(scoring.winner_and_layer((2, 2), (1, 3), (99, 0)), (2, "advantage_objectives"))
        self.assertEqual(scoring.winner_and_layer((2, 2), (1, 1), (4, 3)), (1, "objective_pieces"))
        self.assertEqual(scoring.winner_and_layer((2, 2), (1, 1), (3, 3)), (0, "draw"))

    def test_winner_transition_labels_cover_all_directions(self) -> None:
        expected = {
            (1, 2): "P1->P2", (2, 1): "P2->P1", (1, 0): "P1->draw",
            (2, 0): "P2->draw", (0, 1): "draw->P1", (0, 2): "draw->P2",
        }
        self.assertEqual({pair: run_analysis.transition(*pair) for pair in expected}, expected)


class FrozenSourceGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not common.SOURCE_LOCK.is_file() or not common.PROTOCOL_LOCK.is_file():
            raise unittest.SkipTest("Issue #105 inputs have not been frozen")
        cls.config = common.load_json(common.CONFIG_PATH)
        cls.source = common.load_json(common.SOURCE_LOCK)
        run_analysis.verify_locks(cls.config, cls.source)
        cache: dict[str, list[dict[str, str]]] = {}
        cls.games = [
            run_analysis.audit_game(game, run_analysis.source_result(game, cache))
            for game in cls.source["games"]
        ]

    def test_minimum_597_old_winner_gate(self) -> None:
        minimum = [row for row in self.games if row["minimum_gate"]]
        self.assertEqual(len(minimum), 597)
        self.assertEqual(sum(row["status"] == "resolved" for row in minimum), 597)
        self.assertEqual(sum(bool(row["old_winner_reproduced"]) for row in minimum), 597)

    def test_extended_retained_games_are_reconstructable(self) -> None:
        self.assertEqual(len(self.games), 2537)
        self.assertEqual(sum(row["status"] == "resolved" for row in self.games), 2537)
        self.assertEqual(sum(bool(row["old_winner_reproduced"]) for row in self.games), 2537)

    def test_expected_dataset_counts(self) -> None:
        counts = Counter((row["board"], row["iteration_limit"]) for row in self.games if row["minimum_gate"])
        self.assertEqual(counts, {
            ("3x3", 10000): 100, ("3x3", 30000): 100, ("3x3", 100000): 100,
            ("4x4", 10000): 100, ("4x4", 30000): 100, ("4x4", 100000): 97,
        })

    def test_every_piece_partition_and_own_secured_invariant(self) -> None:
        for row in self.games:
            for player in (1, 2):
                excluded = sum(int(row[f"p{player}_excluded_{name}"]) for name in (
                    "own_secured", "opponent_secured", "opponent_advantage", "neutral"
                ))
                self.assertEqual(
                    int(row[f"previous_p{player}_objective_pieces"]),
                    int(row[f"corrected_p{player}_objective_pieces"]) + excluded,
                )
                self.assertEqual(
                    int(row[f"p{player}_excluded_own_secured"]),
                    3 * int(row[f"p{player}_secured_objectives"]),
                )

    def test_current_game_definition_is_advantage_only(self) -> None:
        text = (common.REPO_ROOT / "games/Heitan.lud").read_text(encoding="utf-8")
        definition = text.split('(define "ScoringPiecesOnObjectives"', 1)[1].split('(define "ObjectiveScore"', 1)[0]
        self.assertIn('(= ("PointState" (to)) #1)', definition)


if __name__ == "__main__":
    unittest.main()
