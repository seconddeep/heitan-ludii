from pathlib import Path
import unittest
import protocol

ROOT=Path(__file__).resolve().parents[3]

class ProtocolTests(unittest.TestCase):
    def setUp(self):self.config=protocol.load_config()
    def test_frozen_matrix_and_unique_tasks(self):
        protocol.validate_prepilot_config(self.config)
        self.assertEqual(3,len(protocol.tasks(self.config,"pilot")))
        self.assertEqual(36,len(protocol.tasks(self.config,"measured")))
    def test_source_values_are_extracted_from_game(self):
        actual=protocol.extract_board_values(ROOT/self.config["game"],self.config["expected_board_values"])
        self.assertEqual(5525,actual["8x8"]["secured_weight"])
        self.assertEqual(56,actual["8x8"]["turns"])
    def test_classification_is_exclusive(self):
        self.assertEqual(["feasible","borderline","infeasible in current environment","not attempted"],self.config["classification"]["categories"])
        self.assertFalse(self.config["classification"]["manual_override_allowed"])
    def test_memory_roles_are_not_conflated(self):
        fields=self.config["measurement_fields"]
        self.assertIn("peak_rss_bytes",fields);self.assertIn("physical_ram_bytes",fields);self.assertIn("jvm_xmx",fields);self.assertIn("gc_log_status",fields)

if __name__=="__main__":unittest.main()
