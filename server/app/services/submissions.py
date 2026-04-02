import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.submission import Submission


async def create_submission(
    db: AsyncSession,
    *,
    assignment_id: uuid.UUID,
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
