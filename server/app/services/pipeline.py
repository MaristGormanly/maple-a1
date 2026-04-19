"""Submission evaluation pipeline.

Milestone 2 (Sylvie + Dom) wires the deterministic phase: clone the
test suite, run the student container, parse results, score, and
persist the EvaluationResult row.

Milestone 3 (Dom) extends the pipeline with an ``Evaluating`` phase
that runs the three-pass LLM evaluation:

    Pass 1  →  conditional Pass 2  →  Pass 3

The AI phase is opt-in at runtime: when Jayden's ``llm.complete``
is still the M1/M2 stub (``raise NotImplementedError``), the
phase is skipped and the submission stays at ``Completed``.  This
keeps the deterministic flow operational while the LLM
infrastructure is being built.

Boundaries
----------
* This module **does not modify** Jayden's ``llm.py``,
  ``rag_retriever``, or linter implementation files.  Each Jayden
  hook is imported lazily; if the import fails the pipeline
  proceeds with safe defaults (``None`` / empty list) and logs
  the degradation.
* Persistence helpers live in :mod:`app.services.submissions`
  (``persist_evaluation_result`` for the M2 row, and
  ``update_evaluation_result`` for the M3 ``ai_feedback_json``
  merge-update).
"""

from __future__ import annotations

import inspect
import logging
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from ..models.database import async_session_maker
from . import llm
from .ai_passes import run_pass1, run_pass2, run_pass3
from .assignments import get_assignment_by_id
from .ast_chunker import CodeChunk, extract_chunks
from .docker_client import run_container
from .language_detector import detect_language_version
from .llm_validator import EvaluationFailedError
from .review_flags import compute_review_flags, determine_terminal_status
from .scoring import calculate_deterministic_score
from .submissions import (
    DuplicateEvaluationError,
    persist_evaluation_result,
    update_evaluation_result,
    update_submission_status,
)
from .test_parser import parse_test_results

logger = logging.getLogger(__name__)

_CONTAINER_TIMEOUT_SECONDS = 30

# --- Optional Jayden hooks (lazy imports, safe defaults) -------------------
#
# These modules are owned by Jayden and may not exist yet.  We import
# defensively so Dom's pipeline can run end-to-end with stubbed/missing
# infrastructure.  Once Jayden lands the real implementations the
# imports succeed automatically and the AI phase activates.
try:  # pragma: no cover -- import guard
    from .rag_retriever import retrieve_style_chunks as _retrieve_style_chunks  # type: ignore
except Exception:  # pragma: no cover -- import guard
    _retrieve_style_chunks = None  # type: ignore[assignment]

try:  # pragma: no cover -- import guard
    from .linter import run_linters as _run_linters  # type: ignore
except Exception:  # pragma: no cover -- import guard
    _run_linters = None  # type: ignore[assignment]


# Cap chunker walks to avoid pathological repos exhausting the Pass 2
# context window.  Tuned to be generous for typical M3 student repos.
_MAX_CHUNKS_PER_REPO: int = 200

# File extensions per language for the AST chunker repo walk.
_LANGUAGE_EXTENSIONS: dict[str, tuple[str, ...]] = {
    "python": (".py",),
    "javascript": (".js", ".jsx", ".mjs", ".cjs"),
    "typescript": (".ts", ".tsx"),
    "java": (".java",),
}


# ---------------------------------------------------------------------------
# LLM-readiness probe
# ---------------------------------------------------------------------------

def _is_llm_ready() -> bool:
    """Return True iff Jayden's ``llm.complete`` looks operational.

    The Milestone 1 stub unconditionally raises ``NotImplementedError``.
    We detect that pattern via source inspection so the pipeline can
    gracefully short-circuit the AI phase without performing a real
    completion call (which would cost tokens or fail with a confusing
    error).  Once Jayden's implementation lands, the source no longer
    matches and the AI phase activates automatically.
    """
    try:
        src = inspect.getsource(llm.complete)
    except (TypeError, OSError):
        # Source unavailable (e.g. C-implemented) — assume ready and
        # let any real failure surface during the actual call.
        return True
    return "raise NotImplementedError" not in src


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

async def run_pipeline(
    submission_id: uuid.UUID,
    assignment_id: uuid.UUID | None,
    student_repo_path: str,
    rubric_content: object,
    github_pat: str,
) -> None:
    if assignment_id is None:
        return

    test_suite_dir: Path | None = None
    try:
        async with async_session_maker() as db:
            if await update_submission_status(db, submission_id, "Testing") is None:
                logger.warning("run_pipeline: submission %s not found", submission_id)
                return
            assignment = await get_assignment_by_id(db, assignment_id)
            if assignment is None:
                await update_submission_status(db, submission_id, "Failed")
                return
            suite_url = (assignment.test_suite_repo_url or "").strip()
            if not suite_url:
                await update_submission_status(db, submission_id, "Failed")
                return
            language_override = assignment.language_override
            enable_lint_review = bool(assignment.enable_lint_review)

        test_suite_dir = Path(tempfile.mkdtemp(prefix="maple-testsuite-"))
        from .. import main as app_main

        await app_main.clone_repository(suite_url, test_suite_dir, github_pat)

        lang = detect_language_version(student_repo_path, language_override)
        language = lang.get("language", "")
        container = await run_container(
            language,
            student_repo_path,
            str(test_suite_dir.resolve()),
            timeout_seconds=_CONTAINER_TIMEOUT_SECONDS,
        )

        parsed = parse_test_results(container.stdout, container.stderr, container.exit_code)
        score = calculate_deterministic_score(parsed, rubric_content)

        metadata_json: dict[str, Any] = {
            "language": lang,
            "exit_code": container.exit_code,
            "resource_constraint_metadata": parsed.get("resource_constraint_metadata"),
            "test_summary": {
                "framework": parsed.get("framework", "unknown"),
                "passed": parsed.get("passed", 0),
                "failed": parsed.get("failed", 0),
                "errors": parsed.get("errors", 0),
                "skipped": parsed.get("skipped", 0),
            },
        }

        async with async_session_maker() as db:
            await persist_evaluation_result(
                db,
                submission_id=submission_id,
                deterministic_score=score,
                metadata_json=metadata_json,
            )
            await update_submission_status(db, submission_id, "Completed")

        # ---------------- Milestone 3: Evaluating phase ----------------
        # Runs only when Jayden's LLM wrapper is operational.  Any
        # LLM/schema failure is handled inline (mapped to
        # EVALUATION_FAILED) so it does NOT cascade into the outer
        # generic-Failed branch below.
        if _is_llm_ready():
            await _run_evaluating_phase(
                submission_id=submission_id,
                student_repo_path=student_repo_path,
                rubric_content=rubric_content,
                language=language,
                enable_lint_review=enable_lint_review,
                parsed=parsed,
                container_exit_code=container.exit_code,
                deterministic_score=score,
                metadata_json=metadata_json,
            )
        else:
            logger.info(
                "run_pipeline: skipping AI phase for submission %s — "
                "llm.complete is still the M1 stub",
                submission_id,
            )
    except DuplicateEvaluationError:
        logger.info(
            "run_pipeline: duplicate evaluation for submission %s — "
            "keeping existing result and Completed status",
            submission_id,
        )
    except Exception:
        logger.exception("run_pipeline failed for submission %s", submission_id)
        try:
            async with async_session_maker() as db:
                await update_submission_status(db, submission_id, "Failed")
        except Exception:
            logger.exception(
                "run_pipeline: could not mark submission %s Failed", submission_id
            )
    finally:
        if test_suite_dir is not None and test_suite_dir.exists():
            shutil.rmtree(test_suite_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Milestone 3 — Evaluating phase
# ---------------------------------------------------------------------------

async def _run_evaluating_phase(
    *,
    submission_id: uuid.UUID,
    student_repo_path: str,
    rubric_content: object,
    language: str,
    enable_lint_review: bool,
    parsed: dict,
    container_exit_code: int | None,
    deterministic_score: float | None,
    metadata_json: dict[str, Any],
) -> None:
    """Run Pass 1 → conditional Pass 2 → Pass 3 and persist the result.

    Exception handling is **broadened** here: schema-validation /
    repair failures (``EvaluationFailedError``) map to the explicit
    ``EVALUATION_FAILED`` terminal status rather than falling through
    to the generic ``Failed`` branch in :func:`run_pipeline`.

    Any other unexpected error logs and re-raises so the outer
    pipeline can decide on terminal status (currently ``Failed``).
    """
    rubric_text = _stringify_rubric(rubric_content)
    rubric_requires_style = _rubric_requires_style(rubric_content)

    # Linter results — Jayden's hook.  When unavailable, we pass
    # ``None`` so Pass 2's skip-logic can still fire correctly.
    linter_violations: list[dict] | None = None
    if _run_linters is not None:
        try:
            linter_violations = await _maybe_await(
                _run_linters(student_repo_path, language=language)
            )
        except Exception:
            logger.exception(
                "run_pipeline: linter hook raised; continuing with no violations"
            )
            linter_violations = None
    else:
        logger.info(
            "run_pipeline: linter hook not importable — passing None to Pass 2"
        )

    code_chunks = _collect_code_chunks_from_repo(student_repo_path, language)

    async with async_session_maker() as db:
        await update_submission_status(db, submission_id, "Evaluating")

    try:
        pass1 = await run_pass1(
            parsed_test_results=parsed,
            rubric_content=rubric_text,
            exit_code=container_exit_code,
            resource_constraint_metadata=parsed.get("resource_constraint_metadata"),
        )

        reasoning = await run_pass2(
            pass1_result=pass1,
            code_chunks=code_chunks,
            rubric_content=rubric_text,
            enable_lint_review=enable_lint_review,
            linter_violations=linter_violations,
            rubric_requires_style=rubric_requires_style,
            language=language,
            style_retriever=_retrieve_style_chunks,
        )

        envelope = await run_pass3(
            reasoning=reasoning,
            rubric_content=rubric_text,
            deterministic_score=deterministic_score,
            metadata=metadata_json,
            code_chunks=code_chunks,
        )
    except EvaluationFailedError as exc:
        logger.error(
            "run_pipeline: AI passes failed schema validation for submission %s "
            "after one repair retry; marking EVALUATION_FAILED. errors=%s",
            submission_id,
            getattr(exc, "validation_errors", None),
        )
        try:
            async with async_session_maker() as db:
                await update_submission_status(
                    db, submission_id, "EVALUATION_FAILED"
                )
        except Exception:
            logger.exception(
                "run_pipeline: could not mark submission %s EVALUATION_FAILED",
                submission_id,
            )
        return

    # ------------------------------------------------------------------
    # Augment metadata with style_guide_version when RAG provided one.
    # Per design-doc §3 §II, every retrieved style chunk carries a
    # ``style_guide_version`` propagated through Pass 2 findings.
    # ------------------------------------------------------------------
    style_guide_versions = _extract_style_guide_versions(reasoning)
    if style_guide_versions:
        # Single version → string; multiple → list (schema accepts both).
        version_value: str | list[str] = (
            style_guide_versions[0]
            if len(style_guide_versions) == 1
            else style_guide_versions
        )
        metadata_json["style_guide_version"] = version_value
        envelope_meta = envelope.setdefault("metadata", {})
        envelope_meta["style_guide_version"] = version_value

    # Apply NEEDS_HUMAN_REVIEW / status rules.
    pass2_block = reasoning.get("pass2") or {}
    retrieval_status = pass2_block.get("retrieval_status")
    flags, awaiting_review = compute_review_flags(
        envelope,
        retrieval_status=retrieval_status,
        language=language,
    )
    envelope["flags"] = flags

    terminal_status = determine_terminal_status(awaiting_review)

    try:
        async with async_session_maker() as db:
            await update_evaluation_result(
                db,
                submission_id=submission_id,
                ai_feedback_json=envelope,
                metadata_json=metadata_json,
            )
            await update_submission_status(db, submission_id, terminal_status)
    except Exception:
        # Persistence error after a successful AI run — log and bubble
        # so the outer except can decide.  We deliberately do NOT mark
        # EVALUATION_FAILED here: schema validation succeeded, the LLM
        # output is valid; the failure is in the DB layer.
        logger.exception(
            "run_pipeline: failed to persist AI feedback for submission %s",
            submission_id,
        )
        raise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _maybe_await(value: Any) -> Any:
    """Await *value* if it is a coroutine; otherwise return as-is.

    Lets the linter / RAG hooks be either sync or async without
    forcing Jayden into one shape.
    """
    if inspect.isawaitable(value):
        return await value
    return value


def _stringify_rubric(rubric_content: object) -> str:
    """Coerce the rubric payload to a string for prompt embedding."""
    if rubric_content is None:
        return ""
    if isinstance(rubric_content, str):
        return rubric_content
    try:
        import json

        return json.dumps(rubric_content, ensure_ascii=False, default=str)
    except Exception:
        return str(rubric_content)


def _rubric_requires_style(rubric_content: object) -> bool:
    """Best-effort detection of whether the rubric requires style review.

    Honours an explicit ``requires_style: true`` flag on a dict
    rubric; otherwise falls back to a keyword heuristic on the
    serialised text.  Conservative: a false negative simply means
    Pass 2 still runs whenever ``enable_lint_review`` AND
    ``linter_violations`` are present, per design-doc §4.
    """
    if isinstance(rubric_content, dict):
        if rubric_content.get("requires_style") is True:
            return True
    text = _stringify_rubric(rubric_content).lower()
    keywords = (
        "style",
        "maintainability",
        "readability",
        "formatting",
        "naming convention",
        "lint",
    )
    return any(k in text for k in keywords)


def _collect_code_chunks_from_repo(
    repo_path: str, language: str | None
) -> list[CodeChunk]:
    """Walk *repo_path* and extract AST chunks for files matching *language*.

    Returns an empty list (rather than raising) for unsupported
    languages, so Pass 2/3 can proceed with a degraded but
    well-defined evidence payload.
    """
    if not language:
        return []
    exts = _LANGUAGE_EXTENSIONS.get(language.lower())
    if not exts:
        logger.info(
            "run_pipeline: no AST chunker support for language=%r — "
            "Pass 2/3 will see an empty code_chunks list",
            language,
        )
        return []

    chunks: list[CodeChunk] = []
    root = Path(repo_path)
    if not root.exists():
        return []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in exts:
            continue
        # Skip vendor / dependency dirs to keep token cost bounded.
        parts = {p.lower() for p in path.parts}
        if parts & {"node_modules", ".venv", "venv", "__pycache__", "dist", "build"}:
            continue
        try:
            chunks.extend(extract_chunks(path))
        except Exception:
            logger.exception("run_pipeline: chunker failed on %s", path)
        if len(chunks) >= _MAX_CHUNKS_PER_REPO:
            logger.info(
                "run_pipeline: capping code chunks at %d for submission",
                _MAX_CHUNKS_PER_REPO,
            )
            break
    return chunks


def _extract_style_guide_versions(reasoning: dict) -> list[str]:
    """Collect distinct style_guide_version values cited by Pass 2 findings.

    Pass 2 findings carry an optional
    ``style_guide_source.style_guide_version`` per design-doc §3 §II.
    We surface the union (deduplicated, insertion-ordered) so the
    pipeline can stamp ``metadata_json["style_guide_version"]`` for
    audit / reproducibility.
    """
    pass2 = reasoning.get("pass2") or {}
    if pass2.get("skipped"):
        return []
    versions: list[str] = []
    seen: set[str] = set()
    for finding in pass2.get("findings", []) or []:
        source = finding.get("style_guide_source") or {}
        version = source.get("style_guide_version")
        if isinstance(version, str) and version and version not in seen:
            seen.add(version)
            versions.append(version)
    return versions
