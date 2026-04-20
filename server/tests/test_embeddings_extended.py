"""Extended tests for embeddings.py — request shape, HTTP errors, batch ordering."""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.embeddings import EmbeddingError, embed_batch, embed_text

_HTTPX_POST = "httpx.AsyncClient.post"
_SETTINGS = "app.services.embeddings.settings"


def _resp(embeddings: list, status_code: int = 200):
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    if status_code >= 400:
        import httpx
        mock.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock()
        )
    mock.json.return_value = {
        "data": [{"embedding": e, "index": i} for i, e in enumerate(embeddings)]
    }
    return mock


class TestEmbedTextRequestShape(unittest.TestCase):
    """embed_text sends the correct request body to the OpenAI endpoint."""

    def test_uses_text_embedding_3_large_model(self):
        mock_resp = _resp([[0.0] * 1536])
        captured_body = []

        async def fake_post(url, **kwargs):
            captured_body.append(kwargs.get("json", {}))
            return mock_resp

        async def run():
            with patch(_SETTINGS) as ms:
                ms.OPENAI_API_KEY = "sk-x"
                with patch(_HTTPX_POST, side_effect=fake_post):
                    return await embed_text("hello")

        asyncio.run(run())
        self.assertEqual(captured_body[0]["model"], "text-embedding-3-large")

    def test_sends_dimensions_1536(self):
        mock_resp = _resp([[0.0] * 1536])
        captured_body = []

        async def fake_post(url, **kwargs):
            captured_body.append(kwargs.get("json", {}))
            return mock_resp

        async def run():
            with patch(_SETTINGS) as ms:
                ms.OPENAI_API_KEY = "sk-x"
                with patch(_HTTPX_POST, side_effect=fake_post):
                    return await embed_text("hello")

        asyncio.run(run())
        self.assertEqual(captured_body[0]["dimensions"], 1536)

    def test_sends_input_text(self):
        mock_resp = _resp([[0.0] * 1536])
        captured_body = []

        async def fake_post(url, **kwargs):
            captured_body.append(kwargs.get("json", {}))
            return mock_resp

        async def run():
            with patch(_SETTINGS) as ms:
                ms.OPENAI_API_KEY = "sk-x"
                with patch(_HTTPX_POST, side_effect=fake_post):
                    return await embed_text("specific text")

        asyncio.run(run())
        self.assertEqual(captured_body[0]["input"], "specific text")

    def test_sends_bearer_auth_header(self):
        mock_resp = _resp([[0.0] * 1536])
        captured_headers = []

        async def fake_post(url, **kwargs):
            captured_headers.append(kwargs.get("headers", {}))
            return mock_resp

        async def run():
            with patch(_SETTINGS) as ms:
                ms.OPENAI_API_KEY = "sk-mykey"
                with patch(_HTTPX_POST, side_effect=fake_post):
                    return await embed_text("t")

        asyncio.run(run())
        self.assertIn("Bearer sk-mykey", captured_headers[0].get("Authorization", ""))

    def test_returns_list_of_correct_length(self):
        mock_resp = _resp([[0.5] * 1536])

        async def run():
            with patch(_SETTINGS) as ms:
                ms.OPENAI_API_KEY = "sk-x"
                with patch(_HTTPX_POST, new=AsyncMock(return_value=mock_resp)):
                    return await embed_text("t")

        result = asyncio.run(run())
        self.assertEqual(len(result), 1536)


class TestEmbedTextHTTPErrors(unittest.TestCase):
    def test_http_error_propagates(self):
        import httpx
        mock_resp = _resp([], status_code=429)

        async def run():
            with patch(_SETTINGS) as ms:
                ms.OPENAI_API_KEY = "sk-x"
                with patch(_HTTPX_POST, new=AsyncMock(return_value=mock_resp)):
                    return await embed_text("t")

        with self.assertRaises(Exception):
            asyncio.run(run())


class TestEmbedBatchRequestShape(unittest.TestCase):
    def test_sends_list_input(self):
        texts = ["a", "b", "c"]
        mock_resp = _resp([[0.0] * 1536, [0.1] * 1536, [0.2] * 1536])
        captured_body = []

        async def fake_post(url, **kwargs):
            captured_body.append(kwargs.get("json", {}))
            return mock_resp

        async def run():
            with patch(_SETTINGS) as ms:
                ms.OPENAI_API_KEY = "sk-x"
                with patch(_HTTPX_POST, side_effect=fake_post):
                    return await embed_batch(texts)

        asyncio.run(run())
        self.assertEqual(captured_body[0]["input"], texts)
        self.assertEqual(captured_body[0]["dimensions"], 1536)

    def test_returns_one_embedding_per_input(self):
        texts = ["x", "y"]
        mock_resp = _resp([[0.0] * 1536, [1.0] * 1536])

        async def run():
            with patch(_SETTINGS) as ms:
                ms.OPENAI_API_KEY = "sk-x"
                with patch(_HTTPX_POST, new=AsyncMock(return_value=mock_resp)):
                    return await embed_batch(texts)

        result = asyncio.run(run())
        self.assertEqual(len(result), 2)

    def test_out_of_order_indices_sorted(self):
        # API returns index=1 before index=0
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        mock.json.return_value = {
            "data": [
                {"index": 1, "embedding": [0.9] * 1536},
                {"index": 0, "embedding": [0.1] * 1536},
            ]
        }

        async def run():
            with patch(_SETTINGS) as ms:
                ms.OPENAI_API_KEY = "sk-x"
                with patch(_HTTPX_POST, new=AsyncMock(return_value=mock)):
                    return await embed_batch(["first", "second"])

        result = asyncio.run(run())
        self.assertAlmostEqual(result[0][0], 0.1)
        self.assertAlmostEqual(result[1][0], 0.9)


class TestEmbedNoKey(unittest.TestCase):
    def test_embed_text_raises_embedding_error_when_no_key(self):
        async def run():
            with patch(_SETTINGS) as ms:
                ms.OPENAI_API_KEY = None
                return await embed_text("t")
        with self.assertRaises(EmbeddingError):
            asyncio.run(run())

    def test_embed_batch_raises_embedding_error_when_no_key(self):
        async def run():
            with patch(_SETTINGS) as ms:
                ms.OPENAI_API_KEY = None
                return await embed_batch(["t"])
        with self.assertRaises(EmbeddingError):
            asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
