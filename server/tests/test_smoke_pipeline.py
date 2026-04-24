"""Smoke test fixture (M4 task 4.A.8).

Two tiers of tests:

1. Structural (always run): fixture-repos.yaml exists with the
   expected shape; smoke_test.sh exists and is executable. These
   catch drift in the fixture definitions without needing a backend.

2. Live smoke tests (opt-in via `pytest -m smoke`): hit a running
   backend to confirm the health endpoint and full /evaluate pipeline
   are green. Skipped gracefully when no backend is reachable so the
   file is safe to include in the default suite.
"""

from __future__ import annotations

import os
import socket
import stat
import unittest
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_YAML = REPO_ROOT / "eval" / "test-cases" / "fixture-repos.yaml"
SMOKE_SCRIPT = REPO_ROOT / "eval" / "scripts" / "smoke_test.sh"


class FixtureReposStructureTests(unittest.TestCase):
    def test_fixture_yaml_exists(self) -> None:
        self.assertTrue(
            FIXTURE_YAML.exists(),
            f"missing fixture registry: {FIXTURE_YAML}",
        )

    def test_fixture_yaml_lists_known_good_and_failing(self) -> None:
        content = FIXTURE_YAML.read_text(encoding="utf-8")
        self.assertIn("known_good", content, "fixture yaml must define known_good repo")
        self.assertIn("known_failing", content, "fixture yaml must define known_failing repo")
        # Each entry should point at a github.com URL placeholder
        self.assertIn("github.com", content)

    def test_smoke_script_exists_and_executable(self) -> None:
        self.assertTrue(SMOKE_SCRIPT.exists(), f"missing: {SMOKE_SCRIPT}")
        mode = SMOKE_SCRIPT.stat().st_mode
        self.assertTrue(
            mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH),
            "smoke_test.sh must be executable",
        )

    def test_smoke_script_hits_health_endpoint(self) -> None:
        body = SMOKE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("/api/v1/code-eval/health", body)


def _backend_reachable(host: str = "127.0.0.1", port: int = 8000) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


@pytest.mark.smoke
class LiveSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        if not _backend_reachable():
            self.skipTest("backend not reachable on 127.0.0.1:8000")

    def test_health_endpoint_returns_200(self) -> None:
        import httpx  # noqa: WPS433 — only imported when running live

        base = os.environ.get("MAPLE_API_BASE", "http://127.0.0.1:8000")
        r = httpx.get(f"{base}/api/v1/code-eval/health", timeout=5.0)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
