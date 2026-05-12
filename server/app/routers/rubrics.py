import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..middleware.auth import get_current_user, require_role
from ..models import Rubric, get_db
from ..models.assignment import Assignment
from ..utils.responses import success_response, error_response

router = APIRouter(prefix="/rubrics", tags=["rubrics"])

_UPLOADS_DIR = Path(__file__).resolve().parents[3] / "uploads" / "rubrics"


def _rubric_to_dict(r: Rubric) -> dict:
    return {
        "rubric_id": str(r.id),
        "title": r.title,
        "total_points": r.total_points,
        "notes": r.notes,
        "filename": r.filename,
        "has_file": r.filename is not None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# ── Pydantic schemas for POST /rubrics (existing) ────────────────────────────

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
    notes: Optional[str] = None

    @field_validator("criteria")
    @classmethod
    def at_least_one_criterion(cls, v):
        if len(v) < 1:
            raise ValueError("Rubric must have at least one criterion")
        return v


class RubricUpdateRequest(BaseModel):
    title: Optional[str] = None
    notes: Optional[str] = None


# ── POST /rubrics ─────────────────────────────────────────────────────────────

@router.post("")
async def create_rubric(
    request: RubricCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("Instructor")),
):
    criteria_total = sum(c.max_points for c in request.criteria)
    if criteria_total != request.total_points:
        return error_response(
            status_code=400,
            code="VALIDATION_ERROR",
            message=f"Sum of criteria max_points ({criteria_total}) does not equal total_points ({request.total_points})",
        )

    if request.rubric_id:
        try:
            rubric_id = uuid.UUID(request.rubric_id)
        except ValueError:
            return error_response(
                status_code=400,
                code="VALIDATION_ERROR",
                message="rubric_id must be a valid UUID",
            )
    else:
        rubric_id = uuid.uuid4()

    rubric = Rubric(
        id=rubric_id,
        title=request.title,
        total_points=request.total_points,
        schema_json=[c.model_dump() for c in request.criteria],
        notes=request.notes,
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


# ── GET /rubrics ──────────────────────────────────────────────────────────────

@router.get("")
async def list_rubrics(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Rubric).order_by(Rubric.created_at.desc()))
    rubrics = result.scalars().all()
    return success_response({"rubrics": [_rubric_to_dict(r) for r in rubrics]})


# ── GET /rubrics/{rubric_id} ──────────────────────────────────────────────────

@router.get("/{rubric_id}")
async def get_rubric(
    rubric_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        rid = uuid.UUID(rubric_id)
    except ValueError:
        return error_response(400, "VALIDATION_ERROR", "rubric_id must be a valid UUID")
    rubric = await db.get(Rubric, rid)
    if not rubric:
        return error_response(404, "NOT_FOUND", f"Rubric '{rubric_id}' not found")
    return success_response(_rubric_to_dict(rubric))


# ── PUT /rubrics/{rubric_id} ──────────────────────────────────────────────────

@router.put("/{rubric_id}")
async def update_rubric(
    rubric_id: str,
    request: RubricUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("Instructor")),
):
    try:
        rid = uuid.UUID(rubric_id)
    except ValueError:
        return error_response(400, "VALIDATION_ERROR", "rubric_id must be a valid UUID")
    rubric = await db.get(Rubric, rid)
    if not rubric:
        return error_response(404, "NOT_FOUND", f"Rubric '{rubric_id}' not found")
    if request.title is not None:
        rubric.title = request.title
    if request.notes is not None:
        rubric.notes = request.notes
    await db.commit()
    await db.refresh(rubric)
    return success_response(_rubric_to_dict(rubric))


# ── DELETE /rubrics/{rubric_id} ───────────────────────────────────────────────

@router.delete("/{rubric_id}")
async def delete_rubric(
    rubric_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("Instructor")),
):
    try:
        rid = uuid.UUID(rubric_id)
    except ValueError:
        return error_response(400, "VALIDATION_ERROR", "rubric_id must be a valid UUID")
    rubric = await db.get(Rubric, rid)
    if not rubric:
        return error_response(404, "NOT_FOUND", f"Rubric '{rubric_id}' not found")

    linked = (
        await db.execute(select(Assignment).where(Assignment.rubric_id == rid).limit(1))
    ).scalar_one_or_none()
    if linked:
        return error_response(
            409, "CONFLICT", "Rubric is linked to an assignment — unlink it first."
        )

    if rubric.filename:
        for f in _UPLOADS_DIR.glob(f"{rubric_id}_*"):
            f.unlink(missing_ok=True)

    await db.delete(rubric)
    await db.commit()
    return success_response({"deleted": rubric_id})


# ── POST /rubrics/{rubric_id}/file ────────────────────────────────────────────

_ALLOWED_EXTENSIONS = {".pdf", ".json", ".txt"}


@router.post("/{rubric_id}/file")
async def upload_rubric_file(
    rubric_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("Instructor")),
):
    try:
        rid = uuid.UUID(rubric_id)
    except ValueError:
        return error_response(400, "VALIDATION_ERROR", "rubric_id must be a valid UUID")
    rubric = await db.get(Rubric, rid)
    if not rubric:
        return error_response(404, "NOT_FOUND", f"Rubric '{rubric_id}' not found")

    original_name = file.filename or "rubric"
    ext = Path(original_name).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        return error_response(
            400, "VALIDATION_ERROR", f"Unsupported file type '{ext}'. Use .pdf, .json, or .txt."
        )

    content = await file.read()

    # Remove old stored file(s) for this rubric
    if rubric.filename:
        for old in _UPLOADS_DIR.glob(f"{rubric_id}_*"):
            old.unlink(missing_ok=True)

    _UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{rubric_id}_{uuid.uuid4().hex[:8]}{ext}"
    (_UPLOADS_DIR / stored_name).write_bytes(content)

    rubric.filename = original_name
    await db.commit()
    await db.refresh(rubric)
    return success_response(_rubric_to_dict(rubric))


# ── GET /rubrics/{rubric_id}/file ─────────────────────────────────────────────

@router.get("/{rubric_id}/file")
async def get_rubric_file(
    rubric_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        rid = uuid.UUID(rubric_id)
    except ValueError:
        return error_response(400, "VALIDATION_ERROR", "rubric_id must be a valid UUID")
    rubric = await db.get(Rubric, rid)
    if not rubric or not rubric.filename:
        return error_response(404, "NOT_FOUND", "No file stored for this rubric")

    stored_files = list(_UPLOADS_DIR.glob(f"{rubric_id}_*"))
    if not stored_files:
        return error_response(404, "NOT_FOUND", "Rubric file not found on disk")

    path = stored_files[0]
    ext = path.suffix.lower()
    media_type = "application/pdf" if ext == ".pdf" else "text/plain"
    disposition = "inline" if ext == ".pdf" else "inline"

    return FileResponse(
        path=str(path),
        media_type=media_type,
        filename=rubric.filename,
        headers={"Content-Disposition": f'inline; filename="{rubric.filename}"'},
    )
