"""Tests for M4.A.3 — gitignore secrets guard.

Defensive structural checks that enforce the design-doc §6
"Environment Management" invariants:

- .env is gitignored and NOT tracked
- .env.example IS tracked (so engineers get the template)
- No hardcoded GitHub PATs leak into tracked files
"""

import re
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class GitignoreSecretsTests(unittest.TestCase):
    def test_env_file_is_ignored(self) -> None:
        result = _run(["git", "check-ignore", "-v", ".env"])
        self.assertEqual(
            result.returncode,
            0,
            f".env must be gitignored; got stdout={result.stdout!r} stderr={result.stderr!r}",
        )

    def test_server_env_file_is_ignored(self) -> None:
        result = _run(["git", "check-ignore", "-v", "server/.env"])
        self.assertEqual(
            result.returncode,
            0,
            "server/.env must be gitignored",
        )

    def test_env_example_is_tracked(self) -> None:
        result = _run(["git", "ls-files", ".env.example"])
        self.assertTrue(
            result.stdout.strip(),
            ".env.example must be tracked so engineers get the template",
        )

    def test_no_hardcoded_github_pat_in_tracked_files(self) -> None:
        """Scan tracked files for plausible real GitHub PATs.

        Files under server/tests/ and prompts/ are allowed to contain
        shaped-but-fake tokens used to test the redactor; we also
        treat low-entropy tokens (<5 distinct chars after the prefix)
        as obvious test fixtures, not real secrets.
        """
        tracked = _run(["git", "ls-files"]).stdout.splitlines()
        pat_pattern = re.compile(r"gh[ps]_([A-Za-z0-9_]{36,})")
        allowed_prefixes = ("server/tests/", "prompts/")
        offenders: list[tuple[str, str]] = []
        for rel_path in tracked:
            if rel_path.startswith(allowed_prefixes):
                continue
            path = REPO_ROOT / rel_path
            if not path.is_file():
                continue
            if path.resolve() == Path(__file__).resolve():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except (OSError, UnicodeDecodeError):
                continue
            for match in pat_pattern.finditer(text):
                body = match.group(1)
                if len(set(body)) < 5:
                    continue  # low-entropy → obvious test fixture
                offenders.append((rel_path, match.group(0)))
        self.assertFalse(
            offenders,
            f"Plausible GitHub PAT(s) found in tracked files: {offenders}",
        )


if __name__ == "__main__":
    unittest.main()
