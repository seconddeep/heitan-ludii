#!/usr/bin/env python3
"""Frozen bootstrap and classification tests for Issue #112."""

from __future__ import annotations

import unittest

import protocol
import run_analysis


class BootstrapTests(unittest.TestCase):
    def test_percentile_linear_interpolation(self):self.assertEqual(run_analysis.percentile([0,10],.25),2.5)
    def test_rate_is_deterministic(self):self.assertEqual(run_analysis.bootstrap_rate([1,0,1],100,112),run_analysis.bootstrap_rate([1,0,1],100,112))
    def test_difference_is_ordered(self):
        low,high=run_analysis.bootstrap_difference([1]*10,[0]*10,100,1);self.assertEqual((low,high),(1.0,1.0))
    def test_paired_terminal_rescore_difference(self):
        low,high=run_analysis.bootstrap_paired_difference([1]*10,[0]*10,100,1);self.assertEqual((low,high),(1.0,1.0))
    def test_magnitude_excess(self):
        low,high=run_analysis.bootstrap_magnitude_excess([1]*10,[0]*10,[0]*10,100,1);self.assertEqual((low,high),(1.0,1.0))
    def test_did_resamples_four_samples(self):
        low,high=run_analysis.bootstrap_did([1]*5,[0]*5,[1]*5,[1]*5,100,1);self.assertEqual((low,high),(1.0,1.0))


class ClassificationTests(unittest.TestCase):
    def setUp(self):self.config=protocol.load_config()
    def test_depth_precedence(self):
        label,_=run_analysis.classify_stability([.5,.56,.51],[100]*3,self.config["stability_classification"]);self.assertEqual(label,"non-monotonic")
    def test_monotonic_but_unresolved(self):
        label,_=run_analysis.classify_stability([.4,.5,.6],[100]*3,self.config["stability_classification"]);self.assertEqual(label,"monotonic but unresolved")
    def test_historical_pattern_persists(self):
        policy=self.config["analysis"]["historical_pattern_label_policy"];self.assertEqual(run_analysis.classify_historical_pattern(.1,(.0,.2),[100]*3,policy),"persists")
    def test_historical_pattern_reverses(self):
        policy=self.config["analysis"]["historical_pattern_label_policy"];self.assertEqual(run_analysis.classify_historical_pattern(-.1,(-.2,0),[100]*3,policy),"reverses")
    def test_historical_pattern_stabilizes(self):
        policy=self.config["analysis"]["historical_pattern_label_policy"];self.assertEqual(run_analysis.classify_historical_pattern(.02,(-.1,.1),[100]*3,policy),"stabilizes")
    def test_historical_pattern_unresolved(self):
        policy=self.config["analysis"]["historical_pattern_label_policy"];self.assertEqual(run_analysis.classify_historical_pattern(.08,(-.1,.2),[100]*3,policy),"unresolved")


if __name__=="__main__":unittest.main()
