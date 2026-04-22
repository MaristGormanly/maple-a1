# Milestone 3 — Jayden Track: Completion & Verification Plan

> **Execution note:** First post-approval action — copy this plan to `prompts/dev/jayden/milestone-3-jayden-roadmap.md` (user confirmed). API keys (`GEMINI_API_KEY`, `OPENAI_API_KEY`) are available in the dev environment, so the E2E smoke test (G6) will run for real. Cost tracking (G2) is in scope for this iteration.

---

## Context

Milestone 3 (`docs/milestones/milestone-03-tasks.md`) lists 8 tasks under Jayden's track as `[ ]` pending:

1. `services/llm.py` `complete()` — retry + exponential backoff
2. Model fallback chain + 30s/60s timeouts + redactor wiring
3. pgvector migration (`style_guide_chunks` table)
4. Style guide fetch + ingestion pipeline
5. Semantic chunking + `text-embedding-3-large` embedding
6. Cosine similarity retrieval (`retrieve_style_chunks`)
7. Linter execution (`pylint`/`eslint`) in Docker
8. Linter tooling in base images + `docs/deployment.md` update

**Investigation finding (Phase 1 + file reads):** All 8 items are **already implemented in code**. The M3 task doc is stale relative to the repo. Concretely:

| # | M3 Task | File | Status |
|---|---|---|---|
| 1 | `complete()` retry/backoff | `server/app/services/llm.py:208–300` | Implemented (not a stub) |
| 2 | Fallback chain + timeouts + redactor | same file, `MODEL_CHAIN`, `_dispatch`, redact wiring at lines 230–231 | Implemented |
| 3 | pgvector schema | `alembic/versions/b2c3d4e5f6a7_add_style_guide_chunks.py` + `c3d4e5f6a7b8_resize_embedding_vector_add_hnsw.py` | Implemented (HNSW cosine, 1536-dim) |
| 4 | Style guide fetch/ingest | `server/app/services/style_guide_ingester.py` | Implemented — 5 sources |
| 5 | Chunking + embedding | `server/app/services/embeddings.py` + ingester | Implemented (`text-embedding-3-large`, dims=1536) |
| 6 | Cosine retrieval | `server/app/services/rag_retriever.py` | Implemented (top-5, 0.75 threshold, `no_match` logging) |
| 7 | Linter execution in Docker | `server/app/services/linter_runner.py` | Implemented (pylint + eslint JSON parsing) |
| 8 | Linter tooling in base images + docs | `server/app/services/sandbox_images.py` (profiles exist), `docs/deployment.md` | **Code present; deployment doc update not verified** |

Supporting pieces in place: Dom's AI passes (`services/ai_passes.py`), validator (`services/llm_validator.py`), schemas (`services/llm_schemas.py`), pipeline orchestration (`services/pipeline.py`), tests (`server/tests/test_llm*.py`, `test_rag_retriever.py`, `test_linter_runner.py`, etc.).

**Therefore, the real work for "complete all pending Jayden M3 tasks" is an audit-and-close-gaps pass, not net-new construction.** The concrete gaps identified:

- **G1** — `server/app/services/llm.py` docstring (lines 1–9) still labels the wrapper as "stub only". Misleading for reviewers.
- **G2** — `LLMUsage.cost_usd` is hardcoded to `0.0` in both `_call_gemini` (line 163) and `_call_openai` (line 189). Cost observability requirement (design-doc §4 "structured logging of token usage and latency", §6 cost cap) is only partially met.
- **G3** — `latency_ms` returned directly from provider helpers is `0`; the real value is only attached at the outer `complete()` call (line 244). Fine, but confusing — helpers should return latency too, or callers should not rely on the inner value.
- **G4** — Linter base-image specification and pinned versions not confirmed in `docs/deployment.md` (M3 task 8 explicitly asks for this).
- **G5** — `docs/milestones/milestone-03-tasks.md` traceability matrix marks rows 1–8 as `pending`; needs update to `done` post-verification.
- **G6** — End-to-end M3 verification (E2E row in traceability) marked `pending`. No evidence an integration run has been executed with real keys.

## Recommended Approach

Three phases, following the user's "test-first, code-second, test-again" mandate.

### Phase A — Audit & Verification (read-only)

1. Run the existing M3 test suite to confirm the codebase is green before any edits:
   ```bash
   cd server && pytest tests/test_llm.py tests/test_llm_extended.py \
     tests/test_provider_dispatch.py tests/test_rag_retriever.py \
     tests/test_linter_runner.py tests/test_linter_extended.py \
     tests/test_ai_passes_pass1.py tests/test_ai_passes_pass2.py \
     tests/test_ai_passes_pass3.py tests/test_llm_validator.py \
     tests/test_llm_schemas.py tests/test_embeddings.py \
     tests/test_ingester.py -v
   ```
2. Spot-check that `alembic upgrade head` applies the pgvector + HNSW migrations cleanly against a scratch DB.
3. Confirm `sandbox_images.get_lint_profile("python"|"javascript"|"typescript")` returns images with `pylint`/`eslint` installed.

### Phase B — Close Gaps (scoped edits)

For each gap, apply the **Test First → Code Second → Test Again** loop.

**G1 — Update `server/app/services/llm.py` module docstring**
- Test first: No behavioral test; docstring is informational. Add a doctest-style assertion that `llm.complete` is callable and not raising `NotImplementedError` when keys are unset (it currently raises `EvaluationFailedError` after exhaustion, which is correct).
- Code: Rewrite lines 1–9 and lines 63–65 header to state M3 is implemented; describe fallback chain and redaction. Remove "stub only" wording.

**G2 — Token cost tracking in `LLMUsage`**
- Test first: Add `tests/test_llm_cost.py` with fixture token counts for each model; assert `cost_usd` matches a published per-1K pricing table (stored as a constant `MODEL_PRICING` in `llm.py`).
- Code: Introduce `MODEL_PRICING: dict[str, tuple[float, float]]` (input $/1K, output $/1K) and compute `cost_usd = (input_tokens/1000)*in_rate + (output_tokens/1000)*out_rate` inside `_call_gemini` and `_call_openai`.
- Test again: Re-run `test_llm_cost.py` + existing `test_llm.py`.

**G3 — Latency propagation (minor)**
- Defer unless G2 touches the helpers. If touched, set `latency_ms` inside helpers using a local `time.monotonic()` block; outer `complete()` continues to overwrite with total including retries.

**G4 — Deployment doc update for linter base images**
- File: `docs/deployment.md`. Add a subsection under the Docker runtime section titled "Linter base images (M3)". Enumerate:
  - Python image: `python:3.12-slim` + `pylint==<pinned>` (read actual pin from `sandbox_images.py`)
  - JS/TS image: `node:20-alpine` + `eslint@<pinned>` + default config
  - Note that images are built at deploy time; include the `docker pull` / build command used.
- Test: Grep-based CI check — `rg 'pylint' docs/deployment.md && rg 'eslint' docs/deployment.md` non-empty.

**G5 — Milestone doc traceability update**
- File: `docs/milestones/milestone-03-tasks.md`. Flip rows 1–8 in the traceability matrix from `pending` → `done`, and check the `[ ]` boxes at lines 17–41. Add a short "Verified on 2026-04-22" note pointing to the Phase A test run log in `audits/` or `eval/results/`.

**G6 — End-to-end smoke test**
- Test first: Create `server/tests/test_m3_e2e.py` that, gated on `GEMINI_API_KEY` / `OPENAI_API_KEY` being present in env (skip otherwise), drives `pipeline.run_pipeline` with a tiny fixture repo + rubric and asserts: (a) `EvaluationResult.ai_feedback_json` is populated, (b) the envelope validates against `PASS3_OUTPUT_SCHEMA`, (c) `metadata_json` contains `style_guide_version`.
- Run against the dev environment with real keys.
- Record timings and any retry/fallback observed.

### Phase C — Robustness & Ops

- Confirm `settings.GEMINI_API_KEY` / `OPENAI_API_KEY` are documented in `.env.example` (they should be; verify).
- Confirm `alembic upgrade head` is part of the deploy runbook in `docs/deployment.md`; add the pgvector extension bootstrap (`CREATE EXTENSION IF NOT EXISTS vector`) as a pre-migration step if not already present.
- Confirm the style-guide ingester CLI (`python -m app.services.style_guide_ingester`) is listed as a one-time post-deploy step.

## Critical Files

**Likely to be edited (small, surgical):**
- `server/app/services/llm.py` — docstring + `MODEL_PRICING` constant + `cost_usd` computation
- `docs/deployment.md` — linter images subsection + alembic + ingester runbook note
- `docs/milestones/milestone-03-tasks.md` — flip pending→done in matrix + check boxes

**Likely to be added:**
- `server/tests/test_llm_cost.py`
- `server/tests/test_m3_e2e.py` (skip-gated on API keys)

**Read-only reference (no edits expected):**
- `server/app/services/rag_retriever.py`, `embeddings.py`, `style_guide_ingester.py`, `linter_runner.py`, `ai_passes.py`, `pipeline.py`
- `alembic/versions/b2c3d4e5f6a7_add_style_guide_chunks.py`, `c3d4e5f6a7b8_resize_embedding_vector_add_hnsw.py`

## Reused Existing Utilities (do not rebuild)

- `redact`, `redact_dict` — `server/app/services/llm.py:32,41`
- `_call_gemini`, `_call_openai`, `_dispatch` — `server/app/services/llm.py:109,168,194`
- `retrieve_style_chunks` — `server/app/services/rag_retriever.py:34`
- `embed_text`, `embed_batch` — `server/app/services/embeddings.py`
- `run_linter`, `_parse_violations` — `server/app/services/linter_runner.py:106,35`
- `get_lint_profile` — `server/app/services/sandbox_images.py`
- `validate_and_repair` — `server/app/services/llm_validator.py`
- `run_pipeline` — `server/app/services/pipeline.py`

## Verification

End-to-end acceptance for Jayden's M3 slice:

1. `cd server && pytest tests/ -v` — full suite green.
2. `cd server && pytest tests/test_llm_cost.py -v` — cost math green (new).
3. With `GEMINI_API_KEY` set: `cd server && pytest tests/test_m3_e2e.py -v` — live pipeline populates `ai_feedback_json` and passes schema validation.
4. `alembic upgrade head` on a clean DB applies `style_guide_chunks` + HNSW migrations without error.
5. `python -m app.services.style_guide_ingester` populates at least one chunk per language; `SELECT language, count(*) FROM style_guide_chunks GROUP BY 1` returns 5 rows.
6. `rg '"stub only"' server/app/services/llm.py` returns nothing (G1 closed).
7. `rg -n 'pylint|eslint' docs/deployment.md` returns at least two hits (G4 closed).
8. `docs/milestones/milestone-03-tasks.md` traceability rows 1–8 read `done` (G5 closed).

## Resolved Decisions

- **API keys:** Available in the dev environment → G6 E2E test runs live.
- **Plan placement:** First execution step is `cp` of this plan into `prompts/dev/jayden/milestone-3-jayden-roadmap.md`.
- **Cost tracking (G2):** In scope for this M3 iteration.
