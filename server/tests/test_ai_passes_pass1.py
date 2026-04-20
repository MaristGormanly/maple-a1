"""Unit tests for ``app.services.ai_passes.run_pass1``.

Exercises happy path, prompt construction, repair retry path, and
schema-validation failure with a mocked ``llm.complete``.
"""

from __future__ import annotations

import asyncio
import json
import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from app.services.ai_passes import (
    PASS1_MODEL,
    PASS1_SYSTEM_PROMPT,
    PASS1_TIMEOUT_SECONDS,
    run_pass1,
)
from app.services.llm_validator import EvaluationFailedError


def _run(coro):
    return asyncio.run(coro)


_PARSED_TEST_RESULTS: dict = {
    "framework": "pytest",
    "passed": 3,
    "failed": 2,
    "errors": 0,
    "skipped": 0,
    "tests": [
        {"name": "tests/test_math.py::test_add", "status": "passed", "message": None},
        {"name": "tests/test_math.py::test_div_by_zero", "status": "failed",
         "message": "ZeroDivisionError"},
        {"name": "tests/test_io.py::test_read_csv", "status": "failed",
         "message": "FileNotFoundError: data.csv"},
    ],
    "resource_constraint_metadata": None,
    "raw_output_truncated": False,
}

_RUBRIC_CONTENT: str = (
    "Criterion 1: Arithmetic correctness — handle division by zero gracefully.\n"
    "Criterion 2: File IO — read fixture data without crashing."
)

_VALID_PASS1_OUTPUT: dict = {
    "pass": "pass1",
    "failures": [
        {
            "test_name": "tests/test_math.py::test_div_by_zero",
            "classification": "logic_bug",
            "rubric_criterion": "Criterion 1",
            "evidence": "ZeroDivisionError",
            "confidence": 0.9,
        },
        {
            "test_name": "tests/test_io.py::test_read_csv",
            "classification": "environment",
            "rubric_criterion": "Criterion 2",
            "evidence": "FileNotFoundError",
            "confidence": 0.65,
        },
    ],
    "summary": "1 logic bug + 1 environment issue.",
    "needs_human_review": False,
}


def _ok_response(content: str) -> Any:
    """Mock LLMResponse-like object returned by llm.complete."""
    response = MagicMock()
    response.content = content
    return response


class RunPass1HappyPathTests(unittest.TestCase):
    def test_returns_validated_dict_on_success(self) -> None:
        mock_complete = AsyncMock(return_value=_ok_response(json.dumps(_VALID_PASS1_OUTPUT)))

        result = _run(
            run_pass1(
                parsed_test_results=_PARSED_TEST_RESULTS,
                rubric_content=_RUBRIC_CONTENT,
                exit_code=1,
                llm_complete=mock_complete,
            )
        )

        self.assertEqual(result, _VALID_PASS1_OUTPUT)
        mock_complete.assert_awaited_once()

    def test_call_uses_correct_model_and_prompt(self) -> None:
        mock_complete = AsyncMock(return_value=_ok_response(json.dumps(_VALID_PASS1_OUTPUT)))

        _run(
            run_pass1(
                parsed_test_results=_PARSED_TEST_RESULTS,
                rubric_content=_RUBRIC_CONTENT,
                exit_code=1,
                llm_complete=mock_complete,
            )
        )

        kwargs = mock_complete.await_args.kwargs
        self.assertEqual(kwargs["model"], PASS1_MODEL)
        self.assertEqual(kwargs["system_prompt"], PASS1_SYSTEM_PROMPT)
        self.assertEqual(kwargs["timeout"], PASS1_TIMEOUT_SECONDS)
        self.assertEqual(kwargs["temperature"], 0.2)
        self.assertEqual(len(kwargs["messages"]), 1)
        self.assertEqual(kwargs["messages"][0]["role"], "user")

    def test_user_message_includes_rubric_and_test_evidence(self) -> None:
        mock_complete = AsyncMock(return_value=_ok_response(json.dumps(_VALID_PASS1_OUTPUT)))

        _run(
            run_pass1(
                parsed_test_results=_PARSED_TEST_RESULTS,
                rubric_content=_RUBRIC_CONTENT,
                exit_code=1,
                resource_constraint_metadata={"exit_code": 137, "oom_killed": True},
                llm_complete=mock_complete,
            )
        )

        user_msg = mock_complete.await_args.kwargs["messages"][0]["content"]
        self.assertIn("Criterion 1", user_msg)
        self.assertIn("test_div_by_zero", user_msg)
        self.assertIn("FileNotFoundError", user_msg)
        self.assertIn("oom_killed", user_msg)
        self.assertIn("logic_bug", user_msg)

    def test_redaction_strips_github_pat_from_user_message(self) -> None:
        mock_complete = AsyncMock(return_value=_ok_response(json.dumps(_VALID_PASS1_OUTPUT)))
        leaky_results = dict(_PARSED_TEST_RESULTS)
        leaky_results["tests"] = [
            {
                "name": "tests/test_secret.py::test_token",
                "status": "failed",
                "message": "Token: ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            }
        ]

        _run(
            run_pass1(
                parsed_test_results=leaky_results,
                rubric_content=_RUBRIC_CONTENT,
                exit_code=1,
                llm_complete=mock_complete,
            )
        )

        user_msg = mock_complete.await_args.kwargs["messages"][0]["content"]
        self.assertNotIn("ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", user_msg)
        self.assertIn("[REDACTED_GITHUB_PAT]", user_msg)

    def test_accepts_plain_string_response(self) -> None:
        mock_complete = AsyncMock(return_value=json.dumps(_VALID_PASS1_OUTPUT))
        result = _run(
            run_pass1(
                parsed_test_results=_PARSED_TEST_RESULTS,
                rubric_content=_RUBRIC_CONTENT,
                exit_code=0,
                llm_complete=mock_complete,
            )
        )
        self.assertEqual(result, _VALID_PASS1_OUTPUT)


class RunPass1RepairPathTests(unittest.TestCase):
    def test_invalid_first_response_triggers_one_repair_call(self) -> None:
        mock_complete = AsyncMock(
            side_effect=[
                _ok_response("not json at all"),
                _ok_response(json.dumps(_VALID_PASS1_OUTPUT)),
            ]
        )

        result = _run(
            run_pass1(
                parsed_test_results=_PARSED_TEST_RESULTS,
                rubric_content=_RUBRIC_CONTENT,
                exit_code=1,
                llm_complete=mock_complete,
            )
        )

        self.assertEqual(result, _VALID_PASS1_OUTPUT)
        self.assertEqual(mock_complete.await_count, 2)
        repair_user_msg = mock_complete.await_args_list[1].kwargs["messages"][0]["content"]
        self.assertIn("Pass 1", repair_user_msg)
        self.assertIn("not json at all", repair_user_msg)


class RunPass1FailureTests(unittest.TestCase):
    def test_raises_evaluation_failed_when_repair_also_invalid(self) -> None:
        mock_complete = AsyncMock(
            side_effect=[
                _ok_response("garbage one"),
                _ok_response("garbage two"),
            ]
        )

        with self.assertRaises(EvaluationFailedError):
            _run(
                run_pass1(
                    parsed_test_results=_PARSED_TEST_RESULTS,
                    rubric_content=_RUBRIC_CONTENT,
                    exit_code=1,
                    llm_complete=mock_complete,
                )
            )

        self.assertEqual(mock_complete.await_count, 2)

    def test_raises_when_classification_invalid_after_repair(self) -> None:
        bad_output = json.dumps(
            {
                "pass": "pass1",
                "failures": [
                    {"test_name": "x", "classification": "cosmic_rays"},
                ],
                "summary": "bad",
            }
        )
        mock_complete = AsyncMock(
            side_effect=[_ok_response(bad_output), _ok_response(bad_output)]
        )

        with self.assertRaises(EvaluationFailedError) as ctx:
            _run(
                run_pass1(
                    parsed_test_results=_PARSED_TEST_RESULTS,
                    rubric_content=_RUBRIC_CONTENT,
                    exit_code=1,
                    llm_complete=mock_complete,
                )
            )

        self.assertIn(
            "classification",
            " ".join(ctx.exception.validation_errors),
        )


if __name__ == "__main__":
    unittest.main()
