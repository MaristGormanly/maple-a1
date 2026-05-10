from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.user import User


class GitHubSettingsError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def _fernet() -> Fernet:
    key = settings.GITHUB_TOKEN_ENCRYPTION_KEY.strip()
    if not key:
        raise GitHubSettingsError(
            500,
            "CONFIGURATION_ERROR",
            "GITHUB_TOKEN_ENCRYPTION_KEY is not configured.",
        )
    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise GitHubSettingsError(
            500,
            "CONFIGURATION_ERROR",
            "GITHUB_TOKEN_ENCRYPTION_KEY must be a valid Fernet key.",
        ) from exc


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def encrypt_github_token(token: str) -> str:
    return _fernet().encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt_github_token(encrypted_token: str) -> str:
    try:
        return _fernet().decrypt(encrypted_token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise GitHubSettingsError(
            500,
            "CONFIGURATION_ERROR",
            "Stored GitHub token could not be decrypted. Check GITHUB_TOKEN_ENCRYPTION_KEY.",
        ) from exc


async def validate_github_token(token: str) -> str:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get("https://api.github.com/user", headers=headers)
        except httpx.HTTPError as exc:
            raise GitHubSettingsError(
                502,
                "EXTERNAL_SERVICE_ERROR",
                "Unable to reach the GitHub API to validate the token.",
            ) from exc

    if response.status_code == 401:
        raise GitHubSettingsError(
            401,
            "AUTHENTICATION_ERROR",
            "GitHub token is invalid or expired.",
        )
    if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
        raise GitHubSettingsError(
            503,
            "EXTERNAL_SERVICE_ERROR",
            "GitHub API rate limit exceeded while validating the token.",
        )
    if response.status_code != 200:
        raise GitHubSettingsError(
            502,
            "EXTERNAL_SERVICE_ERROR",
            "GitHub API returned an unexpected response while validating the token.",
        )

    login = str(response.json().get("login") or "").strip()
    if not login:
        raise GitHubSettingsError(
            502,
            "EXTERNAL_SERVICE_ERROR",
            "GitHub API did not return a username for the token.",
        )
    return login


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


def github_settings_payload(user: User) -> dict:
    return {
        "connected": bool(user.github_pat_encrypted),
        "github_username": user.github_username,
        "last_updated_at": (
            user.github_token_updated_at.isoformat()
            if user.github_token_updated_at
            else None
        ),
    }


async def store_github_settings(
    db: AsyncSession,
    user: User,
    *,
    github_username: str | None,
    token: str,
) -> dict:
    if user.github_pat_encrypted:
        raise GitHubSettingsError(
            409,
            "CONFLICT",
            "Delete the existing GitHub key before saving a new one.",
        )

    token = token.strip()
    if not token:
        raise GitHubSettingsError(400, "VALIDATION_ERROR", "personal_access_token is required.")

    token_login = await validate_github_token(token)
    requested_username = github_username.strip() if github_username else ""
    if requested_username and requested_username.lower() != token_login.lower():
        raise GitHubSettingsError(
            400,
            "VALIDATION_ERROR",
            "GitHub username does not match the token owner.",
        )

    user.github_username = requested_username or token_login
    user.github_pat_encrypted = encrypt_github_token(token)
    user.github_pat_hash = _hash_token(token)
    user.github_token_updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return github_settings_payload(user)


async def clear_github_settings(db: AsyncSession, user: User) -> dict:
    user.github_username = None
    user.github_pat_encrypted = None
    user.github_pat_hash = None
    user.github_token_updated_at = None
    await db.commit()
    await db.refresh(user)
    return github_settings_payload(user)


async def get_required_github_pat_for_instructor(
    db: AsyncSession,
    instructor_id: uuid.UUID,
) -> str:
    user = await get_user(db, instructor_id)
    if not user:
        raise GitHubSettingsError(401, "AUTH_ERROR", "Invalid user identity in token.")
    if not user.github_pat_encrypted:
        raise GitHubSettingsError(
            400,
            "VALIDATION_ERROR",
            "GitHub connection is not configured. Open Settings and save a Personal Access Token.",
        )
    return decrypt_github_token(user.github_pat_encrypted)
