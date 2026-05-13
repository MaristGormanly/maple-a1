import uuid
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..middleware.auth import require_role
from ..models.database import get_db
from ..models.rubric import Rubric
from ..models.style_guide_chunk import StyleGuideChunk
from ..models.user import User
from ..services.github_settings import (
    GitHubSettingsError,
    clear_github_settings,
    get_user,
    github_settings_payload,
    store_github_settings,
)
from ..utils.responses import error_response, success_response
from ..utils.security import hash_password, verify_password

router = APIRouter(prefix="/settings", tags=["settings"])
_UPLOADS_DIR = Path(__file__).resolve().parents[3] / "uploads" / "rubrics"
_DELETE_CONFIRMATION = "I want to delete my account"


class GitHubSettingsRequest(BaseModel):
    github_username: str | None = Field(default=None, max_length=120)
    personal_access_token: str = Field(min_length=1, max_length=512)


class AccountUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    email: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=80)
    school: str | None = Field(default=None, max_length=160)

    @field_validator("name", "email", "username", "school")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class PasswordUpdateRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class AccountDeleteRequest(BaseModel):
    confirmation: str


async def _current_instructor(db: AsyncSession, current_user: dict):
    try:
        user_id = uuid.UUID(str(current_user["sub"]))
    except (KeyError, ValueError, TypeError):
        return None
    return await get_user(db, user_id)


def _account_payload(user: User) -> dict:
    return {
        "user_id": str(user.id),
        "name": getattr(user, "name", None),
        "email": user.email,
        "username": getattr(user, "username", None),
        "school": getattr(user, "school", None),
        "role": user.role,
        "created_at": user.created_at.isoformat() if getattr(user, "created_at", None) else None,
        "updated_at": user.updated_at.isoformat() if getattr(user, "updated_at", None) else None,
    }


def _normalize_email(email: str | None) -> str | None:
    if email is None:
        return None
    normalized = email.strip().lower()
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise ValueError("Enter a valid email address.")
    return normalized


def _normalize_username(username: str | None) -> str | None:
    if username is None:
        return None
    normalized = username.strip().lower()
    if not normalized:
        return None
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if len(normalized) < 3 or any(ch not in allowed for ch in normalized):
        raise ValueError("Username must be 3-80 letters, numbers, dots, dashes, or underscores.")
    return normalized


async def _has_account_conflict(
    db: AsyncSession,
    user: User,
    *,
    email: str | None,
    username: str | None,
) -> bool:
    clauses = []
    if email and email != user.email:
        clauses.append(func.lower(User.email) == email)
    if username and username != getattr(user, "username", None):
        clauses.append(func.lower(User.username) == username)
    if not clauses:
        return False
    result = await db.execute(select(User.id).where(User.id != user.id, or_(*clauses)).limit(1))
    return result.scalar_one_or_none() is not None


@router.get("/github")
async def get_github_settings(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("Instructor")),
):
    user = await _current_instructor(db, current_user)
    if not user:
        return error_response(401, "AUTH_ERROR", "Invalid user identity in token.")
    return success_response(github_settings_payload(user))


@router.put("/github")
async def put_github_settings(
    request: GitHubSettingsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("Instructor")),
):
    user = await _current_instructor(db, current_user)
    if not user:
        return error_response(401, "AUTH_ERROR", "Invalid user identity in token.")
    try:
        payload = await store_github_settings(
            db,
            user,
            github_username=request.github_username,
            token=request.personal_access_token,
        )
    except GitHubSettingsError as exc:
        return error_response(exc.status_code, exc.code, exc.message)
    return success_response(payload)


@router.delete("/github")
async def delete_github_settings(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("Instructor")),
):
    user = await _current_instructor(db, current_user)
    if not user:
        return error_response(401, "AUTH_ERROR", "Invalid user identity in token.")
    payload = await clear_github_settings(db, user)
    return success_response(payload)


@router.get("/account")
async def get_account_information(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("Instructor")),
):
    user = await _current_instructor(db, current_user)
    if not user:
        return error_response(401, "AUTH_ERROR", "Invalid user identity in token.")
    return success_response(_account_payload(user))


@router.patch("/account")
async def update_account_information(
    request: AccountUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("Instructor")),
):
    user = await _current_instructor(db, current_user)
    if not user:
        return error_response(401, "AUTH_ERROR", "Invalid user identity in token.")

    fields = request.model_fields_set
    try:
        email = _normalize_email(request.email) if "email" in fields else user.email
        username = (
            _normalize_username(request.username)
            if "username" in fields
            else getattr(user, "username", None)
        )
    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc))

    if await _has_account_conflict(db, user, email=email, username=username):
        return error_response(409, "CONFLICT", "A user with that email or username already exists.")

    if "name" in fields:
        if not request.name:
            return error_response(400, "VALIDATION_ERROR", "Name is required.")
        user.name = request.name
    user.email = email
    user.username = username
    if "school" in fields:
        user.school = request.school

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return error_response(409, "CONFLICT", "A user with that email or username already exists.")
    await db.refresh(user)
    return success_response(_account_payload(user))


@router.patch("/account/password")
async def update_account_password(
    request: PasswordUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("Instructor")),
):
    user = await _current_instructor(db, current_user)
    if not user:
        return error_response(401, "AUTH_ERROR", "Invalid user identity in token.")
    if not user.password_hash or not verify_password(request.current_password, user.password_hash):
        return error_response(401, "AUTH_ERROR", "Current password is incorrect.")

    user.password_hash = hash_password(request.new_password)
    await db.commit()
    return success_response({"updated": True})


@router.delete("/account")
async def delete_account(
    request: AccountDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("Instructor")),
):
    user = await _current_instructor(db, current_user)
    if not user:
        return error_response(401, "AUTH_ERROR", "Invalid user identity in token.")
    if request.confirmation != _DELETE_CONFIRMATION:
        return error_response(
            400,
            "VALIDATION_ERROR",
            f'Type "{_DELETE_CONFIRMATION}" to delete this account.',
        )

    result = await db.execute(select(Rubric.id).where(Rubric.instructor_id == user.id))
    rubric_ids = [str(rid) for rid in result.scalars().all()]
    for rubric_id in rubric_ids:
        for path in _UPLOADS_DIR.glob(f"{rubric_id}_*"):
            path.unlink(missing_ok=True)

    await db.delete(user)
    await db.commit()
    return success_response({"deleted": str(user.id)})


@router.get("/style-guide-references")
async def get_style_guide_references(
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_role("Instructor")),
):
    result = await db.execute(
        select(
            StyleGuideChunk.source_title.label("title"),
            StyleGuideChunk.source_url.label("document_url"),
            StyleGuideChunk.language.label("language"),
            StyleGuideChunk.style_guide_version.label("version"),
            func.max(StyleGuideChunk.last_fetched).label("date_created"),
        )
        .group_by(
            StyleGuideChunk.source_title,
            StyleGuideChunk.source_url,
            StyleGuideChunk.language,
            StyleGuideChunk.style_guide_version,
        )
        .order_by(StyleGuideChunk.language, StyleGuideChunk.source_title)
    )

    references = [
        {
            "title": row.title,
            "document_url": row.document_url,
            "language": row.language,
            "version": row.version,
            "date_created": row.date_created.isoformat() if row.date_created else None,
        }
        for row in result.all()
    ]

    return success_response({"references": references})
