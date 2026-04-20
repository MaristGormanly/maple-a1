"""Unit tests for the linter_runner service (server/app/services/linter_runner.py).

Covers language dispatch, JSON parsing, container-hardening config, and
graceful degradation for unsupported languages or malformed output.

linter_runner.py uses an absolute `server.app.services.docker_runner` import,
so the repo root must be on sys.path at import time.
"""

import asyncio
import json
import sys
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure the repo root is on sys.path so `server` resolves.
# __file__ is server/tests/test_linter_runner.py → repo root is 2 dirs up.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from app.services.docker_runner import ContainerConfig, ContainerResult
from app.services.linter_runner import Violation, run_linter


_RUN_CONTAINER_PATCH = "app.services.linter_runner.run_container"
_GET_LINT_PROFILE_PATCH = "app.services.linter_runner.get_lint_profile"


_PYLINT_FIXTURE = json.dumps([
    {
        "path": "main.py",
        "line": 10,
        "symbol": "missing-docstring",
        "type": "convention",
        "message": "Missing module docstring",
    }
])

_ESLINT_FIXTURE = json.dumps([
    {
        "filePath": "/workspace/app.js",
        "messages": [
            {
                "line": 5,
                "ruleId": "no-console",
                "severity": 2,
                "message": "Unexpected console statement.",
            }
        ],
    }
])


def _make_container_result(stdout: str) -> ContainerResult:
    return ContainerResult(exit_code=0, stdout=stdout, stderr="", timed_out=False)


class TestRunLinterPythonParsesViolations(unittest.TestCase):
    def test_run_linter_python_parses_violations(self):
        mock_result = _make_container_result(_PYLINT_FIXTURE)

        async def _run():
            with patch(_RUN_CONTAINER_PATCH, new=AsyncMock(return_value=mock_result)):
                return await run_linter("python", "/tmp/repo")

        violations = asyncio.run(_run())

        self.assertEqual(len(violations), 1)
        v = violations[0]
        self.assertIsInstance(v, Violation)
        self.assertEqual(v.file, "main.py")
        self.assertEqual(v.line, 10)
        self.assertEqual(v.rule_id, "missing-docstring")
        self.assertEqual(v.severity, "convention")
        self.assertEqual(v.message, "Missing module docstring")


class TestRunLinterEslintParsesViolations(unittest.TestCase):
    def test_run_linter_eslint_parses_violations(self):
        mock_result = _make_container_result(_ESLINT_FIXTURE)

        async def _run():
            with patch(_RUN_CONTAINER_PATCH, new=AsyncMock(return_value=mock_result)):
                return await run_linter("javascript", "/tmp/repo")

        violations = asyncio.run(_run())

        self.assertEqual(len(violations), 1)
        v = violations[0]
        self.assertIsInstance(v, Violation)
        self.assertEqual(v.file, "/workspace/app.js")
        self.assertEqual(v.line, 5)
        self.assertEqual(v.rule_id, "no-console")
        self.assertEqual(v.severity, "error")
        self.assertEqual(v.message, "Unexpected console statement.")


class TestRunLinterNoProfileReturnsEmpty(unittest.TestCase):
    def test_run_linter_no_profile_returns_empty(self):
        async def _run():
            with patch(_RUN_CONTAINER_PATCH, new=AsyncMock()) as mock_container:
                result = await run_linter("cobol", "/tmp/repo")
                return result, mock_container

        violations, mock_container = asyncio.run(_run())

        self.assertEqual(violations, [])
        mock_container.assert_not_called()


class TestRunLinterJsonParseErrorReturnsEmpty(unittest.TestCase):
    def test_run_linter_json_parse_error_returns_empty(self):
        bad_stdout = "this is not { valid json }"
        mock_result = _make_container_result(bad_stdout)

        async def _run():
            with patch(_RUN_CONTAINER_PATCH, new=AsyncMock(return_value=mock_result)):
                return await run_linter("python", "/tmp/repo")

        violations = asyncio.run(_run())
        self.assertEqual(violations, [])


class TestContainerConfigHardening(unittest.TestCase):
    """Container started by run_linter must use security-hardened ContainerConfig."""

    def test_container_config_hardening(self):
        mock_result = _make_container_result("[]")
        captured_configs: list[ContainerConfig] = []

        async def capturing_run_container(config: ContainerConfig) -> ContainerResult:
            captured_configs.append(config)
            return mock_result

        async def _run():
            with patch(_RUN_CONTAINER_PATCH, new=capturing_run_container):
                await run_linter("python", "/tmp/repo")

        asyncio.run(_run())

        self.assertEqual(len(captured_configs), 1, "run_container should be called once")
        cfg = captured_configs[0]

        self.assertEqual(cfg.cap_drop, ["ALL"])
        self.assertEqual(cfg.security_opt, ["no-new-privileges:true"])
        self.assertTrue(cfg.read_only)
        self.assertTrue(cfg.network_disabled)
        self.assertEqual(cfg.tmpfs, {"/tmp": "rw,size=64m"})


class TestRunLinterEmptyStdoutReturnsEmpty(unittest.TestCase):
    def test_run_linter_empty_stdout_returns_empty(self):
        mock_result = _make_container_result("")

        async def _run():
            with patch(_RUN_CONTAINER_PATCH, new=AsyncMock(return_value=mock_result)):
                return await run_linter("python", "/tmp/repo")

        violations = asyncio.run(_run())
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
