"""
OpenAI embedding client for MAPLE A1 RAG pipeline.
Calls text-embedding-3-large (3072 dims) per docs/design-doc.md §8.
"""

import httpx

from ..config import settings


class EmbeddingError(Exception):
    pass


async def embed_text(text: str) -> list[float]:
    if not settings.OPENAI_API_KEY:
        raise EmbeddingError("OPENAI_API_KEY not configured")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": "text-embedding-3-large", "input": text},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]


async def embed_batch(texts: list[str]) -> list[list[float]]:
    if not settings.OPENAI_API_KEY:
        raise EmbeddingError("OPENAI_API_KEY not configured")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": "text-embedding-3-large", "input": texts},
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()["data"]
        data.sort(key=lambda item: item["index"])
        return [item["embedding"] for item in data]
