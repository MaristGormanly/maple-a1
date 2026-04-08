import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.database import get_db
from ..models.submission import Submission
from ..middleware.auth import get_current_user
from ..utils.responses import error_response, success_response

router = APIRouter(prefix="/submissions", tags=["submissions"])


def _can_view_submission(submission: Submission, current_user: dict) -> bool:
    role = str(current_user.get("role", "")).strip().lower()

    try:
        current_user_id = uuid.UUID(str(current_user["sub"]))
    except (KeyError, ValueError, TypeError):
        return False

    if submission.student_id == current_user_id:
        return True

    if role == "admin":
        return True

    if role == "instructor" and submission.assignment is not None:
        return submission.assignment.instructor_id == current_user_id

    return False


@router.get("/{submission_id}")
async def get_submission(
    submission_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        sid = uuid.UUID(submission_id)
    except ValueError:
        return error_response(
            status_code=400,
            code="VALIDATION_ERROR",
            message="submission_id must be a valid UUID",
        )

    result = await db.execute(
        select(Submission)
        .options(selectinload(Submission.assignment))
        .options(selectinload(Submission.evaluation_result))
        .where(Submission.id == sid)
    )
    submission = result.scalar_one_or_none()

    if not submission:
        return error_response(
            status_code=404,
            code="NOT_FOUND",
            message=f"Submission '{submission_id}' not found",
        )

    if not _can_view_submission(submission, current_user):
        return error_response(
            status_code=403,
            code="FORBIDDEN",
            message="Access denied.",
        )

    data = {
        "submission_id": str(submission.id),
        "assignment_id": str(submission.assignment_id),
        "student_id": str(submission.student_id),
        "github_repo_url": submission.github_repo_url,
        "commit_hash": submission.commit_hash,
        "status": submission.status,
        "created_at": submission.created_at.isoformat() if submission.created_at else None,
    }

    if submission.evaluation_result:
        data["evaluation"] = {
            "deterministic_score": submission.evaluation_result.deterministic_score,
            "ai_feedback": submission.evaluation_result.ai_feedback_json,
        }

    return success_response(data)
