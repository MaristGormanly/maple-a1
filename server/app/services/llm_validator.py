"""JSON-schema validation and one-shot repair for LLM outputs.

Milestone 3 — Dom's "Schema-validated outputs with one repair retry"
task.  Each AI pass returns a JSON string that must conform to the
corresponding schema in :mod:`app.services.llm_schemas`.  This module
provides :func:`validate_and_repair`, which:

1.  Parses ``raw_json`` and validates it against ``schema``.
2.  On parse or schema failure, invokes the injected ``llm_complete_fn``
    *once* with a repair prompt that includes the original raw output
    and the validation error messages.
3.  Re-parses and re-validates the repair output.  If that also fails,
    raises :class:`EvaluationFailedError` so the orchestrator can mark
    the submission ``EVALUATION_FAILED`` for human review (design-doc
    §4: "If the second output is still invalid, the submission is
    marked ``EVALUATION_FAILED`` for human review.").

The injected ``llm_complete_fn`` is intentionally minimal —
``(prompt: str) -> str | Awaitable[str]`` — so the real
``app.services.llm.complete`` (which has a different signature and
returns an :class:`LLMResponse`) can be adapted at the call site
without modifying ``llm.py``.
"""

from __future__ import annotations

import inspect
import json
import logging
from typing import Any, Awaitable, Callable, Union

from jsonschema import Draft202012Validator, ValidationError

logger = logging.getLogger(__name__)


# Either a sync or async callable that takes a single prompt string and
# returns the LLM's raw text content.
LLMCompleteFn = Callable[[str], Union[str, Awaitable[str]]]


class EvaluationFailedError(Exception):
    """Raised when LLM output cannot be coerced into a valid JSON
    instance even after one repair retry.

    The orchestrator should catch this, mark the submission as
    ``EVALUATION_FAILED``, and surface it for human review.
    """

    def __init__(
        self,
        message: str,
        *,
        original_output: str | None = None,
        repair_output: str | None = None,
        validation_errors: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.original_output = original_output
        self.repair_output = repair_output
        self.validation_errors = validation_errors or []


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_and_validate(
    raw_json: str, validator: Draft202012Validator
) -> tuple[dict | None, list[str]]:
    """Parse ``raw_json`` and validate against ``validator``.

    Returns ``(instance, [])`` on success or ``(None, [error, ...])`` on
    any failure (parse error or schema violations).
    """
    try:
        instance = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        return None, [f"JSON parse error: {exc.msg} (line {exc.lineno}, col {exc.colno})"]

    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    if errors:
        formatted = [_format_validation_error(e) for e in errors]
        return None, formatted

    return instance, []


def _format_validation_error(err: ValidationError) -> str:
    path = "$" + "".join(
        f"[{p}]" if isinstance(p, int) else f".{p}" for p in err.absolute_path
    )
    return f"{path}: {err.message}"


def _build_repair_prompt(
    repair_prompt: str, raw_output: str, validation_errors: list[str]
) -> str:
    """Compose the prompt sent to the LLM for the single repair retry."""
    error_block = "\n".join(f"- {e}" for e in validation_errors)
    return (
        f"{repair_prompt}\n\n"
        f"Validation errors from previous output:\n{error_block}\n\n"
        f"Previous output (raw):\n{raw_output}\n\n"
        "Return only valid JSON conforming to the schema."
    )


async def _call_llm(llm_complete_fn: LLMCompleteFn, prompt: str) -> str:
    """Invoke ``llm_complete_fn`` and await it if it is a coroutine."""
    result = llm_complete_fn(prompt)
    if inspect.isawaitable(result):
        result = await result
    if not isinstance(result, str):
        raise EvaluationFailedError(
            "Repair LLM call did not return a string",
            repair_output=repr(result),
        )
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def validate_and_repair(
    raw_json: str,
    schema: dict,
    llm_complete_fn: LLMCompleteFn,
    repair_prompt: str,
) -> dict[str, Any]:
    """Validate ``raw_json`` against ``schema`` with one repair retry.

    Args:
        raw_json: The raw text returned by an LLM call.
        schema: A JSON Schema dict (typically from
            :mod:`app.services.llm_schemas`).
        llm_complete_fn: Injected callable used for the single repair
            attempt.  Accepts a prompt string and returns (or awaits to)
            the LLM's raw text content.
        repair_prompt: Pass-specific instructions prepended to the
            repair prompt (e.g. the Pass 1 system prompt).

    Returns:
        The parsed, schema-valid JSON instance as a ``dict``.

    Raises:
        EvaluationFailedError: If the original output and the repair
            output both fail to parse or validate.
    """
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    instance, first_errors = _parse_and_validate(raw_json, validator)
    if instance is not None:
        return instance

    logger.warning(
        "validate_and_repair: initial output invalid (%d error(s)); attempting one repair retry",
        len(first_errors),
    )

    composed_prompt = _build_repair_prompt(repair_prompt, raw_json, first_errors)
    repair_output = await _call_llm(llm_complete_fn, composed_prompt)

    repaired_instance, repair_errors = _parse_and_validate(repair_output, validator)
    if repaired_instance is not None:
        logger.info("validate_and_repair: repair retry succeeded")
        return repaired_instance

    logger.error(
        "validate_and_repair: repair retry failed with %d error(s)", len(repair_errors)
    )
    raise EvaluationFailedError(
        "LLM output failed schema validation after one repair retry",
        original_output=raw_json,
        repair_output=repair_output,
        validation_errors=repair_errors,
    )


__all__ = [
    "EvaluationFailedError",
    "LLMCompleteFn",
    "validate_and_repair",
]
