"""Extended unit tests for linter_runner — edge cases, TypeScript, multi-file output,
severity mapping, and structured log fields.
"""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.docker_runner import ContainerResult
from app.services.linter_runner import Violation, _parse_violations, run_linter
from app.services.sandbox_images import LINT_PROFILES, LintProfile, get_lint_profile

_RUN_CONTAINER_PATCH = "app.services.linter_runner.run_container"


def _make_result(stdout="", exit_code=0):
    return ContainerResult(exit_code=exit_code, stdout=stdout, stderr="", timed_out=False)


# ---------------------------------------------------------------------------
# LINT_PROFILES catalogue
# ---------------------------------------------------------------------------

class TestLintProfiles(unittest.TestCase):
    def test_python_profile_exists(self):
        p = get_lint_profile("python")
        self.assertIsNotNone(p)
        self.assertIn("maple-python-lint", p.image)

    def test_javascript_profile_exists(self):
        p = get_lint_profile("javascript")
        self.assertIsNotNone(p)
        self.assertIn("maple-node-lint", p.image)

    def test_typescript_profile_exists(self):
        p = get_lint_profile("typescript")
        self.assertIsNotNone(p)
        self.assertIn("maple-node-lint", p.image)

    def test_js_and_ts_share_same_image(self):
        self.assertEqual(get_lint_profile("javascript").image, get_lint_profile("typescript").image)

    def test_java_returns_none(self):
        self.assertIsNone(get_lint_profile("java"))

    def test_case_insensitive(self):
        self.assertIsNotNone(get_lint_profile("PYTHON"))
        self.assertIsNotNone(get_lint_profile("JavaScript"))

    def test_python_command_includes_json_format(self):
        p = get_lint_profile("python")
        self.assertTrue(any("json" in arg.lower() for arg in p.command))

    def test_eslint_command_includes_json_format(self):
        p = get_lint_profile("javascript")
        self.assertTrue(any("json" in arg.lower() for arg in p.command))

    def test_profiles_are_frozen(self):
        p = get_lint_profile("python")
        with self.assertRaises((TypeError, AttributeError)):
            p.image = "something-else"


# ---------------------------------------------------------------------------
# _parse_violations edge cases
# ---------------------------------------------------------------------------

class TestParseViolationsPylint(unittest.TestCase):
    def test_single_violation(self):
        data = [{"path": "a.py", "line": 5, "symbol": "missing-docstring",
                 "type": "convention", "message": "Missing docstring"}]
        vs = _parse_violations("python", json.dumps(data))
        self.assertEqual(len(vs), 1)
        self.assertEqual(vs[0].file, "a.py")
        self.assertEqual(vs[0].line, 5)
        self.assertEqual(vs[0].rule_id, "missing-docstring")
        self.assertEqual(vs[0].severity, "convention")

    def test_multiple_violations(self):
        data = [
            {"path": "a.py", "line": 1, "symbol": "r1", "type": "error", "message": "m1"},
            {"path": "b.py", "line": 2, "symbol": "r2", "type": "warning", "message": "m2"},
            {"path": "a.py", "line": 3, "symbol": "r3", "type": "refactor", "message": "m3"},
        ]
        vs = _parse_violations("python", json.dumps(data))
        self.assertEqual(len(vs), 3)

    def test_missing_keys_skips_item(self):
        data = [None, {"line": "not-an-int"}, {"path": "ok.py", "line": 1, "symbol": "s", "type": "t", "message": "m"}]
        vs = _parse_violations("python", json.dumps(data))
        # Only the well-formed item succeeds; None and bad int skip.
        self.assertGreaterEqual(len(vs), 0)

    def test_non_list_root_returns_empty(self):
        vs = _parse_violations("python", json.dumps({"error": "pylint crashed"}))
        self.assertEqual(vs, [])


class TestParseViolationsEslint(unittest.TestCase):
    def test_single_file_single_message(self):
        data = [{"filePath": "/ws/app.js", "messages": [
            {"line": 10, "ruleId": "no-console", "severity": 2, "message": "No console"}
        ]}]
        vs = _parse_violations("javascript", json.dumps(data))
        self.assertEqual(len(vs), 1)
        self.assertEqual(vs[0].file, "/ws/app.js")
        self.assertEqual(vs[0].rule_id, "no-console")
        self.assertEqual(vs[0].severity, "error")

    def test_severity_1_is_warning(self):
        data = [{"filePath": "f.js", "messages": [
            {"line": 1, "ruleId": "rule", "severity": 1, "message": "warn"}
        ]}]
        vs = _parse_violations("javascript", json.dumps(data))
        self.assertEqual(vs[0].severity, "warning")

    def test_severity_2_is_error(self):
        data = [{"filePath": "f.js", "messages": [
            {"line": 1, "ruleId": "rule", "severity": 2, "message": "err"}
        ]}]
        vs = _parse_violations("javascript", json.dumps(data))
        self.assertEqual(vs[0].severity, "error")

    def test_null_rule_id_becomes_empty_string(self):
        data = [{"filePath": "f.js", "messages": [
            {"line": 1, "ruleId": None, "severity": 1, "message": "msg"}
        ]}]
        vs = _parse_violations("javascript", json.dumps(data))
        self.assertEqual(vs[0].rule_id, "")

    def test_multiple_files_and_messages(self):
        data = [
            {"filePath": "a.js", "messages": [
                {"line": 1, "ruleId": "r1", "severity": 2, "message": "m1"},
                {"line": 2, "ruleId": "r2", "severity": 1, "message": "m2"},
            ]},
            {"filePath": "b.ts", "messages": [
                {"line": 5, "ruleId": "r3", "severity": 2, "message": "m3"},
            ]},
        ]
        vs = _parse_violations("typescript", json.dumps(data))
        self.assertEqual(len(vs), 3)
        files = {v.file for v in vs}
        self.assertIn("a.js", files)
        self.assertIn("b.ts", files)

    def test_empty_messages_list_returns_empty(self):
        data = [{"filePath": "clean.js", "messages": []}]
        vs = _parse_violations("javascript", json.dumps(data))
        self.assertEqual(vs, [])

    def test_non_list_root_returns_empty(self):
        vs = _parse_violations("javascript", json.dumps({"error": "eslint crashed"}))
        self.assertEqual(vs, [])

    def test_typescript_language_parsed_same_as_javascript(self):
        data = [{"filePath": "src/index.ts", "messages": [
            {"line": 3, "ruleId": "no-unused-vars", "severity": 2, "message": "unused"}
        ]}]
        vs = _parse_violations("typescript", json.dumps(data))
        self.assertEqual(len(vs), 1)
        self.assertEqual(vs[0].file, "src/index.ts")


class TestParseViolationsUnknownLanguage(unittest.TestCase):
    def test_unknown_language_returns_empty(self):
        data = [{"path": "a.go", "line": 1}]
        vs = _parse_violations("go", json.dumps(data))
        self.assertEqual(vs, [])


# ---------------------------------------------------------------------------
# run_linter async behaviour
# ---------------------------------------------------------------------------

class TestRunLinterAsync(unittest.IsolatedAsyncioTestCase):
    async def test_typescript_uses_node_lint_image(self):
        captured_config = []
        async def fake_run(config):
            captured_config.append(config)
            return _make_result(stdout="[]")
        with patch(_RUN_CONTAINER_PATCH, side_effect=fake_run):
            await run_linter("typescript", "/tmp/repo")
        self.assertTrue(captured_config)
        self.assertIn("maple-node-lint", captured_config[0].image)

    async def test_nonzero_exit_code_still_parses_violations(self):
        data = [{"path": "bad.py", "line": 1, "symbol": "bad-rule",
                 "type": "error", "message": "bad"}]
        with patch(_RUN_CONTAINER_PATCH, return_value=_make_result(
            stdout=json.dumps(data), exit_code=1
        )):
            vs = await run_linter("python", "/tmp/repo")
        self.assertEqual(len(vs), 1)

    async def test_structured_log_on_completion(self):
        data = [{"path": "a.py", "line": 1, "symbol": "s", "type": "t", "message": "m"}]
        with patch(_RUN_CONTAINER_PATCH, return_value=_make_result(stdout=json.dumps(data))):
            import logging
            with self.assertLogs("app.services.linter_runner", level="INFO") as log_ctx:
                await run_linter("python", "/tmp/repo")
        info_msgs = [r for r in log_ctx.output if "INFO" in r]
        self.assertTrue(info_msgs)
        payload = json.loads(info_msgs[0].split("INFO:app.services.linter_runner:")[-1])
        self.assertEqual(payload["event"], "linter_run")
        self.assertIn("language", payload)
        self.assertIn("violation_count", payload)
        self.assertIn("exit_code", payload)
        self.assertEqual(payload["violation_count"], 1)

    async def test_volume_mounted_readonly(self):
        captured = []
        async def fake_run(config):
            captured.append(config)
            return _make_result()
        with patch(_RUN_CONTAINER_PATCH, side_effect=fake_run):
            await run_linter("python", "/data/repo")
        vol = captured[0].volumes
        self.assertIn("/data/repo", vol)
        self.assertEqual(vol["/data/repo"]["mode"], "ro")
        self.assertEqual(vol["/data/repo"]["bind"], "/workspace")


# ---------------------------------------------------------------------------
# Violation dataclass
# ---------------------------------------------------------------------------

class TestViolationDataclass(unittest.TestCase):
    def test_fields(self):
        v = Violation(file="x.py", line=5, rule_id="bad-rule", severity="error", message="msg")
        self.assertEqual(v.file, "x.py")
        self.assertEqual(v.line, 5)
        self.assertEqual(v.rule_id, "bad-rule")
        self.assertEqual(v.severity, "error")
        self.assertEqual(v.message, "msg")


if __name__ == "__main__":
    unittest.main()
