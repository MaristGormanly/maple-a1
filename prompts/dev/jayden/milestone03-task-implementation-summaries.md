# Milestone 3 — Implementation Summary: Jayden

## Implementation summary — Jayden (Milestone 3)

### What shipped

**Task 1 — LLM call wrapper (`server/app/services/llm.py`)**
`complete()` is an async function that walks `MODEL_CHAIN` (gemini-3.1-pro-preview → gemini-3.1-flash-lite → gpt-4o). Each model gets `LLM_MAX_RETRIES` attempts with exponential backoff (`LLM_BACKOFF_BASE * 2^(attempt-1)` seconds). Complexity-aware timeouts (`LLM_TIMEOUT_STANDARD`/`LLM_TIMEOUT_COMPLEX`) come from `settings`. Input is redacted before dispatch. Raises `EvaluationFailedError` when all models are exhausted. `ProviderError` stubs mark Gemini and OpenAI dispatch as not-yet-wired. Structured JSON is emitted for every attempt (`event: llm_call` / `llm_retry` / `llm_model_exhausted`).

**Task 2 — LLM settings (`server/app/config.py`)**
Added `GEMINI_API_KEY`, `OPENAI_API_KEY`, `LLM_TIMEOUT_STANDARD` (30 s), `LLM_TIMEOUT_COMPLEX` (60 s), `LLM_MAX_RETRIES` (2), `LLM_BACKOFF_BASE` (1.0) — all optional with safe defaults.

**Task 3 — Embedding client (`server/app/services/embeddings.py`)**
`embed_text()` and `embed_batch()` call OpenAI `text-embedding-3-large` (3072 dims) via `httpx`. Raise `EmbeddingError` if `OPENAI_API_KEY` is unset.

**Task 4 — Style guide ingester (`server/app/services/style_guide_ingester.py`)**
`STYLE_GUIDES` defines five sources: PEP 8 (python), Oracle Java Conventions (java), ts.dev (typescript), Google JS Guide (javascript), Google C++ Guide (c++). `ingest_all()` fetches HTML, chunks by `<h2>`/`<h3>` headings, batch-embeds, delete-then-inserts into `style_guide_chunks`.

**Task 5 — DB model + migration**
`StyleGuideChunk` ORM model (`server/app/models/style_guide_chunk.py`) maps `style_guide_chunks` with a `vector(3072)` embedding column. Migration `b2c3d4e5f6a7` (`alembic/versions/b2c3d4e5f6a7_add_style_guide_chunks.py`) enables the `vector` extension and creates the table.

**Task 6 — RAG retriever (`server/app/services/rag_retriever.py`)**
`retrieve_style_chunks()` embeds the redacted query, runs a raw cosine-similarity SQL query (`1 - (embedding <=> :qvec)`), filters rows below `threshold` (default 0.75), and returns up to `top_k` (default 5) `StyleChunkHit` objects. Logs `retrieval_status: no_match` when the result list is empty.

**Task 7 — Linter Docker images (`server/docker/lint/`)**
`Dockerfile.python`: `python:3.12-slim` + `pylint==3.2.7`. `Dockerfile.node`: `node:20-slim` + `eslint@9.10.0`, `@typescript-eslint/parser@8.7.0`, `@typescript-eslint/eslint-plugin@8.7.0`.

**Task 8 — Linter runner + sandbox profiles**
`sandbox_images.py` adds `LINT_PROFILES` and `get_lint_profile()` for python/javascript/typescript. `linter_runner.py` exposes `run_linter()`, which resolves a `LintProfile`, builds a read-only `ContainerConfig` (512 m RAM, 50% CPU, `cap_drop=ALL`, no network), delegates to `docker_runner.run_container()`, and parses output via `_parse_violations()`. Pylint and eslint JSON formats are both supported.

**New deps** (`server/requirements.txt`): `pgvector`, `openai`, `beautifulsoup4`.

### How to run tests
```
pytest server/tests/test_llm.py server/tests/test_linter_runner.py server/tests/test_rag_retriever.py server/tests/test_embeddings.py -v
```

### How to ingest style guides
```
python -m server.app.services.style_guide_ingester
```

### How to build linter images
```
docker build -f server/docker/lint/Dockerfile.python -t maple-python-lint:3.12 .
docker build -f server/docker/lint/Dockerfile.node   -t maple-node-lint:20 .
```

### Open risks
1. `vector(3072)` exceeds pgvector's HNSW/IVFFlat index cap of 2000 dims — exact cosine scan is used; acceptable at current row counts but confirm if ANN index is needed.
2. `GEMINI_API_KEY` and `OPENAI_API_KEY` must be set in `.env`; embeddings and LLM calls will error without them.
3. `_call_gemini()` and `_call_openai()` are stubs — real SDK wiring is not yet implemented.
4. pgvector requires the `ankane/pgvector` Postgres image or the `vector` extension pre-installed in local Postgres.

**Spec citations:** `docs/design-doc.md` §3 §II, §4, §8; `docs/milestones/milestone-03-tasks.md` Tasks 1–8

---

## Handoff: interface strategies for Dom and Sylvie (Milestone 3)

### For Dom (pipeline orchestrator)

**1. LLM completion**
```python
from server.app.services.llm import complete, EvaluationFailedError
```
`complete(system_prompt, messages, *, complexity="standard", max_tokens=1024, temperature=0.7) -> LLMResponse`
Returns `LLMResponse` with `.content: str`, `.usage.input_tokens`, `.usage.output_tokens`, `.usage.cost_usd`, `.latency_ms`. Raises `EvaluationFailedError` when the full `MODEL_CHAIN` is exhausted — Dom catches this and sets `EVALUATION_FAILED` per `docs/design-doc.md` §4 retry policy.

**2. RAG retrieval**
```python
from server.app.services.rag_retriever import retrieve_style_chunks, StyleChunkHit
```
`retrieve_style_chunks(query_text, language, *, top_k=5, threshold=0.75) -> list[StyleChunkHit]`
Each `StyleChunkHit` exposes `.chunk_text`, `.source_title`, `.source_url`, `.style_guide_version`, `.rule_id`, `.cosine_sim`. An empty return list means `retrieval_status: "no_match"` — Dom should set the `NEEDS_HUMAN_REVIEW` flag per `docs/design-doc.md` §4 and §8. Valid `language` values: `"python"`, `"javascript"`, `"typescript"`, `"java"`, `"c++"`.

**3. Linter runner**
```python
from server.app.services.linter_runner import run_linter, Violation
```
`run_linter(language, repo_host_path) -> list[Violation]`
Each `Violation` has `.file`, `.line`, `.rule_id`, `.severity`, `.message`. Returns an empty list for unsupported languages without raising. Dom checks `enable_lint_review` and `len(violations) > 0` to gate Pass 2 per `docs/design-doc.md` §4.

### For Sylvie (API layer and Angular UI)

Jayden owns no direct API endpoints. Dom populates `ai_feedback_json` on `EvaluationResult`, including `metadata.style_guide_version` sourced from the first `StyleChunkHit.style_guide_version`. Sylvie's `GET /submissions/{id}` extension surfaces this as `evaluation.ai_feedback.metadata.style_guide_version` per `docs/api-spec.md` response shape. All Jayden-to-Sylvie handoff flows through Dom's pipeline output stored in `evaluation_results.ai_feedback_json` — there is no direct contract between Jayden and Sylvie.

**Spec citations:** `docs/design-doc.md` §3 §II (chunk metadata), §4 (retry policy, retrieval threshold, Pass 2 conditions), §8 (task deliverables); `docs/milestones/milestone-03-tasks.md` Tasks 1–8
