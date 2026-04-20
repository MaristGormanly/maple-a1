"""Unit tests for ``app.services.llm_validator.validate_and_repair``.

Exercises the success path (no repair needed), the repair-success path,
and both flavours of failure that must raise ``EvaluationFailedError``:
unrecoverable parse failure and unrecoverable schema failure after one
retry.
"""

from __future__ import annotations

import asyncio
import json
import unittest

from app.services.llm_schemas import PASS1_OUTPUT_SCHEMA
from app.services.llm_validator import (
    EvaluationFailedError,
    validate_and_repair,
)


def _run(coro):
    return asyncio.run(coro)


# A canonical, schema-valid Pass 1 instance reused across success cases.
_VALID_PASS1: dict = {
    "pass": "pass1",
    "failures": [
        {
            "test_name": "tests/test_math.py::test_add",
            "classification": "logic_bug",
            "evidence": "AssertionError",
            "confidence": 0.9,
        }
    ],
    "summary": "One logic bug detected.",
}

_VALID_PASS1_JSON: str = json.dumps(_VALID_PASS1)


class _RecordingLLM:
    """Mock ``llm_complete_fn`` that records the prompt it received."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.response


class _AsyncRecordingLLM:
    """Async variant of the recording mock — covers the awaitable path."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[str] = []

    async def __call__(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.response


def _failing_llm_should_not_be_called(_: str) -> str:
    raise AssertionError("llm_complete_fn must not be invoked when the first parse succeeds")


class ValidateAndRepairSuccessTests(unittest.TestCase):
    def test_valid_first_output_returns_instance_without_calling_llm(self) -> None:
        result = _run(
            validate_and_repair(
                _VALID_PASS1_JSON,
                PASS1_OUTPUT_SCHEMA,
                _failing_llm_should_not_be_called,
                repair_prompt="Fix it.",
            )
        )
        self.assertEqual(result, _VALID_PASS1)


class ValidateAndRepairRepairPathTests(unittest.TestCase):
    def test_repair_succeeds_when_llm_returns_valid_json(self) -> None:
        broken = "this is not json"
        mock_llm = _RecordingLLM(response=_VALID_PASS1_JSON)

        result = _run(
            validate_and_repair(
                broken,
                PASS1_OUTPUT_SCHEMA,
                mock_llm,
                repair_prompt="REPAIR_INSTRUCTIONS",
            )
        )

        self.assertEqual(result, _VALID_PASS1)
        self.assertEqual(len(mock_llm.calls), 1, "LLM must be called exactly once for repair")
        prompt = mock_llm.calls[0]
        self.assertIn("REPAIR_INSTRUCTIONS", prompt)
        self.assertIn("Validation errors", prompt)
        self.assertIn(broken, prompt)

    def test_repair_succeeds_for_schema_violation_first_attempt(self) -> None:
        invalid_instance = {
            "pass": "pass1",
            "failures": [
                {
                    "test_name": "tests/test_math.py::test_add",
                    "classification": "cosmic_rays",
                }
            ],
            "summary": "bad",
        }
        mock_llm = _RecordingLLM(response=_VALID_PASS1_JSON)

        result = _run(
            validate_and_repair(
                json.dumps(invalid_instance),
                PASS1_OUTPUT_SCHEMA,
                mock_llm,
                repair_prompt="Fix.",
            )
        )

        self.assertEqual(result, _VALID_PASS1)
        self.assertEqual(len(mock_llm.calls), 1)
        self.assertIn("classification", mock_llm.calls[0])

    def test_async_llm_complete_fn_is_awaited(self) -> None:
        mock_llm = _AsyncRecordingLLM(response=_VALID_PASS1_JSON)
        result = _run(
            validate_and_repair(
                "{not json",
                PASS1_OUTPUT_SCHEMA,
                mock_llm,
                repair_prompt="Fix.",
            )
        )
        self.assertEqual(result, _VALID_PASS1)
        self.assertEqual(len(mock_llm.calls), 1)


class ValidateAndRepairFailureTests(unittest.TestCase):
    def test_raises_when_repair_output_still_unparseable(self) -> None:
        mock_llm = _RecordingLLM(response="still not json")

        with self.assertRaises(EvaluationFailedError) as ctx:
            _run(
                validate_and_repair(
                    "first attempt also bad",
                    PASS1_OUTPUT_SCHEMA,
                    mock_llm,
                    repair_prompt="Fix.",
                )
            )

        err = ctx.exception
        self.assertEqual(err.original_output, "first attempt also bad")
        self.assertEqual(err.repair_output, "still not json")
        self.assertTrue(err.validation_errors)
        self.assertEqual(len(mock_llm.calls), 1, "LLM must only be called once for repair")

    def test_raises_when_repair_output_still_schema_invalid(self) -> None:
        invalid_repair = json.dumps(
            {
                "pass": "pass1",
                "failures": [],
            }
        )
        mock_llm = _RecordingLLM(response=invalid_repair)

        with self.assertRaises(EvaluationFailedError) as ctx:
            _run(
                validate_and_repair(
                    "{}",
                    PASS1_OUTPUT_SCHEMA,
                    mock_llm,
                    repair_prompt="Fix.",
                )
            )

        err = ctx.exception
        self.assertIn("summary", " ".join(err.validation_errors))
        self.assertEqual(err.repair_output, invalid_repair)

    def test_raises_when_llm_returns_non_string(self) -> None:
        def bad_llm(_: str):
            return {"not": "a string"}

        with self.assertRaises(EvaluationFailedError):
            _run(
                validate_and_repair(
                    "not json",
                    PASS1_OUTPUT_SCHEMA,
                    bad_llm,
                    repair_prompt="Fix.",
                )
            )


if __name__ == "__main__":
    unittest.main()
