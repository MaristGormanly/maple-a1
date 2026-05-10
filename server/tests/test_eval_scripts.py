"""Tests for M4 eval harness scripts (tasks 4.C.2–4.C.6, 4.E.2).

Each script under eval/scripts/ exposes a pure helper (no I/O except
where noted) so the pilot operator has deterministic tooling for
data collection. We test the helpers; CLI wiring is thin argparse
and not worth unit-testing.
"""

import csv
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class PilotRunLogTests(unittest.TestCase):
    def test_append_creates_header_then_row(self) -> None:
        from eval.scripts.pilot_run_log import append_run_row

        with TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "pilot-run-log.csv"
            append_run_row(
                csv_path,
                {
                    "submission_id": "sub_1",
                    "commit_hash": "abc123",
                    "latency_ms_total": 12345,
                    "models_used": "gemini-3.1-pro-preview",
                    "estimated_cost_usd": 0.42,
                },
            )
            append_run_row(
                csv_path,
                {
                    "submission_id": "sub_2",
                    "commit_hash": "def456",
                    "latency_ms_total": 9999,
                    "models_used": "gemini-3.1-flash-lite",
                    "estimated_cost_usd": 0.11,
                },
            )

            with csv_path.open() as f:
                rows = list(csv.DictReader(f))

            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["submission_id"], "sub_1")
            self.assertEqual(rows[1]["commit_hash"], "def456")

    def test_append_rejects_missing_required_column(self) -> None:
        from eval.scripts.pilot_run_log import append_run_row

        with TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "pilot-run-log.csv"
            with self.assertRaises(ValueError):
                append_run_row(csv_path, {"submission_id": "sub_1"})


class RubricAlignmentTests(unittest.TestCase):
    def test_delta_computation_and_pct_within_5(self) -> None:
        from eval.scripts.rubric_alignment import compute_deltas

        ai = [
            {"criterion_id": "c1", "score": 90},
            {"criterion_id": "c2", "score": 70},
            {"criterion_id": "c3", "score": 50},
        ]
        instructor = [
            {"criterion_id": "c1", "score": 92},  # delta 2, within
            {"criterion_id": "c2", "score": 65},  # delta 5, within
            {"criterion_id": "c3", "score": 40},  # delta 10, NOT within
        ]
        result = compute_deltas(ai, instructor)

        self.assertEqual(len(result["rows"]), 3)
        deltas = {r["criterion_id"]: r["delta"] for r in result["rows"]}
        self.assertEqual(deltas, {"c1": 2, "c2": 5, "c3": 10})
        self.assertAlmostEqual(result["pct_within_5_points"], 2 / 3)

    def test_mismatched_criterion_ids_raise(self) -> None:
        from eval.scripts.rubric_alignment import compute_deltas

        with self.assertRaises(ValueError):
            compute_deltas(
                [{"criterion_id": "c1", "score": 90}],
                [{"criterion_id": "cX", "score": 90}],
            )


class ConsistencyRunTests(unittest.TestCase):
    def test_per_criterion_variance(self) -> None:
        from eval.scripts.consistency_run import compute_per_criterion_variance

        runs = [
            [{"criterion_id": "c1", "score": 80}, {"criterion_id": "c2", "score": 60}],
            [{"criterion_id": "c1", "score": 82}, {"criterion_id": "c2", "score": 58}],
            [{"criterion_id": "c1", "score": 81}, {"criterion_id": "c2", "score": 62}],
        ]
        variance = compute_per_criterion_variance(runs)
        self.assertIn("c1", variance)
        self.assertIn("c2", variance)
        # max - min for c1 is 82-80=2; for c2 is 62-58=4
        self.assertEqual(variance["c1"]["range"], 2)
        self.assertEqual(variance["c2"]["range"], 4)
        self.assertTrue(variance["c1"]["within_target"])  # range <= 3
        self.assertFalse(variance["c2"]["within_target"])

    def test_requires_at_least_two_runs(self) -> None:
        from eval.scripts.consistency_run import compute_per_criterion_variance

        with self.assertRaises(ValueError):
            compute_per_criterion_variance([[{"criterion_id": "c1", "score": 80}]])


class GradingTimeTests(unittest.TestCase):
    def test_valid_row_passes(self) -> None:
        from eval.scripts.grading_time import validate_row

        row = {"submission_id": "sub_1", "mode": "manual", "seconds": 900}
        self.assertEqual(validate_row(row), row)

    def test_rejects_unknown_mode(self) -> None:
        from eval.scripts.grading_time import validate_row

        with self.assertRaises(ValueError):
            validate_row({"submission_id": "sub_1", "mode": "other", "seconds": 10})

    def test_rejects_negative_seconds(self) -> None:
        from eval.scripts.grading_time import validate_row

        with self.assertRaises(ValueError):
            validate_row({"submission_id": "sub_1", "mode": "manual", "seconds": -1})


class CalibrationRatingsTests(unittest.TestCase):
    def test_valid_ratings_pass(self) -> None:
        from eval.scripts.calibration_ratings import validate_ratings

        row = {
            "submission_id": "sub_1",
            "clarity": 5,
            "relevance": 4,
            "instructional_value": 3,
        }
        self.assertEqual(validate_ratings(row), row)

    def test_out_of_range_rating_rejected(self) -> None:
        from eval.scripts.calibration_ratings import validate_ratings

        with self.assertRaises(ValueError):
            validate_ratings(
                {
                    "submission_id": "sub_1",
                    "clarity": 6,
                    "relevance": 3,
                    "instructional_value": 3,
                }
            )

    def test_non_integer_rating_rejected(self) -> None:
        from eval.scripts.calibration_ratings import validate_ratings

        with self.assertRaises(ValueError):
            validate_ratings(
                {
                    "submission_id": "sub_1",
                    "clarity": 4.5,
                    "relevance": 3,
                    "instructional_value": 3,
                }
            )

    def test_missing_rating_rejected(self) -> None:
        from eval.scripts.calibration_ratings import validate_ratings

        with self.assertRaises(ValueError):
            validate_ratings({"submission_id": "sub_1", "clarity": 4, "relevance": 3})


if __name__ == "__main__":
    unittest.main()
