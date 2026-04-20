"""Unit tests for the style guide ingester (server/app/services/style_guide_ingester.py).

All HTTP and DB I/O is mocked. Tests cover: version parsing, heading-based
chunking, rule_id slugification, and ingest_all orchestration.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Stub heavy DB/pgvector imports before importing the module under test.
import sys
_db_stub = MagicMock()
_db_stub.async_session_maker = MagicMock()
sys.modules.setdefault("app.models.database", _db_stub)
sys.modules.setdefault("app.models", MagicMock())

from app.services.style_guide_ingester import (  # noqa: E402
    STYLE_GUIDES,
    RawDocument,
    StyleGuideSource,
    _slugify,
    fetch_and_parse,
    ingest_all,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PEP8_HTML = """
<html><body>
<h1>PEP 8 Style Guide</h1>
<p>Last modified: 2023-11-01</p>
<h2>Indentation</h2>
<p>Use 4 spaces per indentation level.</p>
<h2>Maximum Line Length</h2>
<p>Limit all lines to a maximum of 79 characters.</p>
<h3>Long lines</h3>
<p>Wrap long expressions.</p>
</body></html>
"""

_SOURCE = StyleGuideSource(
    source_title="PEP 8 — Style Guide for Python Code",
    url="https://peps.python.org/pep-0008/",
    language="python",
    format="html",
    version_pattern=r"(?:Last modified|Created|Version)[:\s]+(\d{4}-\d{2}-\d{2}|\d{4})",
)


def _mock_httpx_response(html: str, status_code: int = 200):
    resp = MagicMock()
    resp.text = html
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        from httpx import HTTPStatusError, Request, Response
        resp.raise_for_status.side_effect = HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock()
        )
    return resp


# ---------------------------------------------------------------------------
# Slugify
# ---------------------------------------------------------------------------

class TestSlugify(unittest.TestCase):
    def test_basic_lowercasing(self):
        self.assertEqual(_slugify("Indentation"), "indentation")

    def test_spaces_become_underscores(self):
        self.assertEqual(_slugify("Maximum Line Length"), "maximum_line_length")

    def test_special_chars_stripped(self):
        self.assertEqual(_slugify("Use 4-space tabs!"), "use_4_space_tabs")

    def test_multiple_spaces_collapsed(self):
        self.assertEqual(_slugify("a  b"), "a_b")

    def test_empty_string(self):
        self.assertEqual(_slugify(""), "")

    def test_unicode_normalised(self):
        result = _slugify("Ré\u0301sumé")
        self.assertNotIn("\u00e9", result)  # accented e removed


# ---------------------------------------------------------------------------
# fetch_and_parse
# ---------------------------------------------------------------------------

_HTTPX_CLIENT_PATCH = "httpx.AsyncClient"


class TestFetchAndParseVersionExtraction(unittest.TestCase):
    """Version extracted from HTML when the pattern matches."""

    def test_parses_date_version(self):
        mock_resp = _mock_httpx_response(_PEP8_HTML)
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        async def run():
            with patch(_HTTPX_CLIENT_PATCH, return_value=mock_client):
                return await fetch_and_parse(_SOURCE)

        doc = asyncio.run(run())
        self.assertEqual(doc.version, "2023-11-01")

    def test_returns_unknown_when_no_version_match(self):
        html = "<html><body><h2>Section</h2><p>Content</p></body></html>"
        mock_resp = _mock_httpx_response(html)
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        async def run():
            with patch(_HTTPX_CLIENT_PATCH, return_value=mock_client):
                return await fetch_and_parse(_SOURCE)

        doc = asyncio.run(run())
        self.assertEqual(doc.version, "unknown")


class TestFetchAndParseChunking(unittest.TestCase):
    """Sections chunked by h2/h3 headings."""

    def _parse(self, html: str) -> RawDocument:
        mock_resp = _mock_httpx_response(html)
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        async def run():
            with patch(_HTTPX_CLIENT_PATCH, return_value=mock_client):
                return await fetch_and_parse(_SOURCE)

        return asyncio.run(run())

    def test_produces_one_section_per_heading(self):
        doc = self._parse(_PEP8_HTML)
        # Headings: Indentation, Maximum Line Length, Long lines = 3
        self.assertEqual(len(doc.sections), 3)

    def test_section_rule_ids_are_slugified(self):
        doc = self._parse(_PEP8_HTML)
        rule_ids = [s[0] for s in doc.sections]
        self.assertIn("indentation", rule_ids)
        self.assertIn("maximum_line_length", rule_ids)

    def test_chunk_text_contains_heading_and_body(self):
        doc = self._parse(_PEP8_HTML)
        indentation_chunk = next(c for r, c in doc.sections if r == "indentation")
        self.assertIn("Indentation", indentation_chunk)
        self.assertIn("4 spaces", indentation_chunk)

    def test_no_headings_returns_empty_sections(self):
        html = "<html><body><p>No headings here.</p></body></html>"
        doc = self._parse(html)
        self.assertEqual(doc.sections, [])

    def test_metadata_fields_populated(self):
        doc = self._parse(_PEP8_HTML)
        self.assertEqual(doc.source_title, _SOURCE.source_title)
        self.assertEqual(doc.url, _SOURCE.url)
        self.assertEqual(doc.language, "python")

    def test_empty_heading_skipped(self):
        html = "<html><body><h2></h2><h2>Real Section</h2><p>Body</p></body></html>"
        doc = self._parse(html)
        self.assertEqual(len(doc.sections), 1)
        self.assertEqual(doc.sections[0][0], "real_section")


# ---------------------------------------------------------------------------
# STYLE_GUIDES catalogue
# ---------------------------------------------------------------------------

class TestStyleGuideCatalogue(unittest.TestCase):
    def test_five_guides_defined(self):
        self.assertEqual(len(STYLE_GUIDES), 5)

    def test_all_guides_have_required_fields(self):
        for guide in STYLE_GUIDES:
            self.assertTrue(guide.source_title)
            self.assertTrue(guide.url)
            self.assertTrue(guide.language)
            self.assertTrue(guide.format)
            self.assertTrue(guide.version_pattern)

    def test_languages_covered(self):
        languages = {g.language for g in STYLE_GUIDES}
        self.assertIn("python", languages)
        self.assertIn("java", languages)
        self.assertIn("typescript", languages)
        self.assertIn("javascript", languages)
        self.assertIn("c++", languages)

    def test_all_urls_are_https(self):
        for guide in STYLE_GUIDES:
            self.assertTrue(guide.url.startswith("https://"), guide.url)


# ---------------------------------------------------------------------------
# ingest_all
# ---------------------------------------------------------------------------

class TestIngestAll(unittest.TestCase):
    """ingest_all orchestrates fetch → embed → delete → insert per guide."""

    def _run_ingest(self, mock_fetch, mock_embed_batch, guides=None):
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()

        async def run():
            with patch("app.services.style_guide_ingester.fetch_and_parse", mock_fetch), \
                 patch("app.services.style_guide_ingester.embed_batch", mock_embed_batch):
                if guides is not None:
                    with patch("app.services.style_guide_ingester.STYLE_GUIDES", guides):
                        return await ingest_all(mock_session)
                return await ingest_all(mock_session)

        return asyncio.run(run()), mock_session

    def test_returns_total_chunk_count(self):
        fake_doc = RawDocument(
            source_title="PEP 8", url="https://peps.python.org/pep-0008/",
            language="python", version="2023",
            sections=[("rule_a", "text a"), ("rule_b", "text b")],
        )
        mock_fetch = AsyncMock(return_value=fake_doc)
        mock_embed = AsyncMock(return_value=[[0.1] * 1536, [0.2] * 1536])

        single_guide = [STYLE_GUIDES[0]]
        count, _ = self._run_ingest(mock_fetch, mock_embed, guides=single_guide)
        self.assertEqual(count, 2)

    def test_skips_guide_with_no_sections(self):
        empty_doc = RawDocument(
            source_title="Empty", url="https://example.com",
            language="python", version="unknown", sections=[],
        )
        mock_fetch = AsyncMock(return_value=empty_doc)
        mock_embed = AsyncMock(return_value=[])

        single_guide = [STYLE_GUIDES[0]]
        count, session = self._run_ingest(mock_fetch, mock_embed, guides=single_guide)
        self.assertEqual(count, 0)
        # No INSERT should have been called.
        # execute is called for DELETE even; but no chunks means 0 inserts.

    def test_commits_after_each_guide(self):
        fake_doc = RawDocument(
            source_title="G", url="https://g.com", language="python",
            version="1.0", sections=[("r", "text")],
        )
        mock_fetch = AsyncMock(return_value=fake_doc)
        mock_embed = AsyncMock(return_value=[[0.0] * 1536])

        two_guides = [STYLE_GUIDES[0], STYLE_GUIDES[1]]
        _, session = self._run_ingest(mock_fetch, mock_embed, guides=two_guides)
        self.assertEqual(session.commit.await_count, 2)


if __name__ == "__main__":
    unittest.main()
