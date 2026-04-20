import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.evaluation_result import EvaluationResult
from ..models.submission import Submission

logger = logging.getLogger(__name__)


class DuplicateEvaluationError(Exception):
    """Raised when an EvaluationResult already exists for the submission."""


async def create_submission(
    db: AsyncSession,
    *,
    assignment_id: uuid.UUID | None = None,
    student_id: uuid.UUID,
    github_repo_url: str,
    commit_hash: str | None = None,
    status: str = "Pending",
) -> Submission:
    """Persist a new Submission row and return the refreshed ORM instance.

    Intended to be called from the evaluate handler (Sylvie's ingestion
    pipeline) after cloning succeeds, so that downstream GET /submissions/{id}
    and future milestones can read from PostgreSQL instead of the JSON cache.
    """
    submission = Submission(
        id=uuid.uuid4(),
        assignment_id=assignment_id,
        student_id=student_id,
        github_repo_url=github_repo_url,
        commit_hash=commit_hash,
        status=status,
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)
    return submission


async def get_submission_by_id(
    db: AsyncSession,
    submission_id: uuid.UUID,
) -> Submission | None:
    result = await db.execute(
        select(Submission).where(Submission.id == submission_id)
    )
    return result.scalar_one_or_none()


async def persist_evaluation_result(
    db: AsyncSession,
    *,
    submission_id: uuid.UUID,
    deterministic_score: float | None,
    metadata_json: dict | None = None,
    ai_feedback_json: dict | None = None,
) -> EvaluationResult:
    """Persist an EvaluationResult row.

    The ``ai_feedback_json`` parameter is optional and defaults to
    ``None`` to preserve backward compatibility with the M2 deterministic
    path, which calls this helper *before* the AI passes have produced a
    payload.  M3 callers may pre-populate it when they know the value at
    insert time, but the typical M3 flow creates the row with
    ``ai_feedback_json=None`` here and then merges the LLM envelope in
    via :func:`update_evaluation_result` once the three-pass pipeline
    completes.

    Raises ``DuplicateEvaluationError`` (instead of a raw
    ``IntegrityError``) when a result already exists for *submission_id*,
    so callers can treat duplicate runs as non-fatal.
    """
    row = EvaluationResult(
        id=uuid.uuid4(),
        submission_id=submission_id,
        deterministic_score=deterministic_score,
        ai_feedback_json=ai_feedback_json,
        metadata_json=metadata_json,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        logger.warning(
            "Duplicate EvaluationResult for submission %s — treating as idempotent",
            submission_id,
        )
        raise DuplicateEvaluationError(
            f"EvaluationResult already exists for submission {submission_id}"
        )
    await db.refresh(row)
    return row


async def _load_evaluation_result_by_submission(
    db: AsyncSession,
    submission_id: uuid.UUID,
) -> EvaluationResult | None:
    """Internal helper — load the (unique) EvaluationResult for a submission."""
    result = await db.execute(
        select(EvaluationResult).where(
            EvaluationResult.submission_id == submission_id
        )
    )
    return result.scalar_one_or_none()


async def update_evaluation_result(
    db: AsyncSession,
    *,
    submission_id: uuid.UUID,
    ai_feedback_json: dict | None = None,
    metadata_json: dict | None = None,
) -> EvaluationResult | None:
    """Merge-update the EvaluationResult row for *submission_id*.

    Semantics
    ---------
    1. Load the existing row by ``submission_id``.
    2. If found, apply non-``None`` field updates and commit.  Passing
       ``None`` for either field leaves the existing column value
       untouched (i.e. partial updates are supported).
    3. If no row exists, insert one with the supplied fields and commit
       (``deterministic_score`` is left ``NULL`` — only the M2
       deterministic phase fills that column).
    4. If the insert races a concurrent writer (``IntegrityError`` on
       the unique ``submission_id`` constraint), roll back, **re-load**
       the now-existing row, and merge-update it.  This honours the
       ``DuplicateEvaluationError`` contract: the AI update path will
       *never* surface a duplicate to the caller — it converges on the
       canonical row.

    The typical M3 caller is :func:`app.services.pipeline.run_pipeline`,
    which always calls :func:`persist_evaluation_result` first, so the
    load path (step 1) is the hot path.  The insert/race path exists
    purely for defence in depth (manual re-runs, replay tooling, etc.).

    Returns
    -------
    The refreshed :class:`EvaluationResult` row.  Returns ``None`` only
    if both the load and the insert (after rollback) fail to surface a
    row — which would indicate a corrupt DB state and is logged.
    """
    row = await _load_evaluation_result_by_submission(db, submission_id)

    if row is not None:
        return await _apply_merge_update(
            db,
            row,
            ai_feedback_json=ai_feedback_json,
            metadata_json=metadata_json,
        )

    # No existing row — insert.  This branch is unusual for the
    # M3 pipeline (which always calls persist_evaluation_result first)
    # but supported for replay / manual-update tooling.
    logger.info(
        "update_evaluation_result: inserting new EvaluationResult for "
        "submission %s (no existing row found)",
        submission_id,
    )
    new_row = EvaluationResult(
        id=uuid.uuid4(),
        submission_id=submission_id,
        deterministic_score=None,
        ai_feedback_json=ai_feedback_json,
        metadata_json=metadata_json,
    )
    db.add(new_row)
    try:
        await db.commit()
    except IntegrityError:
        # Concurrent writer beat us to the unique constraint.  Roll
        # back, re-load, and merge — never surface DuplicateEvaluationError
        # on the AI update path.
        await db.rollback()
        logger.warning(
            "update_evaluation_result: insert raced for submission %s; "
            "falling back to merge-update on re-loaded row",
            submission_id,
        )
        row = await _load_evaluation_result_by_submission(db, submission_id)
        if row is None:
            logger.error(
                "update_evaluation_result: insert raced but row still not "
                "visible for submission %s — DB state inconsistent",
                submission_id,
            )
            return None
        return await _apply_merge_update(
            db,
            row,
            ai_feedback_json=ai_feedback_json,
            metadata_json=metadata_json,
        )

    await db.refresh(new_row)
    return new_row


async def _apply_merge_update(
    db: AsyncSession,
    row: EvaluationResult,
    *,
    ai_feedback_json: dict | None,
    metadata_json: dict | None,
) -> EvaluationResult:
    """Apply field updates to *row* and commit.  Internal helper.

    ``None`` for either field is interpreted as "leave the existing
    value untouched" — callers that want to *clear* a field should
    pass an explicit empty dict (``{}``).
    """
    if ai_feedback_json is not None:
        row.ai_feedback_json = ai_feedback_json
    if metadata_json is not None:
        row.metadata_json = metadata_json
    await db.commit()
    await db.refresh(row)
    return row


async def update_submission_status(
    db: AsyncSession,
    submission_id: uuid.UUID,
    status: str,
) -> Submission | None:
    """Update a submission's status (e.g. Pending -> Testing -> Completed)."""
    submission = await get_submission_by_id(db, submission_id)
    if submission is None:
        return None
    submission.status = status
    await db.commit()
    await db.refresh(submission)
    return submission
