from __future__ import annotations

import json
import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.routers.settings import (
    AccountDeleteRequest,
    AccountUpdateRequest,
    GitHubSettingsRequest,
    PasswordUpdateRequest,
    delete_account,
    delete_github_settings,
    get_account_information,
    get_github_settings,
    get_style_guide_references,
    put_github_settings,
    update_account_information,
    update_account_password,
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

    async def test_style_guide_references_returns_grouped_metadata(self) -> None:
        db = AsyncMock()
        result = MagicMock()
        result.all.return_value = [
            SimpleNamespace(
                title="PEP 8 — Style Guide for Python Code",
                document_url="https://peps.python.org/pep-0008/",
                language="python",
                version="2024-06-01",
                date_created=datetime(2026, 5, 12, 14, 30, tzinfo=timezone.utc),
            ),
            SimpleNamespace(
                title="Google JavaScript Style Guide",
                document_url="https://google.github.io/styleguide/jsguide.html",
                language="javascript",
                version="2.0",
                date_created=datetime(2026, 5, 11, 9, 0, tzinfo=timezone.utc),
            ),
        ]
        db.execute.return_value = result

        response = await get_style_guide_references(
            db=db,
            _current_user={"sub": str(uuid.uuid4()), "role": "Instructor"},
        )

        payload = _payload(response)
        self.assertTrue(payload["success"])
        self.assertEqual(len(payload["data"]["references"]), 2)
        first = payload["data"]["references"][0]
        self.assertEqual(first["title"], "PEP 8 — Style Guide for Python Code")
        self.assertEqual(first["document_url"], "https://peps.python.org/pep-0008/")
        self.assertEqual(first["language"], "python")
        self.assertEqual(first["version"], "2024-06-01")
        self.assertEqual(first["date_created"], "2026-05-12T14:30:00+00:00")
        self.assertNotIn("chunk_text", first)
        self.assertNotIn("embedding", first)

    async def test_style_guide_references_returns_empty_list(self) -> None:
        db = AsyncMock()
        result = MagicMock()
        result.all.return_value = []
        db.execute.return_value = result

        response = await get_style_guide_references(
            db=db,
            _current_user={"sub": str(uuid.uuid4()), "role": "Instructor"},
        )

        payload = _payload(response)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["references"], [])


class AccountSettingsRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_account_returns_profile_without_password_hash(self) -> None:
        user = SimpleNamespace(
            id=uuid.uuid4(),
            name="Elena Marsh",
            email="elena@marist.edu",
            username="emarsh",
            school="Marist",
            role="Instructor",
            created_at=None,
            updated_at=None,
        )

        response = await get_account_information(
            db=_db_returning(user),
            current_user={"sub": str(user.id), "role": "Instructor"},
        )

        payload = _payload(response)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["name"], "Elena Marsh")
        self.assertEqual(payload["data"]["email"], "elena@marist.edu")
        self.assertNotIn("password_hash", payload["data"])

    async def test_update_account_saves_profile_fields(self) -> None:
        user = SimpleNamespace(
            id=uuid.uuid4(),
            name="Elena Marsh",
            email="old@marist.edu",
            username="oldname",
            school=None,
            role="Instructor",
            created_at=None,
            updated_at=None,
        )
        db = AsyncMock()
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = user
        conflict_result = MagicMock()
        conflict_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(side_effect=[user_result, conflict_result])
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        response = await update_account_information(
            AccountUpdateRequest(
                name="Elena M.",
                email="New@Marist.edu",
                username="newname",
                school="School of CS",
            ),
            db=db,
            current_user={"sub": str(user.id), "role": "Instructor"},
        )

        payload = _payload(response)
        self.assertTrue(payload["success"])
        self.assertEqual(user.name, "Elena M.")
        self.assertEqual(user.email, "new@marist.edu")
        self.assertEqual(user.username, "newname")
        self.assertEqual(user.school, "School of CS")

    @patch("app.routers.settings.hash_password", side_effect=lambda p: f"hashed::{p}")
    @patch("app.routers.settings.verify_password", return_value=True)
    async def test_update_password_requires_current_password(self, _verify, _hash) -> None:
        user = SimpleNamespace(
            id=uuid.uuid4(),
            email="elena@marist.edu",
            role="Instructor",
            password_hash="hashed::oldpassword",
        )
        db = _db_returning(user)
        db.commit = AsyncMock()

        response = await update_account_password(
            PasswordUpdateRequest(
                current_password="oldpassword",
                new_password="newpassword",
            ),
            db=db,
            current_user={"sub": str(user.id), "role": "Instructor"},
        )

        payload = _payload(response)
        self.assertTrue(payload["success"])
        self.assertTrue(payload["data"]["updated"])
        self.assertEqual(user.password_hash, "hashed::newpassword")

    async def test_delete_account_requires_confirmation_text(self) -> None:
        user = SimpleNamespace(id=uuid.uuid4(), email="elena@marist.edu", role="Instructor")

        response = await delete_account(
            AccountDeleteRequest(confirmation="delete"),
            db=_db_returning(user),
            current_user={"sub": str(user.id), "role": "Instructor"},
        )

        payload = _payload(response)
        self.assertFalse(payload["success"])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(payload["error"]["code"], "VALIDATION_ERROR")

    async def test_delete_account_deletes_current_user(self) -> None:
        user = SimpleNamespace(id=uuid.uuid4(), email="elena@marist.edu", role="Instructor")
        db = AsyncMock()
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = user
        rubric_result = MagicMock()
        rubric_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(side_effect=[user_result, rubric_result])
        db.delete = AsyncMock()
        db.commit = AsyncMock()

        response = await delete_account(
            AccountDeleteRequest(confirmation="I want to delete my account"),
            db=db,
            current_user={"sub": str(user.id), "role": "Instructor"},
        )

        payload = _payload(response)
        self.assertTrue(payload["success"])
        db.delete.assert_awaited_once_with(user)
        db.commit.assert_awaited_once()


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
