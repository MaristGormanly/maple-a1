import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.assignment import Assignment
from ..models.submission import Submission


def parse_assignment_id(raw: str) -> uuid.UUID:
    """Parse a raw string into a UUID, raising ValueError on bad format.

    Centralises the validation that the audit flagged as missing: the
    evaluate form currently accepts an arbitrary string for assignment_id
    while the DB column is a UUID FK to assignments.  Sylvie's handler can
    call this to validate before persistence.
    """
    return uuid.UUID(raw)


async def get_assignment_by_id(
    db: AsyncSession,
    assignment_id: uuid.UUID,
) -> Assignment | None:
    result = await db.execute(
        select(Assignment).where(Assignment.id == assignment_id)
    )
    return result.scalar_one_or_none()


async def validate_assignment_exists(
    db: AsyncSession,
    assignment_id: uuid.UUID,
) -> Assignment:
    """Return the Assignment or raise ValueError if it doesn't exist.

    Provides FK-existence validation so that a Submission can safely
    reference this assignment_id without hitting an IntegrityError at
    commit time.
    """
    assignment = await get_assignment_by_id(db, assignment_id)
    if assignment is None:
        raise ValueError(f"Assignment '{assignment_id}' does not exist")
    return assignment


async def list_assignments(
    db: AsyncSession,
    *,
    instructor_id: uuid.UUID,
    role: str,
) -> list[tuple]:
    """Return all assignments visible to the caller, with submission counts.

    Instructors see only their own assignments. Admins see all.
    Each element is a (Assignment, int) tuple where the int is the
    count of submissions for that assignment.
    """
    count_sub = (
        select(func.count())
        .where(Submission.assignment_id == Assignment.id)
        .correlate(Assignment)
        .scalar_subquery()
    )
    q = select(Assignment, count_sub.label("submission_count")).order_by(Assignment.title)
    if role.strip().lower() not in ("admin",):
        q = q.where(Assignment.instructor_id == instructor_id)
    result = await db.execute(q)
    return result.all()


async def create_assignment(
    db: AsyncSession,
    *,
    title: str,
    instructor_id: uuid.UUID,
    test_suite_repo_url: str | None = None,
    rubric_id: uuid.UUID | None = None,
    enable_lint_review: bool = False,
    language_override: str | None = None,
) -> Assignment:
    assignment = Assignment(
        id=uuid.uuid4(),
        title=title,
        instructor_id=instructor_id,
        test_suite_repo_url=test_suite_repo_url,
        rubric_id=rubric_id,
        enable_lint_review=enable_lint_review,
        language_override=language_override,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return assignment
