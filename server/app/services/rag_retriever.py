"""
Style guide chunk retrieval for MAPLE A1 RAG pipeline.

Design-doc references:
    - §8 "cosine similarity retrieval: top-5 chunks, threshold 0.75; log retrieval_status: no_match"
    - §4 "Retrieval uses cosine similarity, filters by programming language..."
"""

import json
import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import text

from ..models.database import async_session_maker
from ..services.embeddings import embed_text
from ..services.llm import redact

logger = logging.getLogger(__name__)


@dataclass
class StyleChunkHit:
    id: uuid.UUID
    source_title: str
    source_url: str
    style_guide_version: str
    rule_id: str | None
    chunk_text: str
    cosine_sim: float


async def retrieve_style_chunks(
    query_text: str,
    language: str,
    *,
    top_k: int = 5,
    threshold: float = 0.75,
) -> list[StyleChunkHit]:
    qvec = await embed_text(redact(query_text))

    async with async_session_maker() as session:
        result = await session.execute(
            text("""
                SELECT id, source_title, source_url, style_guide_version, rule_id, chunk_text,
                       1 - (embedding <=> :qvec) AS cosine_sim
                FROM style_guide_chunks
                WHERE language = :lang AND embedding IS NOT NULL
                ORDER BY embedding <=> :qvec
                LIMIT :k
            """),
            {"qvec": qvec, "lang": language, "k": top_k},
        )
        rows = result.fetchall()

    hits = [
        StyleChunkHit(
            id=row.id,
            source_title=row.source_title,
            source_url=row.source_url,
            style_guide_version=row.style_guide_version,
            rule_id=row.rule_id,
            chunk_text=row.chunk_text,
            cosine_sim=float(row.cosine_sim),
        )
        for row in rows
        if float(row.cosine_sim) >= threshold
    ]

    if not hits:
        logger.info(
            json.dumps({
                "event": "rag_retrieval",
                "language": language,
                "retrieval_status": "no_match",
                "candidates": len(rows),
            })
        )

    return hits
