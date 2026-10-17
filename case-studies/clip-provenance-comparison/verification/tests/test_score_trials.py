#!/usr/bin/env python3
"""Regression checks for the public Clip Provenance scorer."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "clip_provenance_score_trials", ROOT / "verification/score_trials.py"
)
SCORER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(SCORER)


class ScoreTrialsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = SCORER.score_suite(ROOT)

    def test_truth_composition(self):
        self.assertEqual(
            self.result["truth_summary"], {"rows": 200, "genuine": 160, "foreign": 40}
        )

    def test_recorded_snapshot_metrics(self):
        expected = {
            "deepseek": {
                "accepted_matches": 151,
                "accepted_correct_sources": 151,
                "accepted_correct_source_and_time": 151,
                "proposed_correct_genuine_sources": 160,
                "proposed_correct_genuine_source_and_time": 160,
                "explicit_foreign_rejections": 22,
                "genuine_unidentified": 0,
                "uncertain_rows": 27,
                "uncertain_genuine": 9,
                "uncertain_foreign": 18,
            },
            "astra": {
                "accepted_matches": 137,
                "accepted_correct_sources": 137,
                "accepted_correct_source_and_time": 137,
                "proposed_correct_genuine_sources": 160,
                "proposed_correct_genuine_source_and_time": 159,
                "explicit_foreign_rejections": 40,
                "genuine_unidentified": 0,
                "uncertain_rows": 23,
                "uncertain_genuine": 23,
                "uncertain_foreign": 0,
            },
            "kimi-round2": {
                "accepted_matches": 134,
                "accepted_correct_sources": 134,
                "accepted_correct_source_and_time": 133,
                "proposed_correct_genuine_sources": 140,
                "proposed_correct_genuine_source_and_time": 139,
                "explicit_foreign_rejections": 34,
                "genuine_unidentified": 19,
                "uncertain_rows": 13,
                "uncertain_genuine": 7,
                "uncertain_foreign": 6,
            },
            "kimi-round3": {
                "accepted_matches": 136,
                "accepted_correct_sources": 134,
                "accepted_correct_source_and_time": 132,
                "proposed_correct_genuine_sources": 144,
                "proposed_correct_genuine_source_and_time": 141,
                "explicit_foreign_rejections": 14,
                "genuine_unidentified": 10,
                "uncertain_rows": 40,
                "uncertain_genuine": 16,
                "uncertain_foreign": 24,
            },
        }
        for trial, wanted in expected.items():
            metrics = self.result["trials"][trial]["metrics"]
            with self.subTest(trial=trial):
                self.assertEqual({key: metrics[key] for key in wanted}, wanted)

    def test_each_snapshot_covers_the_same_200_clips(self):
        wanted = {f"clip_{index:03d}.mp4" for index in range(200)}
        for trial, result in self.result["trials"].items():
            with self.subTest(trial=trial):
                self.assertEqual({row["clip"] for row in result["rows"]}, wanted)

    def test_tolerance_is_inclusive(self):
        truth = {
            "clip_000.mp4": {
                "clip": "clip_000.mp4",
                "master": "master_00.mp4",
                "offset_sec": 10.0,
            }
        }
        row = {
            "clip": "clip_000.mp4",
            "native_tier": "confident",
            "tier": "confident",
            "candidate_master": "master_00.mp4",
            "candidate_offset": 11.5,
        }
        result = SCORER.score_trial([row], truth, "astra", 1.5)
        self.assertTrue(result["rows"][0]["joint_correct"])


if __name__ == "__main__":
    unittest.main()
