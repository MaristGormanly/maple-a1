"""Structural test for M4.D.3 — app-level rollback runbook.

Asserts docs/deployment.md contains an App-level rollback section
with the essential commands a Team Lead needs during a pilot
incident. Structural-only test to prevent doc rot.
"""

import re
import unittest
from pathlib import Path


DEPLOYMENT_DOC = Path(__file__).resolve().parents[2] / "docs" / "deployment.md"


class RollbackRunbookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.content = DEPLOYMENT_DOC.read_text(encoding="utf-8")

    def test_doc_exists(self) -> None:
        self.assertTrue(DEPLOYMENT_DOC.exists(), f"missing: {DEPLOYMENT_DOC}")

    def test_app_level_rollback_section_present(self) -> None:
        self.assertRegex(
            self.content,
            r"(?m)^##\s+App-level rollback\b",
            "docs/deployment.md must contain an '## App-level rollback' section",
        )

    def test_rollback_mentions_git_revert(self) -> None:
        section = self._extract_rollback_section()
        self.assertIn("git revert", section)

    def test_rollback_mentions_systemctl_restart(self) -> None:
        section = self._extract_rollback_section()
        self.assertIn("systemctl restart maple-a1", section)

    def test_rollback_mentions_verification(self) -> None:
        section = self._extract_rollback_section()
        self.assertRegex(
            section,
            r"(curl|health|journalctl)",
            "rollback section must document a verification step",
        )

    def test_rollback_requires_team_lead_signoff(self) -> None:
        section = self._extract_rollback_section()
        self.assertRegex(
            section,
            r"(?i)(team\s*lead|authoriz)",
            "rollback section must note Team Lead authorization (per 4.D.3)",
        )

    def _extract_rollback_section(self) -> str:
        match = re.search(
            r"(?ms)^##\s+App-level rollback\b.*?(?=^##\s+|\Z)",
            self.content,
        )
        self.assertIsNotNone(match, "App-level rollback section not found")
        return match.group(0)


if __name__ == "__main__":
    unittest.main()
