"""Unit tests for ``app.services.ai_passes.run_pass2``.

Covers:
  * Skip conditions (design-doc §4): no flag + no violations + no
    rubric requirement -> placeholder, no LLM call.
  * Trigger via lint path: ``enable_lint_review`` + violations.
  * Trigger via rubric path: ``rubric_requires_style``.
  * Style retriever wiring (sync + async, ``None`` fallback).
  * Schema-invalid output triggers repair retry; second failure raises.
  * Pass 1 reasoning is preserved in the returned shared object.
"""

from __future__ import annotations

import asyncio
import json
import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from app.services.ai_passes import (
    PASS2_MODEL,
    PASS2_SYSTEM_PROMPT,
    PASS2_TIMEOUT_SECONDS,
    run_pass2,
)
from app.services.ast_chunker import CodeChunk
from app.services.llm_validator import EvaluationFailedError


def _run(coro):
    return asyncio.run(coro)


_PASS1_REASONING: dict = {
    "pass": "pass1",
    "failures": [
        {
            "test_name": "tests/test_x.py::test_y",
            "classification": "logic_bug",
            "evidence": "AssertionError",
            "confidence": 0.9,
        }
    ],
    "summary": "One logic bug.",
}

_CODE_CHUNKS = [
    CodeChunk(
        file_path="src/util.py",
        language="python",
        kind="function",
        name="add",
        start_line=10,
        end_line=12,
        text="def add(a, b):\n    return a + b\n",
    ),
    CodeChunk(
        file_path="src/util.py",
        language="python",
        kind="function",
        name="mul",
        start_line=15,
        end_line=18,
        text="def mul(a, b):\n    return a * b\n",
    ),
]

_LINTER_VIOLATIONS = [
    {
        "file": "src/util.py",
        "line": 10,
        "rule": "E501",
        "message": "Line too long",
        "severity": "warning",
    }
]

_RETRIEVED_STYLE_CHUNKS = [
    {
        "source_title": "PEP 8",
        "source_url": "https://peps.python.org/pep-0008/",
        "language": "python",
        "style_guide_version": "2024-09-01",
        "rule_id": "E501",
        "chunk_text": "Limit lines to 79 characters.",
    }
]

_VALID_PASS2_OUTPUT: dict = {
    "pass": "pass2",
    "skipped": False,
    "findings": [
        {
            "file_path": "src/util.py",
            "line_range": {"start": 10, "end": 10},
            "rule_reference": "PEP8:E501",
            "severity": "warning",
            "message": "Line too long (120 > 79).",
            "style_guide_excerpt": "Limit lines to 79 characters.",
            "style_guide_source": {
                "source_title": "PEP 8",
                "style_guide_version": "2024-09-01",
                "rule_id": "E501",
            },
        }
    ],
}


def _ok_response(content: str) -> Any:
    response = MagicMock()
    response.content = content
    return response


def _llm_should_not_be_called(*_args: Any, **_kwargs: Any):
    raise AssertionError("llm.complete must not be called when Pass 2 is skipped")


def _retriever_should_not_be_called(**_kwargs: Any):
    raise AssertionError("style retriever must not be called when Pass 2 is skipped")


# ---------------------------------------------------------------------------
# Skip path
# ---------------------------------------------------------------------------


class Pass2SkipTests(unittest.TestCase):
    def test_skips_when_no_flag_no_violations_no_rubric(self) -> None:
        result = _run(
            run_pass2(
                pass1_result=_PASS1_REASONING,
                code_chunks=_CODE_CHUNKS,
                rubric_content="Test correctness only.",
                enable_lint_review=False,
                linter_violations=None,
                rubric_requires_style=False,
                language="python",
                llm_complete=_llm_should_not_be_called,
                style_retriever=_retriever_should_not_be_called,
            )
        )

        self.assertEqual(result["pass1"], _PASS1_REASONING)
        self.assertTrue(result["pass2"]["skipped"])
        self.assertEqual(result["pass2"]["findings"], [])
        self.assertEqual(result["pass2"]["pass"], "pass2")
        self.assertIn("notes", result["pass2"])

    def test_skips_when_lint_enabled_but_no_violations(self) -> None:
        result = _run(
            run_pass2(
                pass1_result=_PASS1_REASONING,
                code_chunks=_CODE_CHUNKS,
                rubric_content="Correctness.",
                enable_lint_review=True,
                linter_violations=[],
                rubric_requires_style=False,
                language="python",
                llm_complete=_llm_should_not_be_called,
                style_retriever=_retriever_should_not_be_called,
            )
        )
        self.assertTrue(result["pass2"]["skipped"])

    def test_skips_when_violations_exist_but_lint_review_disabled_and_no_rubric(
        self,
    ) -> None:
        # design-doc §4: requires (enable_lint_review AND violations) OR rubric_style
        result = _run(
            run_pass2(
                pass1_result=_PASS1_REASONING,
                code_chunks=_CODE_CHUNKS,
                rubric_content="Correctness only.",
                enable_lint_review=False,
                linter_violations=_LINTER_VIOLATIONS,
                rubric_requires_style=False,
                language="python",
                llm_complete=_llm_should_not_be_called,
                style_retriever=_retriever_should_not_be_called,
            )
        )
        self.assertTrue(result["pass2"]["skipped"])


# ---------------------------------------------------------------------------
# Trigger path — runs Pass 2
# ---------------------------------------------------------------------------


class Pass2TriggerTests(unittest.TestCase):
    def test_triggers_via_lint_path(self) -> None:
        mock_complete = AsyncMock(return_value=_ok_response(json.dumps(_VALID_PASS2_OUTPUT)))
        mock_retriever = MagicMock(return_value=_RETRIEVED_STYLE_CHUNKS)

        result = _run(
            run_pass2(
                pass1_result=_PASS1_REASONING,
                code_chunks=_CODE_CHUNKS,
                rubric_content="Style and correctness.",
                enable_lint_review=True,
                linter_violations=_LINTER_VIOLATIONS,
                rubric_requires_style=False,
                language="python",
                llm_complete=mock_complete,
                style_retriever=mock_retriever,
            )
        )

        self.assertEqual(result["pass1"], _PASS1_REASONING)
        self.assertEqual(result["pass2"]["pass"], "pass2")
        self.assertEqual(result["pass2"]["findings"][0]["rule_reference"], "PEP8:E501")
        self.assertEqual(result["pass2"]["retrieval_status"], "ok")
        mock_complete.assert_awaited_once()
        mock_retriever.assert_called_once()

    def test_triggers_via_rubric_path_without_violations(self) -> None:
        mock_complete = AsyncMock(return_value=_ok_response(json.dumps(_VALID_PASS2_OUTPUT)))
        mock_retriever = MagicMock(return_value=_RETRIEVED_STYLE_CHUNKS)

        result = _run(
            run_pass2(
                pass1_result=_PASS1_REASONING,
                code_chunks=_CODE_CHUNKS,
                rubric_content="Style required.",
                enable_lint_review=False,
                linter_violations=None,
                rubric_requires_style=True,
                language="python",
                llm_complete=mock_complete,
                style_retriever=mock_retriever,
            )
        )

        self.assertEqual(result["pass2"]["pass"], "pass2")
        mock_complete.assert_awaited_once()

    def test_call_uses_correct_model_and_timeout(self) -> None:
        mock_complete = AsyncMock(return_value=_ok_response(json.dumps(_VALID_PASS2_OUTPUT)))
        mock_retriever = MagicMock(return_value=_RETRIEVED_STYLE_CHUNKS)

        _run(
            run_pass2(
                pass1_result=_PASS1_REASONING,
                code_chunks=_CODE_CHUNKS,
                rubric_content="Style.",
                enable_lint_review=True,
                linter_violations=_LINTER_VIOLATIONS,
                language="python",
                llm_complete=mock_complete,
                style_retriever=mock_retriever,
            )
        )

        kwargs = mock_complete.await_args.kwargs
        self.assertEqual(kwargs["model"], PASS2_MODEL)
        self.assertEqual(kwargs["system_prompt"], PASS2_SYSTEM_PROMPT)
        self.assertEqual(kwargs["timeout"], PASS2_TIMEOUT_SECONDS)
        self.assertEqual(kwargs["temperature"], 0.2)

    def test_user_message_includes_chunks_violations_and_retrieved_chunks(self) -> None:
        mock_complete = AsyncMock(return_value=_ok_response(json.dumps(_VALID_PASS2_OUTPUT)))
        mock_retriever = MagicMock(return_value=_RETRIEVED_STYLE_CHUNKS)

        _run(
            run_pass2(
                pass1_result=_PASS1_REASONING,
                code_chunks=_CODE_CHUNKS,
                rubric_content="Style.",
                enable_lint_review=True,
                linter_violations=_LINTER_VIOLATIONS,
                language="python",
                llm_complete=mock_complete,
                style_retriever=mock_retriever,
            )
        )

        user_msg = mock_complete.await_args.kwargs["messages"][0]["content"]
        self.assertIn("def add(a, b)", user_msg)
        self.assertIn("def mul(a, b)", user_msg)
        self.assertIn("E501", user_msg)
        self.assertIn("Line too long", user_msg)
        self.assertIn("PEP 8", user_msg)
        self.assertIn("Limit lines to 79 characters.", user_msg)
        self.assertIn("pass1_reasoning", user_msg)


# ---------------------------------------------------------------------------
# Retriever wiring
# ---------------------------------------------------------------------------


class Pass2RetrieverTests(unittest.TestCase):
    def test_retriever_called_with_query_and_language(self) -> None:
        mock_complete = AsyncMock(return_value=_ok_response(json.dumps(_VALID_PASS2_OUTPUT)))
        mock_retriever = MagicMock(return_value=_RETRIEVED_STYLE_CHUNKS)

        _run(
            run_pass2(
                pass1_result=_PASS1_REASONING,
                code_chunks=_CODE_CHUNKS,
                rubric_content="Style.",
                enable_lint_review=True,
                linter_violations=_LINTER_VIOLATIONS,
                language="python",
                llm_complete=mock_complete,
                style_retriever=mock_retriever,
            )
        )

        retriever_kwargs = mock_retriever.call_args.kwargs
        self.assertEqual(retriever_kwargs["language"], "python")
        self.assertIn("add", retriever_kwargs["query_text"])
        self.assertIn("E501", retriever_kwargs["query_text"])

    def test_retrieval_status_no_match_when_retriever_returns_empty(self) -> None:
        mock_complete = AsyncMock(return_value=_ok_response(json.dumps(_VALID_PASS2_OUTPUT)))
        mock_retriever = MagicMock(return_value=[])

        result = _run(
            run_pass2(
                pass1_result=_PASS1_REASONING,
                code_chunks=_CODE_CHUNKS,
                rubric_content="Style.",
                enable_lint_review=True,
                linter_violations=_LINTER_VIOLATIONS,
                language="python",
                llm_complete=mock_complete,
                style_retriever=mock_retriever,
            )
        )

        self.assertEqual(result["pass2"]["retrieval_status"], "no_match")

    def test_retrieval_status_unavailable_when_no_retriever_injected(self) -> None:
        mock_complete = AsyncMock(return_value=_ok_response(json.dumps(_VALID_PASS2_OUTPUT)))

        result = _run(
            run_pass2(
                pass1_result=_PASS1_REASONING,
                code_chunks=_CODE_CHUNKS,
                rubric_content="Style.",
                enable_lint_review=True,
                linter_violations=_LINTER_VIOLATIONS,
                language="python",
                llm_complete=mock_complete,
                style_retriever=None,
            )
        )

        self.assertEqual(result["pass2"]["retrieval_status"], "unavailable")

    def test_async_retriever_is_awaited(self) -> None:
        mock_complete = AsyncMock(return_value=_ok_response(json.dumps(_VALID_PASS2_OUTPUT)))
        mock_retriever = AsyncMock(return_value=_RETRIEVED_STYLE_CHUNKS)

        result = _run(
            run_pass2(
                pass1_result=_PASS1_REASONING,
                code_chunks=_CODE_CHUNKS,
                rubric_content="Style.",
                enable_lint_review=True,
                linter_violations=_LINTER_VIOLATIONS,
                language="python",
                llm_complete=mock_complete,
                style_retriever=mock_retriever,
            )
        )

        mock_retriever.assert_awaited_once()
        self.assertEqual(result["pass2"]["retrieval_status"], "ok")


# ---------------------------------------------------------------------------
# Repair / failure
# ---------------------------------------------------------------------------


class Pass2RepairAndFailureTests(unittest.TestCase):
    def test_invalid_first_response_triggers_repair_retry(self) -> None:
        mock_complete = AsyncMock(
            side_effect=[
                _ok_response("not json"),
                _ok_response(json.dumps(_VALID_PASS2_OUTPUT)),
            ]
        )
        mock_retriever = MagicMock(return_value=_RETRIEVED_STYLE_CHUNKS)

        result = _run(
            run_pass2(
                pass1_result=_PASS1_REASONING,
                code_chunks=_CODE_CHUNKS,
                rubric_content="Style.",
                enable_lint_review=True,
                linter_violations=_LINTER_VIOLATIONS,
                language="python",
                llm_complete=mock_complete,
                style_retriever=mock_retriever,
            )
        )

        self.assertEqual(result["pass2"]["pass"], "pass2")
        self.assertEqual(mock_complete.await_count, 2)

    def test_raises_evaluation_failed_when_repair_also_invalid(self) -> None:
        mock_complete = AsyncMock(
            side_effect=[_ok_response("garbage"), _ok_response("still garbage")]
        )
        mock_retriever = MagicMock(return_value=_RETRIEVED_STYLE_CHUNKS)

        with self.assertRaises(EvaluationFailedError):
            _run(
                run_pass2(
                    pass1_result=_PASS1_REASONING,
                    code_chunks=_CODE_CHUNKS,
                    rubric_content="Style.",
                    enable_lint_review=True,
                    linter_violations=_LINTER_VIOLATIONS,
                    language="python",
                    llm_complete=mock_complete,
                    style_retriever=mock_retriever,
                )
            )


if __name__ == "__main__":
    unittest.main()
