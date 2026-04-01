import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.models import Rubric, get_db
from server.app.utils.responses import success_response, error_response

router = APIRouter(prefix="/rubrics", tags=["rubrics"])


class RubricLevel(BaseModel):
    label: str
    points: int
    description: str


class RubricCriterion(BaseModel):
    name: str
    max_points: int
    levels: list[RubricLevel]

    @field_validator("levels")
    @classmethod
    def at_least_one_level(cls, v):
        if len(v) < 1:
            raise ValueError("Each criterion must have at least one level")
        return v


class RubricCreateRequest(BaseModel):
    rubric_id: Optional[str] = None
    title: str
    total_points: int
    criteria: list[RubricCriterion]

    @field_validator("criteria")
    @classmethod
    def at_least_one_criterion(cls, v):
        if len(v) < 1:
            raise ValueError("Rubric must have at least one criterion")
        return v


@router.post("")
async def create_rubric(request: RubricCreateRequest, db: AsyncSession = Depends(get_db)):
    criteria_total = sum(c.max_points for c in request.criteria)
    if criteria_total != request.total_points:
        return error_response(
            status_code=400,
            code="VALIDATION_ERROR",
            message=f"Sum of criteria max_points ({criteria_total}) does not equal total_points ({request.total_points})",
        )

    rubric_id = uuid.UUID(request.rubric_id) if request.rubric_id else uuid.uuid4()

    rubric = Rubric(
        id=rubric_id,
        title=request.title,
        total_points=request.total_points,
        schema_json=[c.model_dump() for c in request.criteria],
    )

    db.add(rubric)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return error_response(
            status_code=409,
            code="CONFLICT",
            message=f"A rubric with id '{rubric_id}' already exists",
        )
    await db.refresh(rubric)

    return success_response({
        "rubric_id": str(rubric.id),
        "title": rubric.title,
        "criteria_count": len(request.criteria),
    })
