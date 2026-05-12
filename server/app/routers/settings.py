import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..middleware.auth import require_role
from ..models.database import get_db
from ..models.style_guide_chunk import StyleGuideChunk
from ..services.github_settings import (
    GitHubSettingsError,
    clear_github_settings,
    get_user,
    github_settings_payload,
    store_github_settings,
)
from ..utils.responses import error_response, success_response

router = APIRouter(prefix="/settings", tags=["settings"])


class GitHubSettingsRequest(BaseModel):
    github_username: str | None = Field(default=None, max_length=120)
    personal_access_token: str = Field(min_length=1, max_length=512)


async def _current_instructor(db: AsyncSession, current_user: dict):
    try:
        user_id = uuid.UUID(str(current_user["sub"]))
    except (KeyError, ValueError, TypeError):
        return None
    return await get_user(db, user_id)


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
