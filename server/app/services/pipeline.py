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
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from ..models.database import async_session_maker
from . import llm
# region agent log
from ._debug_log import dlog as _dlog  # debug session d6fd1e
# endregion
from .ai_passes import run_pass1, run_pass2, run_pass3
from .assignments import get_assignment_by_id
from .ast_chunker import CodeChunk, extract_chunks
from .docker_client import run_container
from .git_ingest import CloneError, clone_repository
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

_CONTAINER_TIMEOUT_SECONDS = 120


def _resolve_clone_repository():
    """Return a clone function, preferring app.main for test patching compatibility."""
    app_main = sys.modules.get("app.main")
    if app_main is not None:
        maybe_clone = getattr(app_main, "clone_repository", None)
        if callable(maybe_clone):
            return maybe_clone
    return clone_repository

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
    from .linter_runner import run_linter as _run_linter  # type: ignore
except Exception:  # pragma: no cover -- import guard
    _run_linter = None  # type: ignore[assignment]


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
        sig = inspect.signature(llm.complete)
        has_var_kw = any(
            p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
        if "model" not in sig.parameters and not has_var_kw:
            return False
    except (TypeError, ValueError):
        pass

    try:
        src = inspect.getsource(llm.complete)
    except (TypeError, OSError):
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
    # region agent log
    _dlog(
        location="pipeline.py:run_pipeline:enter",
        hypothesis_id="A,B,F",
        message="run_pipeline entered",
        data={
            "submission_id": str(submission_id),
            "assignment_id": str(assignment_id) if assignment_id else None,
            "student_repo_path": student_repo_path,
        },
    )
    # endregion
    if assignment_id is None:
        return

    test_suite_dir: Path | None = None
    try:
        async with async_session_maker() as db:
            if await update_submission_status(db, submission_id, "Testing") is None:
                logger.warning("run_pipeline: submission %s not found", submission_id)
                return
            _dlog(
                location="pipeline.py:run_pipeline:status_set_testing",
                hypothesis_id="A,B,F",
                message="status set to Testing",
                data={"submission_id": str(submission_id)},
                run_id=str(submission_id)[:8],
            )
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
            _dlog(
                location="pipeline.py:run_pipeline:assignment_resolved",
                hypothesis_id="A,B",
                message="assignment loaded",
                data={
                    "submission_id": str(submission_id),
                    "suite_url": suite_url,
                    "language_override": language_override,
                    "enable_lint_review": enable_lint_review,
                },
                run_id=str(submission_id)[:8],
            )

        test_suite_dir = Path(tempfile.mkdtemp(prefix="maple-testsuite-"))
        clone_impl = _resolve_clone_repository()
        _dlog(
            location="pipeline.py:run_pipeline:clone_start",
            hypothesis_id="A,B",
            message="about to clone test suite",
            data={"submission_id": str(submission_id), "suite_url": suite_url},
            run_id=str(submission_id)[:8],
        )
        try:
            await clone_impl(suite_url, test_suite_dir, github_pat)
        except CloneError as exc:
            shutil.rmtree(test_suite_dir, ignore_errors=True)
            logger.error("run_pipeline: test suite clone failed: %s", exc.message)
            await update_submission_status(db, submission_id, "Failed")
            return
        _dlog(
            location="pipeline.py:run_pipeline:clone_done",
            hypothesis_id="A,B",
            message="test suite cloned successfully",
            data={
                "submission_id": str(submission_id),
                "test_suite_dir": str(test_suite_dir),
            },
            run_id=str(submission_id)[:8],
        )

        lang = detect_language_version(student_repo_path, language_override)
        language = lang.get("language", "")
        _dlog(
            location="pipeline.py:run_pipeline:container_start",
            hypothesis_id="A,B",
            message="about to run student container",
            data={
                "submission_id": str(submission_id),
                "language": language,
                "timeout_seconds": _CONTAINER_TIMEOUT_SECONDS,
            },
            run_id=str(submission_id)[:8],
        )
        _container_run_error: str | None = None
        try:
            container = await run_container(
                language,
                student_repo_path,
                str(test_suite_dir.resolve()),
                timeout_seconds=_CONTAINER_TIMEOUT_SECONDS,
            )
        except Exception as _exc:
            _container_run_error = str(_exc)
            logger.warning(
                "run_pipeline: container run failed; continuing with null test results — %s",
                _container_run_error,
            )
            from .docker_client import ContainerResult as _ContainerResult
            container = _ContainerResult(stdout="", stderr="", exit_code=None)

        _dlog(
            location="pipeline.py:run_pipeline:container_done",
            hypothesis_id="A,B",
            message="container finished",
            data={
                "submission_id": str(submission_id),
                "exit_code": container.exit_code,
                "stdout_len": len(container.stdout or ""),
                "stderr_len": len(container.stderr or ""),
            },
            run_id=str(submission_id)[:8],
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

        # Persist deterministic results first; status transitions are
        # decided by whether the AI phase will run.  We deliberately
        # do NOT mark "Completed" yet when the AI phase is queued — a
        # transient "Completed" would let the frontend's
        # ``TERMINAL_STATUSES`` poll guard short-circuit before AI
        # feedback lands (status-page.component.ts).
        async with async_session_maker() as db:
            await persist_evaluation_result(
                db,
                submission_id=submission_id,
                deterministic_score=score,
                metadata_json=metadata_json,
            )
        _dlog(
            location="pipeline.py:run_pipeline:deterministic_persisted",
            hypothesis_id="A,B",
            message="deterministic result persisted",
            data={
                "submission_id": str(submission_id),
                "deterministic_score": score,
            },
            run_id=str(submission_id)[:8],
        )

        # ---------------- Milestone 3: Evaluating phase ----------------
        # Runs only when Jayden's LLM wrapper is operational.  Any
        # LLM/schema failure is handled inline (mapped to
        # EVALUATION_FAILED) so it does NOT cascade into the outer
        # generic-Failed branch below.
        # region agent log
        _llm_ready_value = _is_llm_ready()
        _dlog(
            location="pipeline.py:run_pipeline:llm_ready_gate",
            hypothesis_id="A,B",
            message="post-deterministic; checking LLM readiness",
            data={
                "submission_id": str(submission_id),
                "is_llm_ready": _llm_ready_value,
                "deterministic_score": score,
                "test_count_total": (
                    parsed.get("passed", 0) + parsed.get("failed", 0)
                    + parsed.get("errors", 0) + parsed.get("skipped", 0)
                ),
                "language": language,
                "enable_lint_review": enable_lint_review,
            },
        )
        # endregion
        if _llm_ready_value:
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
            # region agent log
            _dlog(
                location="pipeline.py:run_pipeline:llm_not_ready",
                hypothesis_id="A",
                message="AI phase skipped because _is_llm_ready returned False",
                data={"submission_id": str(submission_id)},
            )
            # endregion
            logger.info(
                "run_pipeline: skipping AI phase for submission %s — "
                "llm.complete is still the M1 stub",
                submission_id,
            )
            async with async_session_maker() as db:
                await update_submission_status(db, submission_id, "Completed")
    except DuplicateEvaluationError:
        # region agent log
        _dlog(
            location="pipeline.py:run_pipeline:duplicate_eval",
            hypothesis_id="F",
            message="DuplicateEvaluationError caught — existing result preserved",
            data={"submission_id": str(submission_id)},
        )
        # endregion
        logger.info(
            "run_pipeline: duplicate evaluation for submission %s — "
            "keeping existing result and Completed status",
            submission_id,
        )
    except Exception as _exc:
        # region agent log
        _dlog(
            location="pipeline.py:run_pipeline:generic_exception",
            hypothesis_id="B,D",
            message="run_pipeline outer except Exception fired",
            data={
                "submission_id": str(submission_id),
                "exc_type": type(_exc).__name__,
                "exc_str": str(_exc)[:300],
            },
        )
        # endregion
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

def _normalize_criteria_scores(envelope: dict) -> None:
    """Convert LLM 1-5 ordinal scores to 0-100: 50 + (score - 1) * 12.5."""
    for criterion in envelope.get("criteria_scores") or []:
        raw = criterion.get("score")
        if isinstance(raw, (int, float)) and 1 <= raw <= 5:
            criterion["score"] = round(50 + (raw - 1) * 12.5, 2)


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
    if _run_linter is not None:
        try:
            linter_violations = await _maybe_await(
                _run_linter(language, str(student_repo_path))
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

    # region agent log
    _dlog(
        location="pipeline.py:_run_evaluating_phase:enter",
        hypothesis_id="B,C,E",
        message="entering AI evaluating phase",
        data={
            "submission_id": str(submission_id),
            "code_chunks_count": len(code_chunks),
            "linter_violations_count": (
                0 if linter_violations is None else len(linter_violations)
            ),
            "rubric_requires_style": rubric_requires_style,
            "rubric_text_len": len(rubric_text),
            "test_count_total": (
                parsed.get("passed", 0) + parsed.get("failed", 0)
                + parsed.get("errors", 0) + parsed.get("skipped", 0)
            ),
            "tests_in_payload": len(parsed.get("tests", []) or []),
        },
    )
    # endregion

    try:
        pass1 = await run_pass1(
            parsed_test_results=parsed,
            rubric_content=rubric_text,
            exit_code=container_exit_code,
            resource_constraint_metadata=parsed.get("resource_constraint_metadata"),
        )
        # region agent log
        _dlog(
            location="pipeline.py:_run_evaluating_phase:pass1_done",
            hypothesis_id="B,C",
            message="pass1 returned",
            data={
                "submission_id": str(submission_id),
                "pass1_keys": list(pass1.keys()) if isinstance(pass1, dict) else None,
                "pass1_failures_count": len(
                    pass1.get("failures", []) if isinstance(pass1, dict) else []
                ),
            },
        )
        # endregion

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
        # region agent log
        _dlog(
            location="pipeline.py:_run_evaluating_phase:pass2_done",
            hypothesis_id="B,C",
            message="pass2 returned",
            data={
                "submission_id": str(submission_id),
                "reasoning_keys": list(reasoning.keys()) if isinstance(reasoning, dict) else None,
                "pass2_skipped": (
                    reasoning.get("pass2", {}).get("skipped")
                    if isinstance(reasoning, dict) else None
                ),
                "pass2_findings_count": len(
                    (reasoning.get("pass2", {}) or {}).get("findings", [])
                    if isinstance(reasoning, dict) else []
                ),
            },
        )
        # endregion

        envelope = await run_pass3(
            reasoning=reasoning,
            rubric_content=rubric_text,
            deterministic_score=deterministic_score,
            metadata=metadata_json,
            code_chunks=code_chunks,
        )
        _normalize_criteria_scores(envelope)
        # region agent log
        _dlog(
            location="pipeline.py:_run_evaluating_phase:pass3_done",
            hypothesis_id="C,D",
            message="pass3 returned",
            data={
                "submission_id": str(submission_id),
                "envelope_keys": list(envelope.keys()) if isinstance(envelope, dict) else None,
                "criteria_scores_count": len(envelope.get("criteria_scores", []) or []),
                "flags": envelope.get("flags", []),
                "per_criterion_recs_counts": [
                    len(c.get("recommendations", []) or [])
                    for c in (envelope.get("criteria_scores", []) or [])
                    if isinstance(c, dict)
                ],
            },
        )
        # endregion
    except EvaluationFailedError as exc:
        # region agent log
        _dlog(
            location="pipeline.py:_run_evaluating_phase:evaluation_failed",
            hypothesis_id="B,C",
            message="EvaluationFailedError caught — schema/repair exhausted",
            data={
                "submission_id": str(submission_id),
                "error_str": str(exc)[:300],
                "validation_errors": getattr(exc, "validation_errors", None),
            },
        )
        # endregion
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
        # region agent log
        _dlog(
            location="pipeline.py:_run_evaluating_phase:before_persist",
            hypothesis_id="C,D",
            message="about to persist ai_feedback_json + terminal status",
            data={
                "submission_id": str(submission_id),
                "terminal_status": terminal_status,
                "criteria_scores_count": len(envelope.get("criteria_scores", []) or []),
                "flags_in_envelope": envelope.get("flags", []),
            },
        )
        # endregion
        async with async_session_maker() as db:
            await update_evaluation_result(
                db,
                submission_id=submission_id,
                ai_feedback_json=envelope,
                metadata_json=metadata_json,
            )
            await update_submission_status(db, submission_id, terminal_status)
        # region agent log
        _dlog(
            location="pipeline.py:_run_evaluating_phase:after_persist",
            hypothesis_id="C,D",
            message="ai_feedback_json persisted; terminal status set",
            data={
                "submission_id": str(submission_id),
                "terminal_status": terminal_status,
            },
        )
        # endregion
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
