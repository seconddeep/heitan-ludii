#!/usr/bin/env python3
"""Frozen bootstrap and classification tests for Issue #108."""

from __future__ import annotations

import unittest

import protocol
import run_analysis


class BootstrapTests(unittest.TestCase):
    def test_percentile_linear_interpolation(self):self.assertEqual(run_analysis.percentile([0,10],.25),2.5)
    def test_rate_is_deterministic(self):self.assertEqual(run_analysis.bootstrap_rate([1,0,1],100,108),run_analysis.bootstrap_rate([1,0,1],100,108))
    def test_difference_is_ordered(self):
        low,high=run_analysis.bootstrap_difference([1]*10,[0]*10,100,1);self.assertEqual((low,high),(1.0,1.0))
    def test_did_resamples_four_samples(self):
        low,high=run_analysis.bootstrap_did([1]*5,[0]*5,[1]*5,[1]*5,100,1);self.assertEqual((low,high),(1.0,1.0))


class ClassificationTests(unittest.TestCase):
    def setUp(self):self.config=protocol.load_config()
    def test_depth_precedence(self):
        label,_=run_analysis.classify_stability([.5,.56,.51],[100]*3,self.config["stability_classification"]);self.assertEqual(label,"non-monotonic")
    def test_drop_weakens_precedes_persists(self):
        policy=self.config["analysis"]["drop_label_policy"];self.assertEqual(run_analysis.classify_drop((-.3,-.1),(.01,.2),[100]*5,policy),"weakens")
    def test_drop_persists(self):
        policy=self.config["analysis"]["drop_label_policy"];self.assertEqual(run_analysis.classify_drop((-.3,-.1),(-.1,.2),[100]*5,policy),"persists")
    def test_drop_disappears(self):
        policy=self.config["analysis"]["drop_label_policy"];self.assertEqual(run_analysis.classify_drop((0,.2),(-.1,.2),[100]*5,policy),"disappears")
    def test_drop_unresolved_when_ci_crosses_zero(self):
        policy=self.config["analysis"]["drop_label_policy"];self.assertEqual(run_analysis.classify_drop((-.1,.2),(-.1,.2),[100]*5,policy),"unresolved")


if __name__=="__main__":unittest.main()
