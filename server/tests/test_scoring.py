import unittest

from app.services.scoring import calculate_deterministic_score


class CalculateDeterministicScoreTests(unittest.TestCase):
    def test_all_pass_returns_100(self) -> None:
        result = calculate_deterministic_score(
            {"passed": 5, "failed": 0, "errors": 0, "skipped": 0, "tests": []}
        )
        self.assertEqual(result, 100.0)

    def test_all_fail_returns_0(self) -> None:
        result = calculate_deterministic_score(
            {"passed": 0, "failed": 4, "errors": 0, "skipped": 0, "tests": []}
        )
        self.assertEqual(result, 0.0)

    def test_mixed_returns_proportional(self) -> None:
        result = calculate_deterministic_score(
            {"passed": 3, "failed": 1, "errors": 0, "skipped": 0, "tests": []}
        )
        self.assertEqual(result, 75.0)

    def test_zero_tests_returns_0(self) -> None:
        result = calculate_deterministic_score(
            {"passed": 0, "failed": 0, "errors": 0, "skipped": 0, "tests": []}
        )
        self.assertEqual(result, 0.0)

    def test_all_errors_returns_0(self) -> None:
        result = calculate_deterministic_score(
            {"passed": 0, "failed": 0, "errors": 3, "skipped": 0, "tests": []}
        )
        self.assertEqual(result, 0.0)

    def test_skipped_excluded_from_total(self) -> None:
        result = calculate_deterministic_score(
            {"passed": 2, "failed": 0, "errors": 0, "skipped": 3, "tests": []}
        )
        self.assertEqual(result, 100.0)

    def test_skipped_with_failures(self) -> None:
        result = calculate_deterministic_score(
            {"passed": 1, "failed": 1, "errors": 0, "skipped": 5, "tests": []}
        )
        self.assertEqual(result, 50.0)

    def test_rubric_weighted_scoring(self) -> None:
        test_results = {
            "passed": 2,
            "failed": 1,
            "errors": 0,
            "skipped": 0,
            "tests": [
                {"name": "test_correctness_add", "status": "passed", "message": None},
                {"name": "test_correctness_sub", "status": "failed", "message": None},
                {"name": "test_style_formatting", "status": "passed", "message": None},
            ],
        }
        rubric = {
            "criteria": [
                {"name": "correctness", "weight": 70},
                {"name": "style", "weight": 30},
            ],
        }
        score = calculate_deterministic_score(test_results, rubric)
        # correctness: 1/2 matched pass -> 70 * 0.5 = 35
        # style:       1/1 matched pass -> 30 * 1.0 = 30
        # total_weight = 100 -> (35+30)/100 * 100 = 65
        self.assertEqual(score, 65.0)

    def test_rubric_without_weights_falls_back(self) -> None:
        result = calculate_deterministic_score(
            {"passed": 3, "failed": 1, "errors": 0, "skipped": 0, "tests": []},
            rubric_content={"criteria": [{"name": "Correctness"}]},
        )
        self.assertEqual(result, 75.0)

    def test_string_rubric_falls_back(self) -> None:
        result = calculate_deterministic_score(
            {"passed": 1, "failed": 1, "errors": 0, "skipped": 0, "tests": []},
            rubric_content="Just grade it",
        )
        self.assertEqual(result, 50.0)


if __name__ == "__main__":
    unittest.main()
