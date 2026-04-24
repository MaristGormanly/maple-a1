"""Tests for M4.A.4 — CORS production lock.

Ensures Settings rejects a wildcard CORS origin when APP_ENV is
"production" (per design-doc §8 milestone 4 step
"Set CORS headers (no wildcard in production)") while leaving
development and test environments unaffected.
"""

import unittest

from pydantic import ValidationError

from app.config import Settings


REQUIRED = {
    "DATABASE_URL": "postgresql+asyncpg://u:p@localhost/t",
    "SECRET_KEY": "dummy-secret",
    "GITHUB_PAT": "ghp_dummyplaceholder",
}


def _build(**overrides):
    return Settings(**{**REQUIRED, **overrides}, _env_file=None)


class CorsProductionLockTests(unittest.TestCase):
    def test_cors_rejects_wildcard_string_in_production(self) -> None:
        with self.assertRaises(ValidationError):
            _build(APP_ENV="production", CORS_ORIGINS="*")

    def test_cors_rejects_wildcard_in_list_in_production(self) -> None:
        with self.assertRaises(ValidationError):
            _build(APP_ENV="production", CORS_ORIGINS=["https://maple-a1.com", "*"])

    def test_cors_allows_specific_origin_in_production(self) -> None:
        s = _build(APP_ENV="production", CORS_ORIGINS="https://maple-a1.com")
        self.assertEqual(s.cors_origins_list, ["https://maple-a1.com"])

    def test_cors_allows_wildcard_in_development(self) -> None:
        s = _build(APP_ENV="development", CORS_ORIGINS="*")
        self.assertEqual(s.cors_origins_list, ["*"])

    def test_cors_allows_wildcard_in_test(self) -> None:
        s = _build(APP_ENV="test", CORS_ORIGINS="*")
        self.assertEqual(s.cors_origins_list, ["*"])


if __name__ == "__main__":
    unittest.main()
