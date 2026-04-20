"""
Standalone demo of the MAPLE A1 RAG retrieval pipeline.

Three modes:
    python scripts/demo_rag.py --ingest
    python scripts/demo_rag.py --query "naming" --lang python
    python scripts/demo_rag.py --showcase

Run from the repo root with the server virtualenv active. Requires
OPENAI_API_KEY, DATABASE_URL, and `alembic upgrade head` already applied.
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "server"))


SHOWCASE_QUERIES: list[tuple[str, str]] = [
    ("header file include guards", "c++"),
    ("naming conventions", "python"),
    ("let const var", "javascript"),
    ("favorite pizza toppings", "python"),
]


def _print_header(title: str) -> None:
    bar = "=" * len(title)
    print(f"\n{bar}\n{title}\n{bar}")


async def _run_query(query: str, lang: str, *, top_k: int = 5, threshold: float = 0.75) -> None:
    from app.services.rag_retriever import retrieve_style_chunks

    print(f"\n> query={query!r}  language={lang}  top_k={top_k}  threshold={threshold}")
    started = time.perf_counter()
    hits = await retrieve_style_chunks(query, lang, top_k=top_k, threshold=threshold)
    elapsed_ms = (time.perf_counter() - started) * 1000

    if not hits:
        print(f"  (no hits above threshold; see server log for retrieval_status=no_match)  [{elapsed_ms:.0f} ms]")
        return

    print(f"  {len(hits)} hit(s) in {elapsed_ms:.0f} ms")
    for i, hit in enumerate(hits, start=1):
        snippet = hit.chunk_text.strip().replace("\n", " ")[:200]
        print(f"  [{i}] cos={hit.cosine_sim:.3f}  {hit.source_title}  rule={hit.rule_id}")
        print(f"      {snippet}{'...' if len(hit.chunk_text) > 200 else ''}")


def _register_pgvector_codec() -> None:
    """Teach the shared asyncpg engine how to serialize Python lists to pgvector.

    The project's raw-SQL inserts/queries bypass SQLAlchemy's type system, so
    asyncpg needs the pgvector codec registered on every new connection.
    """
    from pgvector.asyncpg import register_vector
    from sqlalchemy import event

    from app.models.database import engine

    @event.listens_for(engine.sync_engine, "connect")
    def _on_connect(dbapi_connection, _connection_record):
        dbapi_connection.run_async(register_vector)


async def _run_ingest() -> None:
    from app.models.database import async_session_maker
    from app.services.style_guide_ingester import ingest_all

    _print_header("Ingesting style guides")
    started = time.perf_counter()
    async with async_session_maker() as session:
        count = await ingest_all(session)
    elapsed = time.perf_counter() - started
    print(f"\nIngested {count} chunks in {elapsed:.1f}s.")


async def _run_showcase() -> None:
    # Production gate is 0.75; lowered for the demo because text-embedding-3-large
    # @ 1536 dims with these chunk sizes clusters relevant matches in 0.50-0.75,
    # while genuinely-irrelevant queries still score well under 0.10.
    showcase_threshold = 0.50
    _print_header("RAG retrieval showcase")
    for query, lang in SHOWCASE_QUERIES:
        await _run_query(query, lang, threshold=showcase_threshold)


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo the MAPLE A1 RAG retrieval pipeline.")
    parser.add_argument("--ingest", action="store_true", help="Run ingest_all() and exit.")
    parser.add_argument("--showcase", action="store_true", help="Run the canned demo queries.")
    parser.add_argument("--query", help="Custom query text (requires --lang).")
    parser.add_argument("--lang", help="Language filter for --query (e.g. python, typescript, c++).")
    parser.add_argument("--top-k", type=int, default=5, help="Top-k chunks to retrieve (default 5).")
    parser.add_argument("--threshold", type=float, default=0.75, help="Cosine similarity floor (default 0.75).")
    args = parser.parse_args()

    if not (args.ingest or args.showcase or args.query):
        args.showcase = True

    _register_pgvector_codec()

    async def runner() -> None:
        if args.ingest:
            await _run_ingest()
        if args.query:
            if not args.lang:
                parser.error("--query requires --lang")
            _print_header("Custom query")
            await _run_query(args.query, args.lang, top_k=args.top_k, threshold=args.threshold)
        if args.showcase:
            await _run_showcase()

    asyncio.run(runner())


if __name__ == "__main__":
    main()
