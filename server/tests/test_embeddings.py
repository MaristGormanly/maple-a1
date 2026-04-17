"""Unit tests for the embeddings service (server/app/services/embeddings.py).

All network I/O is mocked; no real OpenAI calls are made.
"""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.embeddings import EmbeddingError, embed_batch, embed_text


_HTTPX_POST_PATCH = "httpx.AsyncClient.post"
_SETTINGS_PATCH = "app.services.embeddings.settings"


def _make_response(embedding: list[float], index: int = 0) -> MagicMock:
    """Return a mock httpx Response with the given embedding at *index*."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "data": [{"embedding": embedding, "index": index}]
    }
    return mock_resp


def _make_batch_response(items: list[tuple[int, list[float]]]) -> MagicMock:
    """Return a mock httpx Response with multiple embeddings (possibly out of order)."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "data": [{"index": idx, "embedding": emb} for idx, emb in items]
    }
    return mock_resp


class TestEmbedTextReturns3072Floats(unittest.TestCase):
    """embed_text() should return a list of exactly 3072 floats on success."""

    def test_embed_text_returns_3072_floats(self):
        fake_embedding = [0.1] * 3072
        mock_resp = _make_response(fake_embedding)

        async def _run():
            with patch(_SETTINGS_PATCH) as mock_settings:
                mock_settings.OPENAI_API_KEY = "sk-test-key"
                with patch(_HTTPX_POST_PATCH, new=AsyncMock(return_value=mock_resp)):
                    return await embed_text("some source text")

        result = asyncio.run(_run())

        self.assertEqual(len(result), 3072)
        self.assertAlmostEqual(result[0], 0.1)


class TestEmbedTextNoApiKeyRaises(unittest.TestCase):
    """embed_text() must raise EmbeddingError when OPENAI_API_KEY is absent/None."""

    def test_embed_text_no_api_key_raises(self):
        async def _run():
            with patch(_SETTINGS_PATCH) as mock_settings:
                mock_settings.OPENAI_API_KEY = None
                return await embed_text("some text")

        with self.assertRaises(EmbeddingError):
            asyncio.run(_run())


class TestEmbedBatchSortsByIndex(unittest.TestCase):
    """embed_batch() returns embeddings in index order even if the API returns them out of order."""

    def test_embed_batch_sorts_by_index(self):
        emb_0 = [0.1] * 3072
        emb_1 = [0.2] * 3072
        emb_2 = [0.3] * 3072

        # Return index=2 first, then index=0, then index=1 (deliberately scrambled).
        mock_resp = _make_batch_response([(2, emb_2), (0, emb_0), (1, emb_1)])

        async def _run():
            with patch(_SETTINGS_PATCH) as mock_settings:
                mock_settings.OPENAI_API_KEY = "sk-test-key"
                with patch(_HTTPX_POST_PATCH, new=AsyncMock(return_value=mock_resp)):
                    return await embed_batch(["text0", "text1", "text2"])

        result = asyncio.run(_run())

        self.assertEqual(len(result), 3)
        # After sorting by index, order should be emb_0, emb_1, emb_2.
        self.assertAlmostEqual(result[0][0], 0.1)
        self.assertAlmostEqual(result[1][0], 0.2)
        self.assertAlmostEqual(result[2][0], 0.3)


if __name__ == "__main__":
    unittest.main()
