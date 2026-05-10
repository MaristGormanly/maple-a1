import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..middleware.auth import require_role
from ..models.database import get_db
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
