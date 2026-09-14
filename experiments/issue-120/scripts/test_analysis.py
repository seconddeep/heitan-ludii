#!/usr/bin/env python3
"""Frozen interval and bootstrap tests."""

import unittest
import run_analysis

class AnalysisTests(unittest.TestCase):
    def test_percentile_linear_interpolation(self):self.assertEqual(run_analysis.percentile([0,10],.25),2.5)
    def test_wilson_known_bounds(self):
        low,high=run_analysis.wilson(0,30);self.assertEqual(low,0);self.assertGreater(high,0)
        low,high=run_analysis.wilson(30,30);self.assertLess(low,1);self.assertAlmostEqual(high,1)
    def test_bootstrap_is_deterministic(self):self.assertEqual(run_analysis.bootstrap_difference([1,0,1],[0,0,1],100,120),run_analysis.bootstrap_difference([1,0,1],[0,0,1],100,120))

    def test_rate_row_retains_draws_in_denominator(self):
        row=run_analysis.rate_row(30000,[{"winner":"1"},{"winner":"2"},{"winner":"0"}])
        self.assertEqual(row,{"uct":30000,"validated":3,"p1_rate":.333333,"draw_rate":.333333})

if __name__=="__main__":unittest.main()
