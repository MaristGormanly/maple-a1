from __future__ import annotations

import json
import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.routers.settings import (
    GitHubSettingsRequest,
    delete_github_settings,
    get_github_settings,
    put_github_settings,
)
from app.services.github_settings import GitHubSettingsError, get_required_github_pat_for_instructor


def _payload(response) -> dict:
    if isinstance(response, dict):
        return response
    return json.loads(response.body)


def _db_returning(user) -> AsyncMock:
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db.execute.return_value = result
    return db


class GitHubSettingsRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_returns_metadata_without_plaintext_token(self) -> None:
        user = SimpleNamespace(
            id=uuid.uuid4(),
            github_username="instructor",
            github_pat_encrypted="encrypted-token",
            github_token_updated_at=datetime(2026, 5, 9, tzinfo=timezone.utc),
        )
        response = await get_github_settings(
            db=_db_returning(user),
            current_user={"sub": str(user.id), "role": "Instructor"},
        )

        payload = _payload(response)
        self.assertTrue(payload["success"])
        self.assertTrue(payload["data"]["connected"])
        self.assertEqual(payload["data"]["github_username"], "instructor")
        self.assertIn("last_updated_at", payload["data"])
        self.assertNotIn("personal_access_token", payload["data"])
        self.assertNotIn("github_pat_encrypted", payload["data"])

    @patch("app.services.github_settings.encrypt_github_token", return_value="encrypted-token")
    @patch("app.services.github_settings.validate_github_token", new_callable=AsyncMock)
    async def test_put_validates_and_stores_encrypted_token(self, validate_mock, _encrypt) -> None:
        validate_mock.return_value = "instructor"
        user = SimpleNamespace(
            id=uuid.uuid4(),
            github_username=None,
            github_pat_encrypted=None,
            github_pat_hash=None,
            github_token_updated_at=None,
        )
        db = _db_returning(user)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        response = await put_github_settings(
            GitHubSettingsRequest(
                github_username="instructor",
                personal_access_token="github_pat_secret",
            ),
            db=db,
            current_user={"sub": str(user.id), "role": "Instructor"},
        )

        payload = _payload(response)
        self.assertTrue(payload["success"])
        self.assertTrue(payload["data"]["connected"])
        self.assertEqual(user.github_pat_encrypted, "encrypted-token")
        self.assertNotEqual(user.github_pat_hash, "github_pat_secret")
        self.assertNotIn("github_pat_secret", json.dumps(payload))
        validate_mock.assert_awaited_once_with("github_pat_secret")

    async def test_delete_clears_token_fields(self) -> None:
        user = SimpleNamespace(
            id=uuid.uuid4(),
            github_username="instructor",
            github_pat_encrypted="encrypted-token",
            github_pat_hash="hash",
            github_token_updated_at=datetime.now(timezone.utc),
        )
        db = _db_returning(user)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        response = await delete_github_settings(
            db=db,
            current_user={"sub": str(user.id), "role": "Instructor"},
        )

        payload = _payload(response)
        self.assertTrue(payload["success"])
        self.assertFalse(payload["data"]["connected"])
        self.assertIsNone(user.github_pat_encrypted)
        self.assertIsNone(user.github_pat_hash)

    @patch("app.services.github_settings.validate_github_token", new_callable=AsyncMock)
    async def test_put_rejects_replacement_when_token_exists(self, validate_mock) -> None:
        user = SimpleNamespace(
            id=uuid.uuid4(),
            github_username="instructor",
            github_pat_encrypted="encrypted-token",
            github_pat_hash="hash",
            github_token_updated_at=datetime.now(timezone.utc),
        )

        response = await put_github_settings(
            GitHubSettingsRequest(
                github_username="instructor",
                personal_access_token="github_pat_replacement",
            ),
            db=_db_returning(user),
            current_user={"sub": str(user.id), "role": "Instructor"},
        )

        payload = _payload(response)
        self.assertEqual(response.status_code, 409)
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error"]["code"], "CONFLICT")
        self.assertEqual(payload["error"]["message"], "Delete the existing GitHub key before saving a new one.")
        validate_mock.assert_not_awaited()


class GitHubSettingsServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_required_pat_fails_clearly_when_unset(self) -> None:
        user = SimpleNamespace(
            id=uuid.uuid4(),
            github_pat_encrypted=None,
        )

        with self.assertRaises(GitHubSettingsError) as ctx:
            await get_required_github_pat_for_instructor(_db_returning(user), user.id)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.code, "VALIDATION_ERROR")
        self.assertIn("GitHub connection is not configured", ctx.exception.message)
