"""
Style guide fetcher and ingester for MAPLE A1 RAG pipeline.

Fetches canonical style guides, chunks them by heading, embeds each chunk,
and upserts into the style_guide_chunks table.
"""

import asyncio
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import text

from ..models.database import async_session_maker
from .embeddings import embed_batch


@dataclass
class StyleGuideSource:
    source_title: str
    url: str
    language: str
    format: str
    version_pattern: str


@dataclass
class RawDocument:
    source_title: str
    url: str
    language: str
    version: str
    sections: list[tuple[str, str]] = field(default_factory=list)


STYLE_GUIDES = [
    StyleGuideSource(
        source_title="PEP 8 — Style Guide for Python Code",
        url="https://peps.python.org/pep-0008/",
        language="python",
        format="html",
        version_pattern=r"(?:Last modified|Created|Version)[:\s]+(\d{4}-\d{2}-\d{2}|\d{4})",
    ),
    StyleGuideSource(
        source_title="Oracle Java Code Conventions",
        url="https://www.oracle.com/java/technologies/javase/codeconventions-introduction.html",
        language="java",
        format="html",
        version_pattern=r"(\d{4})",
    ),
    StyleGuideSource(
        source_title="ts.dev TypeScript Style Guide",
        url="https://ts.dev/style/",
        language="typescript",
        format="html",
        version_pattern=r"(?:version|rev)[:\s]*([\d.]+)",
    ),
    StyleGuideSource(
        source_title="Google JavaScript Style Guide",
        url="https://google.github.io/styleguide/jsguide.html",
        language="javascript",
        format="html",
        version_pattern=r"(?:Version|Revision)[:\s]*([\d.]+)",
    ),
    StyleGuideSource(
        source_title="Google C++ Style Guide",
        url="https://google.github.io/styleguide/cppguide.html",
        language="c++",
        format="html",
        version_pattern=r"(?:Version|Revision)[:\s]*([\d.]+)",
    ),
]


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s-]+", "_", text)
    return text


async def fetch_and_parse(source: StyleGuideSource) -> RawDocument:
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        response = await client.get(source.url, headers={"User-Agent": "MAPLE-A1/1.0"})
        response.raise_for_status()
        html = response.text

    version_match = re.search(source.version_pattern, html, re.IGNORECASE)
    version = version_match.group(1) if version_match else "unknown"

    soup = BeautifulSoup(html, "html.parser")

    sections: list[tuple[str, str]] = []
    headings = soup.find_all(["h2", "h3"])

    for heading in headings:
        heading_text = heading.get_text(separator=" ", strip=True)
        if not heading_text:
            continue

        rule_id = _slugify(heading_text)
        chunk_parts = [heading_text]

        for sibling in heading.next_siblings:
            if hasattr(sibling, "name") and sibling.name in ("h2", "h3"):
                break
            text_content = sibling.get_text(separator=" ", strip=True) if hasattr(sibling, "get_text") else str(sibling).strip()
            if text_content:
                chunk_parts.append(text_content)

        chunk_text = "\n".join(chunk_parts).strip()
        if chunk_text:
            sections.append((rule_id, chunk_text))

    return RawDocument(
        source_title=source.source_title,
        url=source.url,
        language=source.language,
        version=version,
        sections=sections,
    )


async def ingest_all(db_session) -> int:
    total_upserted = 0

    for source in STYLE_GUIDES:
        doc = await fetch_and_parse(source)
        if not doc.sections:
            continue

        chunk_texts = [section[1] for section in doc.sections]
        embeddings = await embed_batch(chunk_texts)

        now = datetime.now(timezone.utc)

        await db_session.execute(
            text("DELETE FROM style_guide_chunks WHERE source_url = :url"),
            {"url": source.url},
        )

        for (rule_id, chunk_text), embedding in zip(doc.sections, embeddings):
            await db_session.execute(
                text("""
                    INSERT INTO style_guide_chunks
                        (source_title, source_url, language, style_guide_version,
                         rule_id, last_fetched, chunk_text, embedding)
                    VALUES
                        (:source_title, :source_url, :language, :style_guide_version,
                         :rule_id, :last_fetched, :chunk_text, :embedding)
                """),
                {
                    "source_title": doc.source_title,
                    "source_url": doc.url,
                    "language": doc.language,
                    "style_guide_version": doc.version,
                    "rule_id": rule_id,
                    "last_fetched": now,
                    "chunk_text": chunk_text,
                    "embedding": embedding,
                },
            )
            total_upserted += 1

        await db_session.commit()

    return total_upserted


async def main() -> None:
    async with async_session_maker() as session:
        count = await ingest_all(session)
        print(f"Ingested {count} chunks.")


if __name__ == "__main__":
    asyncio.run(main())
