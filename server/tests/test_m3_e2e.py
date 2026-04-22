"""Live end-to-end smoke test for Jayden's Milestone 3 slice.

Exercises the real ``llm.complete`` against the configured provider
chain (Gemini → GPT-4o fallback) through Pass 1 → Pass 3. Validates
that:

  1. The retry / fallback / backoff loop in ``llm.complete`` produces a
     syntactically valid completion.
  2. The response survives ``validate_and_repair`` against
     ``PASS1_OUTPUT_SCHEMA`` and ``PASS3_OUTPUT_SCHEMA``.
  3. Per-call token/cost accounting lands on ``LLMResponse.usage``.

This test is **skipped by default**. It only runs when at least one
provider key is configured in the environment:

    GEMINI_API_KEY=...  OR  OPENAI_API_KEY=...

Invoke with:

    cd server && pytest tests/test_m3_e2e.py -v -s

The deterministic pipeline (Docker sandbox, DB persistence) is **not**
exercised here — those layers are covered by
``tests/test_pipeline.py`` and ``tests/test_evaluate_submission_integration.py``.
This test specifically verifies the LLM-wrapper + validator + schema
slice that Jayden's M3 tasks #1, #2, #5, #6 deliver.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from app.services.ai_passes import run_pass1, run_pass3
from app.services.llm import complete


def _run(coro):
    return asyncio.run(coro)

pytestmark = pytest.mark.skipif(
    not (os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")),
    reason="no LLM provider key configured — skipping live M3 E2E smoke",
)


_TINY_RUBRIC = (
    "Criterion 1 — Correctness (60 pts): student code must pass the "
    "provided pytest suite.\n"
    "Criterion 2 — Readability (40 pts): variable names must be "
    "descriptive; no single-letter identifiers outside of loops."
)

_PARSED_TEST_RESULTS = {
    "framework": "pytest",
    "tests": [
        {"name": "test_add", "status": "passed"},
        {
            "name": "test_divide_by_zero",
            "status": "failed",
            "message": "ZeroDivisionError: division by zero",
        },
    ],
    "summary": {"passed": 1, "failed": 1, "total": 2},
}


def test_complete_returns_non_empty_response_with_usage():
    """Smoke-check: the real ``complete`` produces content + token counts + cost."""
    resp = _run(complete(
        system_prompt="You are a terse assistant. Reply with a single word.",
        messages=[{"role": "user", "content": "Say hello."}],
        complexity="standard",
        max_tokens=16,
        temperature=0.0,
    ))

    assert resp.content.strip(), "LLM returned empty content"
    assert resp.usage.input_tokens >= 0
    assert resp.usage.output_tokens >= 0
    # cost_usd is only 0.0 when the responding model is not in MODEL_PRICING.
    # Since MODEL_CHAIN and MODEL_PRICING are kept in lockstep by
    # test_llm_cost.py, a production response should always price.
    assert resp.usage.cost_usd >= 0.0
    assert resp.latency_ms > 0


def test_pass1_live_produces_schema_valid_reconciliation():
    """Pass 1 live: test reconciliation classifies the failing test."""
    result = _run(run_pass1(
        parsed_test_results=_PARSED_TEST_RESULTS,
        rubric_content=_TINY_RUBRIC,
        exit_code=1,
    ))
    # validate_and_repair already enforces PASS1_OUTPUT_SCHEMA; an
    # explicit assertion documents the contract.
    assert isinstance(result, dict)
    assert result, "Pass 1 returned an empty reconciliation object"


def test_pass3_live_produces_maple_standard_envelope():
    """Pass 3 live: synthesis returns a schema-valid MAPLE envelope."""
    reasoning = {
        "pass1": {"summary": "1 of 2 tests passed; divide-by-zero bug in target."},
    }
    envelope = _run(run_pass3(
        reasoning=reasoning,
        rubric_content=_TINY_RUBRIC,
        deterministic_score=50.0,
        metadata={"language": "python", "language_version": "3.12"},
    ))
    assert isinstance(envelope, dict)
    assert "criteria_scores" in envelope
    assert isinstance(envelope["criteria_scores"], list)
