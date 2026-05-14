"""Tests for the auth router (register + login).

Exercises the register/login functions directly with a mocked async
session, mirroring the pattern used by test_submissions_router.py.
This guards the password_hash schema invariant that previously
escaped CI: the M4 audit found the column was missing from both
the migration and the ORM, but no test caught it because nothing
exercised the auth path.

Bcrypt is patched to a deterministic identity function so the tests
remain stable across passlib/bcrypt version skews in CI environments.
"""
from __future__ import annotations

import json
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.exc import IntegrityError

from app.routers import auth as auth_router
from app.routers.auth import login, register, LoginRequest, RegisterRequest


def _fake_hash(password: str) -> str:
    return f"hashed::{password}"


def _fake_verify(plain: str, hashed: str) -> bool:
    return hashed == _fake_hash(plain)


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


def _db_with_no_user() -> AsyncMock:
    return _db_returning(None)


class RegisterTests(unittest.IsolatedAsyncioTestCase):
    @patch.object(auth_router, "hash_password", side_effect=_fake_hash)
    async def test_register_returns_user_with_instructor_role(self, _hash) -> None:
        captured = {}

        async def fake_refresh(user):
            user.id = uuid.uuid4()

        def fake_add(user):
            captured["user"] = user

        db = AsyncMock()
        db.add = MagicMock(side_effect=fake_add)
        db.commit = AsyncMock(return_value=None)
        db.refresh = AsyncMock(side_effect=fake_refresh)

        response = await register(
            RegisterRequest(
                name="Elena Marsh",
                email="NewInstructor@Marist.edu",
                username="emarsh",
                school="Marist",
                password="hunter22",
            ),
            db=db,
        )

        payload = _payload(response)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["email"], "newinstructor@marist.edu")
        self.assertEqual(payload["data"]["name"], "Elena Marsh")
        self.assertEqual(payload["data"]["username"], "emarsh")
        self.assertEqual(payload["data"]["school"], "Marist")
        self.assertEqual(payload["data"]["role"], "Instructor")
        self.assertIn("user_id", payload["data"])
        self.assertIn("access_token", payload["data"])

        # Confirm the row that was added carries a populated password_hash —
        # this is the invariant the prior audit found was crashing at runtime
        # because the column did not exist.
        added_user = captured["user"]
        self.assertEqual(added_user.password_hash, "hashed::hunter22")
        self.assertNotEqual(added_user.password_hash, "hunter22")
        self.assertEqual(added_user.role, "Instructor")

    @patch.object(auth_router, "hash_password", side_effect=_fake_hash)
    async def test_register_duplicate_email_returns_409(self, _hash) -> None:
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock(
            side_effect=IntegrityError("INSERT", {}, Exception("duplicate"))
        )
        db.rollback = AsyncMock()

        response = await register(
            RegisterRequest(name="Taken", email="taken@marist.edu", password="hunter22"),
            db=db,
        )

        payload = _payload(response)
        self.assertFalse(payload["success"])
        self.assertEqual(response.status_code, 409)
        self.assertEqual(payload["error"]["code"], "CONFLICT")


class LoginTests(unittest.IsolatedAsyncioTestCase):
    @patch.object(auth_router, "verify_password", side_effect=_fake_verify)
    async def test_login_with_correct_password_returns_token(self, _verify) -> None:
        user = SimpleNamespace(
            id=uuid.uuid4(),
            email="elena.marsh@marist.edu",
            role="Instructor",
            password_hash=_fake_hash("hunter2"),
        )
        db = _db_returning(user)

        response = await login(
            LoginRequest(email="elena.marsh@marist.edu", password="hunter2"),
            db=db,
        )

        payload = _payload(response)
        self.assertTrue(payload["success"])
        self.assertIn("access_token", payload["data"])
        self.assertEqual(payload["data"]["token_type"], "bearer")

    @patch.object(auth_router, "verify_password", side_effect=_fake_verify)
    async def test_login_with_wrong_password_returns_401(self, _verify) -> None:
        user = SimpleNamespace(
            id=uuid.uuid4(),
            email="elena.marsh@marist.edu",
            role="Instructor",
            password_hash=_fake_hash("hunter2"),
        )
        db = _db_returning(user)

        response = await login(
            LoginRequest(email="elena.marsh@marist.edu", password="wrong"),
            db=db,
        )

        payload = _payload(response)
        self.assertFalse(payload["success"])
        self.assertEqual(response.status_code, 401)
        self.assertEqual(payload["error"]["code"], "AUTH_ERROR")

    async def test_login_with_unknown_email_returns_401(self) -> None:
        db = _db_with_no_user()

        response = await login(
            LoginRequest(email="ghost@marist.edu", password="hunter2"),
            db=db,
        )

        payload = _payload(response)
        self.assertFalse(payload["success"])
        self.assertEqual(response.status_code, 401)
        self.assertEqual(payload["error"]["code"], "AUTH_ERROR")

    async def test_login_with_user_missing_password_hash_returns_401(self) -> None:
        # Pre-pilot users may have no password_hash (manually provisioned).
        # They should not be allowed to log in.
        user = SimpleNamespace(
            id=uuid.uuid4(),
            email="legacy@marist.edu",
            role="Instructor",
            password_hash=None,
        )
        db = _db_returning(user)

        response = await login(
            LoginRequest(email="legacy@marist.edu", password="anything"),
            db=db,
        )

        payload = _payload(response)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(payload["error"]["code"], "AUTH_ERROR")
