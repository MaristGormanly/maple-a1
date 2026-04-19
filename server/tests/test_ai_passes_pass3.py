"""Unit tests for ``app.services.ai_passes.run_pass3``.

Mocks ``llm.complete``; never touches a network or the real LLM
wrapper.
"""

from __future__ import annotations

import asyncio
import copy
import json
import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from app.services.ai_passes import (
    PASS3_MODEL,
    PASS3_SYSTEM_PROMPT,
    PASS3_TIMEOUT_SECONDS,
    run_pass3,
)
from app.services.ast_chunker import CodeChunk
from app.services.llm_validator import EvaluationFailedError


def _run(coro):
    return asyncio.run(coro)


def _ok_response(content: str) -> Any:
    response = MagicMock()
    response.content = content
    return response


_PASS1: dict = {
    "pass": "pass1",
    "failures": [
        {
            "test_name": "tests/test_math.py::test_add",
            "classification": "logic_bug",
            "evidence": "AssertionError: expected 5, got -1",
            "confidence": 0.9,
        }
    ],
    "summary": "Logic bug in add().",
    "needs_human_review": False,
}

_PASS2: dict = {
    "pass": "pass2",
    "skipped": False,
    "findings": [
        {
            "file_path": "src/math.py",
            "line_range": {"start": 10, "end": 10},
            "rule_reference": "PEP8:E501",
            "severity": "warning",
            "message": "Line too long.",
        }
    ],
    "retrieval_status": "ok",
}

_REASONING_BOTH: dict = {"pass1": _PASS1, "pass2": _PASS2}
_REASONING_PASS1_ONLY: dict = {"pass1": _PASS1, "pass2": {"pass": "pass2", "skipped": True, "findings": []}}

_VALID_RECOMMENDATION: dict = {
    "file_path": "src/math.py",
    "line_range": {"start": 10, "end": 14},
    "original_snippet": "def add(a, b):\n    return a - b\n",
    "revised_snippet": "def add(a, b):\n    return a + b\n",
    "diff": (
        "@@ -10,3 +10,3 @@\n def add(a, b):\n-    return a - b\n+    return a + b\n"
    ),
}

_VALID_ENVELOPE: dict = {
    "criteria_scores": [
        {
            "name": "Correctness",
            "score": 80,
            "level": "Proficient",
            "justification": "Most tests pass; one logic bug remains.",
            "confidence": 0.85,
            "recommendations": [_VALID_RECOMMENDATION],
        },
        {
            "name": "Style",
            "score": 70,
            "level": "Developing",
            "justification": "Minor PEP8 issues.",
            "confidence": 0.75,
        },
    ],
    "deterministic_score": 80.0,
    "metadata": {
        "language": {"name": "python", "version": "3.11"},
        "exit_code": 1,
    },
    "flags": [],
}


class Pass3HappyPathTests(unittest.TestCase):
    def test_returns_validated_envelope(self) -> None:
        mock_complete = AsyncMock(return_value=_ok_response(json.dumps(_VALID_ENVELOPE)))

        result = _run(
            run_pass3(
                reasoning=_REASONING_BOTH,
                rubric_content="Correctness + Style.",
                deterministic_score=80.0,
                metadata={"language": {"name": "python"}},
                code_chunks=[
                    CodeChunk(
                        file_path="src/math.py",
                        language="python",
                        kind="function",
                        name="add",
                        start_line=10,
                        end_line=12,
                        text="def add(a,b):\n    return a-b\n",
                    )
                ],
                llm_complete=mock_complete,
            )
        )

        self.assertEqual(result["criteria_scores"][0]["name"], "Correctness")
        self.assertEqual(result["deterministic_score"], 80.0)
        # Recommendation cites src/math.py which is in the evidence pool.
        self.assertEqual(len(result["criteria_scores"][0]["recommendations"]), 1)
        self.assertNotIn("LOW_CONFIDENCE", result["flags"])

    def test_call_uses_correct_model_and_timeout(self) -> None:
        mock_complete = AsyncMock(return_value=_ok_response(json.dumps(_VALID_ENVELOPE)))
        _run(
            run_pass3(
                reasoning=_REASONING_BOTH,
                rubric_content="Rubric.",
                deterministic_score=80.0,
                code_chunks=None,
                llm_complete=mock_complete,
            )
        )
        kwargs = mock_complete.await_args.kwargs
        self.assertEqual(kwargs["model"], PASS3_MODEL)
        self.assertEqual(kwargs["system_prompt"], PASS3_SYSTEM_PROMPT)
        self.assertEqual(kwargs["timeout"], PASS3_TIMEOUT_SECONDS)
        self.assertEqual(kwargs["temperature"], 0.2)

    def test_user_message_includes_both_pass_reasoning(self) -> None:
        mock_complete = AsyncMock(return_value=_ok_response(json.dumps(_VALID_ENVELOPE)))
        _run(
            run_pass3(
                reasoning=_REASONING_BOTH,
                rubric_content="Style and correctness.",
                deterministic_score=80.0,
                llm_complete=mock_complete,
            )
        )
        user_msg = mock_complete.await_args.kwargs["messages"][0]["content"]
        self.assertIn("pass1_reasoning", user_msg)
        self.assertIn("pass2_reasoning", user_msg)
        self.assertIn("Style and correctness.", user_msg)
        self.assertIn("MAPLE Standard Response Envelope", user_msg)

    def test_works_when_pass2_skipped(self) -> None:
        mock_complete = AsyncMock(return_value=_ok_response(json.dumps(_VALID_ENVELOPE)))
        result = _run(
            run_pass3(
                reasoning=_REASONING_PASS1_ONLY,
                rubric_content="Rubric.",
                deterministic_score=80.0,
                llm_complete=mock_complete,
            )
        )
        self.assertEqual(result["criteria_scores"][0]["name"], "Correctness")


# ---------------------------------------------------------------------------
# Recommendation enforcement
# ---------------------------------------------------------------------------


class Pass3RecommendationEnforcementTests(unittest.TestCase):
    def test_drops_recommendation_for_file_not_in_evidence(self) -> None:
        env = copy.deepcopy(_VALID_ENVELOPE)
        env["criteria_scores"][0]["recommendations"] = [
            {
                **_VALID_RECOMMENDATION,
                "file_path": "src/hallucinated.py",
            }
        ]
        mock_complete = AsyncMock(return_value=_ok_response(json.dumps(env)))

        result = _run(
            run_pass3(
                reasoning=_REASONING_BOTH,
                rubric_content="Rubric.",
                deterministic_score=80.0,
                code_chunks=[
                    CodeChunk(
                        file_path="src/math.py",
                        language="python",
                        kind="function",
                        name="add",
                        start_line=10,
                        end_line=12,
                        text="def add(a,b):\n    return a-b\n",
                    )
                ],
                llm_complete=mock_complete,
            )
        )

        self.assertEqual(result["criteria_scores"][0]["recommendations"], [])
        self.assertIn("LOW_CONFIDENCE", result["flags"])

    def test_drops_recommendation_with_empty_snippet(self) -> None:
        env = copy.deepcopy(_VALID_ENVELOPE)
        # The schema enforces non-empty diff but tolerates an empty snippet
        # at the JSON level.  Our enforcement layer must still reject it.
        env["criteria_scores"][0]["recommendations"] = [
            {**_VALID_RECOMMENDATION, "original_snippet": "   "}
        ]
        mock_complete = AsyncMock(return_value=_ok_response(json.dumps(env)))

        result = _run(
            run_pass3(
                reasoning=_REASONING_BOTH,
                rubric_content="Rubric.",
                deterministic_score=80.0,
                code_chunks=[
                    CodeChunk(
                        file_path="src/math.py",
                        language="python",
                        kind="function",
                        name="add",
                        start_line=10,
                        end_line=12,
                        text="def add(a,b):\n    return a-b\n",
                    )
                ],
                llm_complete=mock_complete,
            )
        )

        self.assertEqual(result["criteria_scores"][0]["recommendations"], [])
        self.assertIn("LOW_CONFIDENCE", result["flags"])

    def test_keeps_recommendation_when_evidence_present(self) -> None:
        mock_complete = AsyncMock(return_value=_ok_response(json.dumps(_VALID_ENVELOPE)))
        result = _run(
            run_pass3(
                reasoning=_REASONING_BOTH,
                rubric_content="Rubric.",
                deterministic_score=80.0,
                code_chunks=[
                    CodeChunk(
                        file_path="src/math.py",
                        language="python",
                        kind="function",
                        name="add",
                        start_line=10,
                        end_line=12,
                        text="def add(a,b):\n    return a-b\n",
                    )
                ],
                llm_complete=mock_complete,
            )
        )
        self.assertEqual(len(result["criteria_scores"][0]["recommendations"]), 1)
        self.assertNotIn("LOW_CONFIDENCE", result["flags"])


# ---------------------------------------------------------------------------
# Uncertainty flag preservation
# ---------------------------------------------------------------------------


class Pass3FlagPreservationTests(unittest.TestCase):
    def test_lifts_pass1_needs_human_review_into_envelope_flags(self) -> None:
        reasoning = copy.deepcopy(_REASONING_BOTH)
        reasoning["pass1"]["needs_human_review"] = True

        mock_complete = AsyncMock(return_value=_ok_response(json.dumps(_VALID_ENVELOPE)))
        result = _run(
            run_pass3(
                reasoning=reasoning,
                rubric_content="Rubric.",
                deterministic_score=80.0,
                code_chunks=[
                    CodeChunk(
                        file_path="src/math.py",
                        language="python",
                        kind="function",
                        name="add",
                        start_line=10,
                        end_line=12,
                        text="def add(a,b):\n    return a-b\n",
                    )
                ],
                llm_complete=mock_complete,
            )
        )
        self.assertIn("NEEDS_HUMAN_REVIEW", result["flags"])

    def test_lifts_pass2_no_match_into_envelope_flags(self) -> None:
        reasoning = copy.deepcopy(_REASONING_BOTH)
        reasoning["pass2"]["retrieval_status"] = "no_match"

        mock_complete = AsyncMock(return_value=_ok_response(json.dumps(_VALID_ENVELOPE)))
        result = _run(
            run_pass3(
                reasoning=reasoning,
                rubric_content="Rubric.",
                deterministic_score=80.0,
                code_chunks=[
                    CodeChunk(
                        file_path="src/math.py",
                        language="python",
                        kind="function",
                        name="add",
                        start_line=10,
                        end_line=12,
                        text="def add(a,b):\n    return a-b\n",
                    )
                ],
                llm_complete=mock_complete,
            )
        )
        self.assertIn("no_match", result["flags"])

    def test_lifts_per_criterion_needs_human_review_level(self) -> None:
        env = copy.deepcopy(_VALID_ENVELOPE)
        env["criteria_scores"][1]["level"] = "NEEDS_HUMAN_REVIEW"
        mock_complete = AsyncMock(return_value=_ok_response(json.dumps(env)))

        result = _run(
            run_pass3(
                reasoning=_REASONING_BOTH,
                rubric_content="Rubric.",
                deterministic_score=80.0,
                code_chunks=[
                    CodeChunk(
                        file_path="src/math.py",
                        language="python",
                        kind="function",
                        name="add",
                        start_line=10,
                        end_line=12,
                        text="def add(a,b):\n    return a-b\n",
                    )
                ],
                llm_complete=mock_complete,
            )
        )
        self.assertIn("NEEDS_HUMAN_REVIEW", result["flags"])


# ---------------------------------------------------------------------------
# Repair / failure
# ---------------------------------------------------------------------------


class Pass3RepairAndFailureTests(unittest.TestCase):
    def test_invalid_first_response_triggers_repair(self) -> None:
        mock_complete = AsyncMock(
            side_effect=[
                _ok_response("not json"),
                _ok_response(json.dumps(_VALID_ENVELOPE)),
            ]
        )
        result = _run(
            run_pass3(
                reasoning=_REASONING_BOTH,
                rubric_content="Rubric.",
                deterministic_score=80.0,
                llm_complete=mock_complete,
            )
        )
        self.assertEqual(result["deterministic_score"], 80.0)
        self.assertEqual(mock_complete.await_count, 2)

    def test_raises_evaluation_failed_when_repair_also_invalid(self) -> None:
        mock_complete = AsyncMock(
            side_effect=[_ok_response("garbage"), _ok_response("more garbage")]
        )
        with self.assertRaises(EvaluationFailedError):
            _run(
                run_pass3(
                    reasoning=_REASONING_BOTH,
                    rubric_content="Rubric.",
                    deterministic_score=80.0,
                    llm_complete=mock_complete,
                )
            )


if __name__ == "__main__":
    unittest.main()
