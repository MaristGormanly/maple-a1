"""Unit tests for the RAG retriever service (server/app/services/rag_retriever.py).

All database and embedding calls are mocked; no real network or DB required.
app.models.database is stubbed at the module level so no pgvector or DB
connection is required at import time.
"""

import asyncio
import json
import logging
import sys
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Stub out app.models.database before rag_retriever is imported.
# This prevents SQLAlchemy from trying to resolve the pgvector Vector type
# during class body execution of StyleGuideChunk.
# ---------------------------------------------------------------------------
_db_mock = MagicMock()
sys.modules.setdefault("app.models.database", _db_mock)
sys.modules.setdefault("app.models", MagicMock())

from app.services.rag_retriever import StyleChunkHit, retrieve_style_chunks  # noqa: E402


_EMBED_PATCH = "app.services.rag_retriever.embed_text"
_SESSION_MAKER_PATCH = "app.services.rag_retriever.async_session_maker"


def _make_row(cosine_sim: float) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        source_title="PEP 8",
        source_url="https://peps.python.org/pep-0008/",
        style_guide_version="2023-01",
        rule_id="E302",
        chunk_text="Use 2 blank lines between top-level definitions.",
        cosine_sim=cosine_sim,
    )


def _make_session_maker(rows: list):
    """Build a mock async_session_maker context manager that returns *rows* from fetchall()."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = rows

    mock_execute = AsyncMock(return_value=mock_result)

    mock_session = AsyncMock()
    mock_session.execute = mock_execute

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    mock_session_maker = MagicMock(return_value=mock_cm)
    return mock_session_maker, mock_session


class TestRetrieveReturnsHitsAboveThreshold(unittest.TestCase):
    """Only rows with cosine_sim >= 0.75 (default threshold) are returned."""

    def test_retrieve_returns_hits_above_threshold(self):
        rows = [_make_row(0.9), _make_row(0.5)]
        mock_session_maker, _ = _make_session_maker(rows)

        async def _run():
            with patch(_EMBED_PATCH, new=AsyncMock(return_value=[0.1] * 3072)):
                with patch(_SESSION_MAKER_PATCH, mock_session_maker):
                    return await retrieve_style_chunks("docstring style", "python")

        hits = asyncio.run(_run())

        self.assertEqual(len(hits), 1)
        self.assertIsInstance(hits[0], StyleChunkHit)
        self.assertAlmostEqual(hits[0].cosine_sim, 0.9)


class TestRetrieveNoMatchLogsAndReturnsEmpty(unittest.TestCase):
    """When no rows exceed threshold, returns [] and logs retrieval_status: no_match."""

    def test_retrieve_no_match_logs_and_returns_empty(self):
        rows = [_make_row(0.5), _make_row(0.6)]
        mock_session_maker, _ = _make_session_maker(rows)

        logged_messages: list[str] = []

        class CapturingHandler(logging.Handler):
            def emit(self, record):
                logged_messages.append(self.format(record))

        handler = CapturingHandler()
        rag_logger = logging.getLogger("app.services.rag_retriever")
        rag_logger.addHandler(handler)
        original_level = rag_logger.level
        rag_logger.setLevel(logging.DEBUG)

        try:
            async def _run():
                with patch(_EMBED_PATCH, new=AsyncMock(return_value=[0.1] * 3072)):
                    with patch(_SESSION_MAKER_PATCH, mock_session_maker):
                        return await retrieve_style_chunks("docstring style", "python")

            hits = asyncio.run(_run())
        finally:
            rag_logger.removeHandler(handler)
            rag_logger.setLevel(original_level)

        self.assertEqual(hits, [])

        no_match_logged = any("no_match" in msg for msg in logged_messages)
        self.assertTrue(no_match_logged, f"Expected 'no_match' in logs; got: {logged_messages}")


class TestRetrieveRedactsQuery(unittest.TestCase):
    """Email addresses in the query text are redacted before embed_text is called."""

    def test_retrieve_redacts_query(self):
        rows = [_make_row(0.9)]
        mock_session_maker, _ = _make_session_maker(rows)
        captured_text: list[str] = []

        async def fake_embed(text: str):
            captured_text.append(text)
            return [0.1] * 3072

        email_addr = "instructor@university.edu"

        async def _run():
            with patch(_EMBED_PATCH, new=fake_embed):
                with patch(_SESSION_MAKER_PATCH, mock_session_maker):
                    return await retrieve_style_chunks(
                        f"Review code by {email_addr}", "python"
                    )

        asyncio.run(_run())

        self.assertTrue(captured_text, "embed_text should have been called")
        self.assertNotIn(email_addr, captured_text[0])
        self.assertIn("[REDACTED_EMAIL]", captured_text[0])


class TestRetrieveAppliesLanguageFilter(unittest.TestCase):
    """The 'lang' SQL parameter must match the requested language."""

    def test_retrieve_applies_language_filter(self):
        rows: list = []
        mock_session_maker, mock_session = _make_session_maker(rows)
        requested_language = "javascript"

        async def _run():
            with patch(_EMBED_PATCH, new=AsyncMock(return_value=[0.1] * 3072)):
                with patch(_SESSION_MAKER_PATCH, mock_session_maker):
                    return await retrieve_style_chunks("arrow functions", requested_language)

        asyncio.run(_run())

        # Verify session.execute was called with params containing the correct lang value.
        mock_session.execute.assert_called_once()
        _sql_arg, params_arg = mock_session.execute.call_args[0]
        self.assertEqual(params_arg.get("lang"), requested_language)


if __name__ == "__main__":
    unittest.main()
