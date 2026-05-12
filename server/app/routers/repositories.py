import uuid

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..middleware.auth import require_role
from ..models.database import get_db
from ..services.github_settings import GitHubSettingsError, get_required_github_pat_for_instructor
from ..utils.responses import error_response, success_response

router = APIRouter(prefix="/repositories", tags=["repositories"])


async def _get_instructor_id(current_user: dict) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(current_user["sub"]))
    except (KeyError, ValueError, TypeError):
        return None


@router.get("")
async def list_repositories(
    page: int = Query(default=1, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("Instructor")),
):
    instructor_id = await _get_instructor_id(current_user)
    if not instructor_id:
        return error_response(401, "AUTH_ERROR", "Invalid user identity in token.")

    try:
        github_pat = await get_required_github_pat_for_instructor(db, instructor_id)
    except GitHubSettingsError as exc:
        return error_response(exc.status_code, exc.code, exc.message)

    headers = {
        "Authorization": f"Bearer {github_pat}",
        "Accept": "application/vnd.github+json",
    }
    params = {
        "per_page": 100,
        "sort": "updated",
        "affiliation": "owner,collaborator,organization_member",
        "page": page,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(
                "https://api.github.com/user/repos", headers=headers, params=params
            )
        except httpx.HTTPError:
            return error_response(
                502,
                "EXTERNAL_SERVICE_ERROR",
                "Unable to reach the GitHub API to list repositories.",
            )

    if response.status_code == 401:
        return error_response(401, "AUTHENTICATION_ERROR", "Saved GitHub token is invalid or expired.")

    if response.status_code == 403:
        if response.headers.get("X-RateLimit-Remaining") == "0":
            return error_response(
                503,
                "EXTERNAL_SERVICE_ERROR",
                "GitHub API rate limit exceeded while listing repositories.",
            )
        return error_response(
            400,
            "VALIDATION_ERROR",
            "Repository list is inaccessible with the saved GitHub token.",
        )

    if response.status_code == 404:
        return error_response(
            400,
            "VALIDATION_ERROR",
            "Repository list endpoint not found. Check your GitHub token permissions.",
        )

    if response.status_code != 200:
        return error_response(
            502,
            "EXTERNAL_SERVICE_ERROR",
            "GitHub API returned an unexpected response while listing repositories.",
        )

    raw = response.json()
    repos = [
        {
            "full_name": item["full_name"],
            "name": item["name"],
            "owner": item["owner"]["login"],
            "html_url": item["html_url"],
            "description": item.get("description") or None,
            "visibility": "private" if item.get("private") else "public",
            "updated_at": item.get("updated_at") or "",
            "default_branch": item.get("default_branch") or "main",
        }
        for item in raw
    ]

    return success_response({"repositories": repos, "page": page, "count": len(repos)})
