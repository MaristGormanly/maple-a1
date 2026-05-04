import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.database import get_db
from ..models.submission import Submission
from ..middleware.auth import get_current_user, require_role
from ..utils.responses import error_response, success_response

router = APIRouter(prefix="/submissions", tags=["submissions"])


class ReviewRequest(BaseModel):
    action: Literal["approve", "reject"]
    instructor_notes: str | None = None


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


def _flatten_criteria_recommendations(criteria_scores: list) -> list:
    """Flatten per-criterion recommendation(s) for the AI feedback envelope.

    The Pass 3 schema (``llm_schemas.CRITERIA_SCORE_SCHEMA``) emits a
    plural ``recommendations`` array per criterion. We also tolerate a
    singular ``recommendation`` object for backwards compatibility with
    older payloads / fallback shapes. Order is preserved across criteria
    so the diff viewer renders them top-down.
    """
    flat: list = []
    for c in criteria_scores:
        if not isinstance(c, dict):
            continue
        plural = c.get("recommendations")
        if isinstance(plural, list):
            for rec in plural:
                if isinstance(rec, dict) and rec:
                    flat.append(rec)
        singular = c.get("recommendation")
        if isinstance(singular, dict) and singular:
            flat.append(singular)
    return flat


def _serialize_submission(submission: Submission, viewer_role: str) -> dict:
    """Build the canonical SubmissionStatusData envelope for a submission.

    Used by both ``GET /submissions/{id}`` and ``POST /submissions/{id}/review``
    so the two endpoints return byte-identical shapes (modulo timestamps).
    AI feedback is surfaced only to privileged viewers (Instructor/Admin)
    or when the submission has been approved.
    """
    role = viewer_role.strip().lower() if viewer_role else ""
    viewer_is_privileged = role in ("instructor", "admin")

    data: dict = {
        "submission_id": str(submission.id),
        "assignment_id": str(submission.assignment_id) if submission.assignment_id else None,
        "student_id": str(submission.student_id),
        "github_repo_url": submission.github_repo_url,
        "commit_hash": submission.commit_hash,
        "status": submission.status,
        "created_at": submission.created_at.isoformat() if submission.created_at else None,
    }

    if submission.evaluation_result:
        er = submission.evaluation_result
        review_status = getattr(er, "review_status", "pending")
        instructor_notes = getattr(er, "instructor_notes", None)

        eval_data: dict = {
            "deterministic_score": er.deterministic_score,
            "review_status": review_status,
            "instructor_notes": instructor_notes,
            "ai_feedback": None,
        }

        meta = er.metadata_json
        if meta and isinstance(meta, dict):
            eval_data["metadata"] = {
                "language": meta.get("language"),
                "test_summary": meta.get("test_summary"),
            }

        feedback_json = er.ai_feedback_json
        if feedback_json and isinstance(feedback_json, dict):
            if viewer_is_privileged or review_status == "approved":
                criteria_scores = feedback_json.get("criteria_scores") or []
                recommendations = _flatten_criteria_recommendations(
                    criteria_scores
                )
                ai_meta = feedback_json.get("metadata") or {}
                eval_data["ai_feedback"] = {
                    "criteria_scores": criteria_scores,
                    "flags": feedback_json.get("flags") or [],
                    "metadata": {
                        "style_guide_version": ai_meta.get("style_guide_version"),
                        "language": ai_meta.get("language"),
                    },
                    "recommendations": recommendations,
                }

        data["evaluation"] = eval_data

    return data


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

    return success_response(
        _serialize_submission(submission, str(current_user.get("role", "")))
    )


@router.post("/{submission_id}/review")
async def review_submission(
    submission_id: str,
    body: ReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("Instructor")),
):
    try:
        sid = uuid.UUID(submission_id)
    except ValueError:
        return error_response(400, "VALIDATION_ERROR", "submission_id must be a valid UUID")

    result = await db.execute(
        select(Submission)
        .options(selectinload(Submission.assignment))
        .options(selectinload(Submission.evaluation_result))
        .where(Submission.id == sid)
    )
    submission = result.scalar_one_or_none()

    if not submission:
        return error_response(404, "NOT_FOUND", f"Submission '{submission_id}' not found")

    if submission.assignment is None:
        return error_response(403, "FORBIDDEN", "Access denied.")

    try:
        current_user_id = uuid.UUID(str(current_user["sub"]))
    except (KeyError, ValueError, TypeError):
        return error_response(401, "AUTH_ERROR", "Invalid user identity in token.")

    if submission.assignment.instructor_id != current_user_id:
        return error_response(403, "FORBIDDEN", "Access denied.")

    if submission.status != "Awaiting Review":
        return error_response(
            400,
            "VALIDATION_ERROR",
            f"Submission is not awaiting review (current status: {submission.status})",
        )

    if submission.evaluation_result is None:
        return error_response(400, "VALIDATION_ERROR", "Submission has no evaluation result to review")

    if body.action == "approve":
        submission.status = "Completed"
        submission.evaluation_result.review_status = "approved"
    else:
        submission.status = "Rejected"
        submission.evaluation_result.review_status = "rejected"
        submission.evaluation_result.instructor_notes = body.instructor_notes

    await db.commit()
    await db.refresh(submission)
    await db.refresh(submission.evaluation_result)

    return success_response(
        _serialize_submission(submission, str(current_user.get("role", "")))
    )
