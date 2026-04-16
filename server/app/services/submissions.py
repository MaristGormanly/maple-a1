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
) -> EvaluationResult:
    """Persist an EvaluationResult row.

    Raises ``DuplicateEvaluationError`` (instead of a raw
    ``IntegrityError``) when a result already exists for *submission_id*,
    so callers can treat duplicate runs as non-fatal.
    """
    row = EvaluationResult(
        id=uuid.uuid4(),
        submission_id=submission_id,
        deterministic_score=deterministic_score,
        ai_feedback_json=None,
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
