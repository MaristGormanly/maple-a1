import unittest

from app.services.test_parser import parse_test_results


class ParseTestResultsTests(unittest.TestCase):
    # ---- pytest ----

    def test_pytest_all_pass(self) -> None:
        stdout = (
            "test_math.py::test_add PASSED\n"
            "test_math.py::test_sub PASSED\n"
            "\n"
            "========================= 2 passed in 0.03s =========================\n"
        )
        result = parse_test_results(stdout, "", 0)
        self.assertEqual(result["framework"], "pytest")
        self.assertEqual(result["passed"], 2)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["errors"], 0)
        self.assertEqual(result["skipped"], 0)
        self.assertIsNone(result["resource_constraint_metadata"])
        self.assertFalse(result["raw_output_truncated"])

    def test_pytest_mixed(self) -> None:
        stdout = (
            "test_math.py::test_add PASSED\n"
            "test_math.py::test_div FAILED\n"
            "test_math.py::test_mul PASSED\n"
            "\n"
            "========================= 1 failed, 2 passed in 0.05s =========================\n"
        )
        result = parse_test_results(stdout, "", 1)
        self.assertEqual(result["framework"], "pytest")
        self.assertEqual(result["passed"], 2)
        self.assertEqual(result["failed"], 1)

    def test_pytest_build_failure(self) -> None:
        stderr = (
            "SyntaxError: invalid syntax (main.py, line 42)\n"
        )
        result = parse_test_results("", stderr, 2)
        self.assertEqual(result["framework"], "unknown")
        self.assertEqual(result["errors"], 1)
        self.assertTrue(any(t["status"] == "error" for t in result["tests"]))
        self.assertIn("SyntaxError", result["tests"][0]["message"])

    # ---- JUnit XML ----

    def test_junit_xml(self) -> None:
        stdout = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<testsuite name="MathTest" tests="3" failures="1" errors="0" skipped="0">\n'
            '  <testcase name="testAdd" classname="MathTest"/>\n'
            '  <testcase name="testSub" classname="MathTest">\n'
            '    <failure message="expected 5 but was 3">assertion error</failure>\n'
            '  </testcase>\n'
            '  <testcase name="testMul" classname="MathTest"/>\n'
            '</testsuite>\n'
        )
        result = parse_test_results(stdout, "", 0)
        self.assertEqual(result["framework"], "junit")
        self.assertEqual(result["passed"], 2)
        self.assertEqual(result["failed"], 1)
        failed_test = next(t for t in result["tests"] if t["status"] == "failed")
        self.assertEqual(failed_test["name"], "testSub")
        self.assertEqual(failed_test["message"], "expected 5 but was 3")

    # ---- Jest ----

    def test_jest_output(self) -> None:
        stdout = (
            "PASS src/math.test.js\n"
            "  Math operations\n"
            "    ✓ adds numbers (3 ms)\n"
            "    ✓ subtracts numbers (1 ms)\n"
            "    ✕ multiplies numbers (2 ms)\n"
            "\n"
            "Test Suites: 1 passed, 1 total\n"
            "Tests:       1 failed, 2 passed, 3 total\n"
        )
        result = parse_test_results(stdout, "", 1)
        self.assertEqual(result["framework"], "jest")
        self.assertEqual(result["passed"], 2)
        self.assertEqual(result["failed"], 1)

    # ---- resource constraints ----

    def test_exit_code_137_oom(self) -> None:
        result = parse_test_results("", "Killed", 137)
        meta = result["resource_constraint_metadata"]
        self.assertIsNotNone(meta)
        self.assertTrue(meta["oom_killed"])
        self.assertFalse(meta["timed_out"])
        self.assertEqual(meta["exit_code"], 137)

    def test_exit_code_124_timeout(self) -> None:
        result = parse_test_results("", "timeout", 124)
        meta = result["resource_constraint_metadata"]
        self.assertIsNotNone(meta)
        self.assertFalse(meta["oom_killed"])
        self.assertTrue(meta["timed_out"])
        self.assertEqual(meta["exit_code"], 124)

    # ---- edge cases ----

    def test_empty_output(self) -> None:
        result = parse_test_results("", "", 0)
        self.assertEqual(result["framework"], "unknown")
        self.assertEqual(result["passed"], 0)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["errors"], 0)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(result["tests"], [])
        self.assertIsNone(result["resource_constraint_metadata"])

    def test_unrecognized_framework(self) -> None:
        stdout = "All 5 checks ok\nDone.\n"
        result = parse_test_results(stdout, "", 0)
        self.assertEqual(result["framework"], "unknown")
        self.assertEqual(result["passed"], 0)
        self.assertEqual(result["tests"], [])

    # ---- truncation flag ----

    def test_raw_output_truncated_flag(self) -> None:
        long_stdout = "x" * 60_000
        result = parse_test_results(long_stdout, "", 0)
        self.assertTrue(result["raw_output_truncated"])


class TestMavenSurefireParser(unittest.TestCase):
    """Regression tests for _parse_maven_surefire aggregate-line handling."""

    def _maven_output(self, class_lines: list[str], aggregate: str) -> str:
        return "\n".join(class_lines) + "\n" + aggregate + "\n"

    def test_named_class_lines_used_over_aggregate(self) -> None:
        # When per-class lines AND aggregate are both visible (normal tail),
        # the parser must use only the named entries — not generate 9267
        # "unknown#N" synthetic duplicates from the aggregate.
        output = (
            "[INFO] Tests run: 12, Failures: 0, Errors: 0, Skipped: 0, "
            "Time elapsed: 0.1 s - in com.example.FooTest\n"
            "[INFO] Tests run: 8, Failures: 1, Errors: 0, Skipped: 0, "
            "Time elapsed: 0.2 s - in com.example.BarTest\n"
            "[INFO] Tests run: 20, Failures: 1, Errors: 0, Skipped: 0\n"  # aggregate
        )
        result = parse_test_results(output, "", 0)
        self.assertEqual(result["framework"], "maven_surefire")
        # Must NOT have 20 "unknown#N" entries from the aggregate
        names = [t["name"] for t in result["tests"]]
        self.assertFalse(any("unknown" in n for n in names), "aggregate must be skipped when named lines exist")
        # Must have entries only from the two named classes
        self.assertEqual(result["passed"], 12 + 7)  # 12 + (8-1)
        self.assertEqual(result["failed"], 1)

    def test_aggregate_only_fallback(self) -> None:
        # When only the aggregate line is visible (all per-class lines were
        # in the discarded middle of a truncated log), fall back to it so
        # the AI still sees a total count.
        output = "[INFO] Tests run: 50, Failures: 2, Errors: 1, Skipped: 3\n"
        result = parse_test_results(output, "", 0)
        self.assertEqual(result["framework"], "maven_surefire")
        self.assertEqual(result["passed"], 44)
        self.assertEqual(result["failed"], 2)
        self.assertEqual(result["errors"], 1)
        self.assertEqual(result["skipped"], 3)

    def test_no_unknown_entries_when_named_present(self) -> None:
        output = (
            "[INFO] Tests run: 3, Failures: 0, Errors: 0, Skipped: 0, "
            "Time elapsed: 0.05 s - in com.example.AlphaTest\n"
            "[INFO] Tests run: 9267, Failures: 0, Errors: 0, Skipped: 0\n"
        )
        result = parse_test_results(output, "", 0)
        self.assertEqual(len(result["tests"]), 3)
        self.assertTrue(all("com.example.AlphaTest" in t["name"] for t in result["tests"]))


if __name__ == "__main__":
    unittest.main()
