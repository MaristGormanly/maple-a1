import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..middleware.auth import get_current_user, require_role
from ..models.database import get_db
from ..services.assignments import (
    create_assignment,
    delete_assignment,
    get_assignment_by_id,
    list_assignments,
    parse_assignment_id,
)
from ..utils.responses import error_response, success_response

router = APIRouter(prefix="/assignments", tags=["assignments"])


class AssignmentCreateRequest(BaseModel):
    title: str
    test_suite_repo_url: Optional[str] = None
    rubric_id: Optional[str] = None
    enable_lint_review: bool = False
    language_override: Optional[str] = None


def _assignment_to_dict(a, submission_count: int = 0) -> dict:
    return {
        "assignment_id": str(a.id),
        "title": a.title,
        "instructor_id": str(a.instructor_id),
        "test_suite_repo_url": a.test_suite_repo_url,
        "rubric_id": str(a.rubric_id) if a.rubric_id else None,
        "enable_lint_review": a.enable_lint_review,
        "language_override": a.language_override,
        "submission_count": submission_count,
    }


@router.get("")
async def list_assignments_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    instructor_id = uuid.UUID(current_user["sub"])
    role = current_user.get("role", "")
    rows = await list_assignments(db, instructor_id=instructor_id, role=role)
    return success_response({
        "assignments": [
            _assignment_to_dict(assignment, int(count))
            for assignment, count in rows
        ]
    })


@router.post("")
async def create_assignment_endpoint(
    request: AssignmentCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("Instructor")),
):
    rubric_uuid = None
    if request.rubric_id:
        try:
            rubric_uuid = uuid.UUID(request.rubric_id)
        except ValueError:
            return error_response(
                status_code=400,
                code="VALIDATION_ERROR",
                message="rubric_id must be a valid UUID",
            )

    instructor_id = uuid.UUID(current_user["sub"])

    assignment = await create_assignment(
        db,
        title=request.title,
        instructor_id=instructor_id,
        test_suite_repo_url=request.test_suite_repo_url,
        rubric_id=rubric_uuid,
        enable_lint_review=request.enable_lint_review,
        language_override=request.language_override,
    )

    return success_response(_assignment_to_dict(assignment))


@router.get("/{assignment_id}")
async def get_assignment_endpoint(
    assignment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        aid = parse_assignment_id(assignment_id)
    except ValueError:
        return error_response(
            status_code=400,
            code="VALIDATION_ERROR",
            message="assignment_id must be a valid UUID",
        )

    assignment = await get_assignment_by_id(db, aid)
    if not assignment:
        return error_response(
            status_code=404,
            code="NOT_FOUND",
            message=f"Assignment '{assignment_id}' not found",
        )

    return success_response(_assignment_to_dict(assignment))


@router.delete("/{assignment_id}", status_code=200)
async def delete_assignment_endpoint(
    assignment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("Instructor")),
):
    try:
        aid = parse_assignment_id(assignment_id)
    except ValueError:
        return error_response(400, "VALIDATION_ERROR", "assignment_id must be a valid UUID")

    assignment = await get_assignment_by_id(db, aid)
    if not assignment:
        return error_response(404, "NOT_FOUND", f"Assignment '{assignment_id}' not found")

    try:
        current_user_id = uuid.UUID(str(current_user["sub"]))
    except (KeyError, ValueError, TypeError):
        return error_response(401, "AUTH_ERROR", "Invalid user identity in token.")

    if assignment.instructor_id != current_user_id:
        return error_response(403, "FORBIDDEN", "You do not own this assignment")

    await delete_assignment(db, aid)
    return success_response({"deleted": assignment_id})
