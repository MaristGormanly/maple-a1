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
