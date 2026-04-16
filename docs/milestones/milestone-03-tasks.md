# Milestone 3 — AI Integration & RAG Pipeline (Week 13 — Lab 3 Prototype)

**Goal:** All three LLM passes operational; style guide RAG pipeline ingested and retrieving; instructor review UI complete. *(Source: `docs/design-doc.md` §8 "Milestone 3 — AI Integration & RAG Pipeline")*

**Deliverable:** Full three-pass AI evaluation runs end-to-end; instructor can review and approve/reject AI feedback; style guide version shown in UI. *(Source: `docs/design-doc.md` §8 "Deliverable: Full three-pass AI evaluation runs end-to-end; instructor can review and approve/reject AI feedback; style guide version shown in UI.")*

---

## Jayden — LLM Service, RAG Infrastructure, Linter Execution (8 tasks)

**Summary:** By the end of these tasks, the LLM service layer (`services/llm.py`) will be fully operational with retry logic, exponential backoff, configurable timeouts, and a three-tier model fallback chain. The pgvector schema will store chunked and embedded style guide excerpts, and a retrieval function will return the top-5 cosine-similar chunks with a 0.75 threshold. All five style guides will be fetched, parsed, versioned, chunked, and embedded. Linter execution (`pylint`/`eslint`) will run inside Docker containers and produce structured violations JSON. These tasks are independently verifiable: the LLM wrapper can be tested against mock providers, the RAG pipeline against a local pgvector instance, and linter execution against the existing Milestone 2 Docker runtime.

**Tasks:**

### LLM Service Hardening

- [ ] Finalize `services/llm.py` `complete()` function: implement 2-retry-per-model logic with exponential backoff. Replace the current `NotImplementedError` stub (line 85) with a working implementation that attempts up to 2 retries per model with exponential backoff (e.g., 1s, 2s delays). On model-level failure (all retries exhausted), fall through to the next model in the chain. Populate the existing `LLMResponse` and `LLMUsage` dataclasses with actual values. Log each attempt, retry, and failure as structured JSON (model name, attempt number, latency, token counts, error type). — *`docs/design-doc.md` §8 "Finalize `services/llm.py`: implement 2-retry-per-model logic with exponential backoff"; also §4 "Retry Policy: Each model gets 2 retries with exponential backoff before a model-level failure is declared"*

- [ ] Implement model fallback chain and configurable timeouts in `services/llm.py`. Wire the fallback order: `gemini-3.1-pro-preview` → `gemini-3.1-flash-lite` → `gpt-4o`. Apply 30-second timeouts for standard calls (Pass 2 style review) and 60-second timeouts for complex calls (Pass 1 reconciliation, Pass 3 synthesis). If all models exhaust retries, raise a terminal error that the pipeline can catch to mark `EVALUATION_FAILED`. Integrate the existing `redact()`/`redact_dict()` functions to sanitize all prompts before external API calls. — *`docs/design-doc.md` §8 "timeouts (30s standard, 60s complex); model fallback chain (`gemini-3.1-pro-preview` → `gemini-3.1-flash-lite` → `gpt-4o`)"; also §4 "If `gpt-4o` also exhausts its 2 retries, the submission is marked `EVALUATION_FAILED` for human review"*
  > *Depends on: `complete()` retry logic task above.*

### RAG Infrastructure

- [ ] Create pgvector schema for style guide chunks. Add an Alembic migration that creates a `style_guide_chunks` table with columns: `id` (UUID PK), `source_title` (string), `source_url` (string), `language` (string), `style_guide_version` (string), `rule_id` (string), `last_fetched` (timestamp), `chunk_text` (text), `embedding` (vector(3072) for `text-embedding-3-large` output). Create a GIN index on the `embedding` column for cosine similarity queries. Ensure the `pgvector` extension is enabled via `CREATE EXTENSION IF NOT EXISTS vector`. — *`docs/design-doc.md` §3 §II "Each chunk stores: `source_title`, `source_url`, `language`, `style_guide_version`, `rule_id`, `last_fetched`. They are embedded with `text-embedding-3-large` and stored in pgvector"; also §8 "Chunk by semantic heading/rule block; embed with `text-embedding-3-large`; store in pgvector"*

- [ ] Implement style guide fetch and ingestion pipeline. Create `services/style_guide_ingester.py` that fetches the five approved style guides: PEP 8 (Python), Oracle Java Code Conventions (Java), ts.dev (TypeScript), Google JS Style Guide (JavaScript), Google C++ Style Guide (C++). Parse each document's version/revision date from its content. Store the parsed `style_guide_version` in chunk metadata. For HTML sources, extract text content; for the Java PDF, extract text from the PDF. — *`docs/design-doc.md` §8 "Fetch and ingest style guides: PEP 8 (Python), Oracle Java Code Conventions (Java), ts.dev (TypeScript), Google JS Style Guide (JavaScript), Google C++ Style Guide (C++)"; also §8 "Parse style guide version from each document; store `style_guide_version` in chunk metadata"*
  > *Depends on: pgvector schema task above (chunks are stored in the `style_guide_chunks` table).*

- [ ] Implement semantic chunking and embedding for style guide documents. For each fetched style guide, chunk by semantic heading and rule block (each discrete rule = one chunk). For each chunk, call the OpenAI `text-embedding-3-large` API to generate a 3072-dimensional embedding vector. Persist each chunk with its embedding, metadata fields (`source_title`, `source_url`, `language`, `style_guide_version`, `rule_id`, `last_fetched`), and text content into the `style_guide_chunks` table. — *`docs/design-doc.md` §8 "Chunk by semantic heading/rule block; embed with `text-embedding-3-large`; store in pgvector"; also §3 §II "Documents are chunked by semantic heading and rule block (each discrete rule = one chunk)"*
  > *Depends on: style guide fetch task above (raw document text must be available before chunking).*

- [ ] Implement cosine similarity retrieval function. Create `services/rag_retriever.py` with a `retrieve_style_chunks(query_text: str, language: str, top_k: int = 5, threshold: float = 0.75)` function. Embed the query text using `text-embedding-3-large`, then query pgvector with cosine similarity (`<=>` operator), filtering by `language`. Return the top-5 chunks above the 0.75 threshold. If no chunk scores above threshold, return an empty list and log `retrieval_status: "no_match"`. — *`docs/design-doc.md` §8 "Implement cosine similarity retrieval: top-5 chunks, threshold 0.75; log `retrieval_status: \"no_match\"` when below threshold"; also §4 "Retrieval uses cosine similarity, filters by programming language and document type, and returns the top 5 chunks. If no chunk scores above 0.75, the system proceeds without retrieval context and records `retrieval_status: \"no_match\"`"*
  > *Depends on: semantic chunking and embedding task above (chunks must be stored before retrieval can function).*

### Linter Execution

- [ ] Implement linter execution inside Docker containers. Extend `services/docker_client.py` (or create `services/linter_runner.py`) to run `pylint` (Python) and `eslint` (JavaScript/TypeScript) statically inside the existing Docker containers. Capture the linter output as structured JSON (file path, line number, rule ID, severity, message). Return the violations list to the pipeline for use as Pass 2 input. Reuse the existing container security hardening from Milestone 2 (`no-new-privileges`, `cap_drop=ALL`, read-only FS, TTL). — *`docs/design-doc.md` §8 "Run `pylint`/`eslint` statically inside the Docker container and capture violations JSON"; also §3 §II "During the Static Analysis phase, linters (`pylint`/`eslint`) identify convention violations"*
  > *Depends on: existing Docker runtime from Milestone 2 (`services/docker_client.py`, `services/docker_runner.py`).*

- [ ] Add linter tooling to language-specific Docker base images. Update the Python base image to include `pylint` pre-installed; update the JavaScript/TypeScript base images to include `eslint` with a default configuration. Pin linter versions for reproducibility. Document the updated image specifications in `docs/deployment.md`. — *`docs/design-doc.md` §3 §II "linters (`pylint`/`eslint`) identify convention violations"*
  > *Depends on: existing base images from Milestone 2 (`services/sandbox_images.py`). The linter execution task above depends on these updated images.*

---

## Dom — Pipeline Logic: Three-Pass AI Evaluation, Schema Validation, Human Review Flag (9 tasks)

**Summary:** By the end of these tasks, the evaluation pipeline will orchestrate three sequential LLM passes after deterministic scoring completes. Pass 1 will reconcile test results against the rubric, Pass 2 will conditionally run style review with RAG-retrieved excerpts and linter output, and Pass 3 will synthesize everything into the final MAPLE Standard Response Envelope. JSON schema validation will catch malformed LLM output with one repair retry. The `NEEDS_HUMAN_REVIEW` flag will be set for ambiguous rubric criteria, low-confidence scores, and no-match retrieval. The `ai_feedback_json` field on `EvaluationResult` (currently null) will be populated. Unit tests for each pass can be written against mock LLM responses; full integration requires Jayden's LLM wrapper and RAG retrieval to be operational.

**Tasks:**

### Schema & Validation

- [ ] Define JSON schemas for each LLM pass output. Create `services/llm_schemas.py` with JSON Schema definitions for: (a) Pass 1 output — test reconciliation object with per-test failure classifications (logic bug, environment, dependency, timeout, memory); (b) Pass 2 output — style findings array with file paths, line ranges, rule references, and severity; (c) Pass 3 output — final MAPLE Standard Response Envelope with `criteria_scores` (0–100 scale, score level, justification, confidence, optional `RecommendationObject`), `deterministic_score`, `metadata`, and `flags` arrays. The `RecommendationObject` schema must require: file path, line range, original snippet, revised snippet, and Git-style diff. — *`docs/design-doc.md` §4 "The output is a strict JSON object shaped for downstream rendering"; also §4 "Recommendation objects include file path, line range, original snippet, revised snippet, and a Git-style diff"*
  > *No cross-section dependencies. These schemas are consumed by the validation task and each pass implementation.*

- [ ] Implement JSON schema validation with one repair retry. Create `services/llm_validator.py` with a `validate_and_repair(raw_json: str, schema: dict, llm_complete_fn, repair_prompt: str) -> dict` function. Parse the LLM output as JSON; validate against the appropriate pass schema. If validation fails, send a repair prompt to the same model with the raw output and the validation errors, requesting a corrected version. If the second output also fails validation, raise an `EvaluationFailedError` that the pipeline catches to mark the submission `EVALUATION_FAILED`. — *`docs/design-doc.md` §8 "Implement JSON schema validation on model output; one repair retry on malformed response; mark `EVALUATION_FAILED` if second output is still invalid"; also §4 "If the model returns malformed JSON, the backend performs one repair retry. If the second output is still invalid, the submission is marked `EVALUATION_FAILED` for human review"*
  > *Depends on: JSON schema definitions task above.*

### Three-Pass LLM Evaluation

- [ ] Implement Pass 1 (test reconciliation) in `services/ai_passes.py`. Create the Pass 1 function that takes: the parsed test results (from `test_parser.py`), rubric content, exit-code metadata, and resource constraint flags. Construct the system prompt per `docs/design-doc.md` §4 Pass 1 prompt. Call `llm.complete()` with model `gemini-3.1-pro-preview` and 60-second timeout. Validate the output against the Pass 1 JSON schema. Return the structured partial feedback object classifying each test failure (logic bug, environment issue, dependency problem, timeout, or memory error). Do not evaluate style in this pass. — *`docs/design-doc.md` §8 "Implement Pass 1 (`gemini-3.1-pro-preview`): test reconciliation against rubric; classify failures"; also §4 "Pass 1 analyzes structured test results against the rubric and classifies failures as likely logic, configuration, dependency, timeout, or memory issues"*
  > *Depends on: Jayden's `llm.complete()` implementation (retry + fallback). Depends on JSON schema validation task above. Unit-testable against mock `llm.complete()` responses.*

- [ ] Implement AST-aware code chunk extraction. Create `services/ast_chunker.py` that parses student source files into an AST and extracts terminal nodes (functions, classes, methods) as discrete logical chunks. If a node exceeds the token limit, recursively split into internal branches; if multiple nodes are undersized, merge them. Return a list of `CodeChunk` objects with file path, line range, and source text. Support Python (via `ast` stdlib), JavaScript/TypeScript, and Java. — *`docs/design-doc.md` §3 §II "The Context Optimizer utilizes an AST parser to implement an AST-Aware Chunking strategy. Unlike fixed-size splitting, this strategy extracts terminal nodes (functions, classes, or methods) as discrete logical units."*
  > *No cross-section dependencies. Fully unit-testable against fixture source files.*

- [ ] Implement Pass 2 (style and maintainability review) in `services/ai_passes.py`. Create the Pass 2 function that: (a) checks whether `enable_lint_review` is true AND linter violations exist, OR the rubric explicitly requires style/maintainability review — skip Pass 2 entirely if neither condition is met; (b) takes AST-extracted code chunks and calls Jayden's `retrieve_style_chunks()` to get RAG-retrieved style excerpts; (c) constructs the system prompt per `docs/design-doc.md` §4 Pass 2 prompt; (d) calls `llm.complete()` with model `gemini-3.1-flash-lite` and 30-second timeout; (e) validates output against the Pass 2 JSON schema. Append style findings to the shared reasoning object from Pass 1. — *`docs/design-doc.md` §8 "Implement Pass 2 (`gemini-3.1-flash-lite`, conditional on `enable_lint_review` flag + linter violations or rubric style criteria): AST-aware code chunk extraction + RAG-retrieved style excerpts"; also §4 "Pass 2 runs only when `enable_lint_review` is true AND static analysis returns violations, OR the rubric explicitly requires style or maintainability review"*
  > *Depends on: Pass 1 task above (Pass 2 appends to the Pass 1 reasoning object). Depends on Jayden's `retrieve_style_chunks()` and linter execution tasks. Depends on AST chunker task above.*

- [ ] Implement Pass 3 (synthesis) in `services/ai_passes.py`. Create the Pass 3 function that takes the combined reasoning object from Passes 1 and 2. Construct the system prompt per `docs/design-doc.md` §4 Pass 3 prompt. Call `llm.complete()` with model `gemini-3.1-pro-preview` and 60-second timeout. Validate output against the Pass 3 JSON schema (MAPLE Standard Response Envelope). For every rubric criterion scoring below "Exemplary," generate a `RecommendationObject` only when an exact file path, line range, and code snippet are present in evidence. Preserve uncertainty flags from earlier passes. — *`docs/design-doc.md` §8 "Implement Pass 3 (`gemini-3.1-pro-preview`): synthesize into MAPLE Standard Response Envelope; emit `RecommendationObject` only when file path, line range, and code snippet are present"; also §4 "Only emit a RecommendationObject when an exact file path, line range, and code snippet are present in evidence"*
  > *Depends on: Pass 2 task above (or Pass 1 if Pass 2 is skipped). Depends on Jayden's `llm.complete()` implementation.*

### Pipeline Orchestration & Persistence

- [ ] Implement `NEEDS_HUMAN_REVIEW` flag logic. In the pipeline orchestration, set the `NEEDS_HUMAN_REVIEW` flag in the `flags` array of the final output when any of the following conditions are met: (a) ambiguous rubric language detected (model returns `NEEDS_HUMAN_REVIEW` for a criterion); (b) low confidence score on any criterion (below a configurable threshold); (c) RAG retrieval returned `retrieval_status: "no_match"` (no style chunks above 0.75 threshold); (d) unsupported language detected (no matching style guide). When this flag is set, submission status should be set to `Awaiting Review` instead of `Completed`. — *`docs/design-doc.md` §8 "Implement `NEEDS_HUMAN_REVIEW` flag for ambiguous rubric language, low confidence, and no-match retrieval"; also §4 "If evidence is insufficient or conflicting, mark the affected criterion as NEEDS_HUMAN_REVIEW"; also §3 §II "For unsupported languages, the system surfaces a `NEEDS_HUMAN_REVIEW` flag"*

- [ ] Extend `pipeline.py` to orchestrate AI passes after deterministic scoring. After the existing `calculate_deterministic_score` and `persist_evaluation_result` calls in `services/pipeline.py`, add an `"Evaluating"` status phase. Run Pass 1, conditionally run Pass 2 (check `assignment.enable_lint_review` and linter output), then run Pass 3. Update the `EvaluationResult` record's `ai_feedback_json` field with the final MAPLE Standard Response Envelope. Include `style_guide_version` in `metadata_json`. Update submission status to `Completed` (or `Awaiting Review` if `NEEDS_HUMAN_REVIEW` flag is set). Catch `EvaluationFailedError` from schema validation and set status to `EVALUATION_FAILED`. — *`docs/design-doc.md` §8 actionable steps (pipeline orchestration is implicit across all pass steps); also §2 "Data Model — EvaluationResult" (`ai_feedback_json` field)*
  > *Depends on: all three Pass implementations, `NEEDS_HUMAN_REVIEW` flag logic, and Jayden's LLM/RAG/linter infrastructure tasks.*

- [ ] Update `persist_evaluation_result()` to store `ai_feedback_json`. Modify `services/submissions.py` `persist_evaluation_result()` (currently hardcodes `ai_feedback_json=None`) to accept an optional `ai_feedback_json` parameter. Also add an `update_evaluation_result()` function that can update an existing `EvaluationResult` record's `ai_feedback_json` after the AI passes complete (since deterministic scoring persists the record first, and AI passes run afterward). — *`docs/design-doc.md` §2 "Data Model — EvaluationResult" (`ai_feedback_json` field)*
  > *Depends on: existing `persist_evaluation_result()` from Milestone 2 (`services/submissions.py`).*

---

## Sylvie — API Contracts & Frontend: AI Feedback Endpoints, Instructor Review UI (8 tasks)

**Summary:** By the end of these tasks, the API will expose an endpoint for instructors to approve or reject AI-generated feedback before release to students. The Angular frontend will display rubric-aligned criteria scores, render `RecommendationObject` diffs, show the style guide version used in the evaluation, and provide an instructor approve/reject workflow. API contract tasks can be verified with pytest against a running server; Angular components can be developed against mock JSON fixtures and fully integrated once Dom's AI pipeline endpoints are live.

**Tasks:**

### API Contract Extensions

- [ ] Implement `POST /submissions/{id}/review` endpoint for instructor approve/reject. Create a new endpoint that accepts `{ "action": "approve" | "reject", "instructor_notes": "optional string" }`. On `approve`: update submission status from `Awaiting Review` to `Completed` and mark `ai_feedback_json` as released. On `reject`: update status to `Rejected` and store instructor notes. Only instructors (JWT role check via `require_role()`) who own the assignment may call this endpoint. Return the updated submission in the MAPLE Standard Response Envelope. — *`docs/design-doc.md` §1 User Story 6 "As an instructor, I want to review AI-generated feedback before releasing it to students so that I can correct errors and maintain final grading authority"; also §8 "instructor approve/reject AI feedback before release to students"*
  > *Depends on: Dom's `NEEDS_HUMAN_REVIEW` flag and `Awaiting Review` status implementation.*

- [ ] Extend `GET /submissions/{id}` response to include AI feedback fields. Ensure that when `ai_feedback_json` is populated, the response includes: `evaluation.ai_feedback.criteria_scores` (array), `evaluation.ai_feedback.flags` (array), `evaluation.ai_feedback.metadata` (including `style_guide_version`), and `evaluation.ai_feedback.recommendations` (array of `RecommendationObject`). Add an `evaluation.review_status` field (`"pending"`, `"approved"`, `"rejected"`) to indicate whether the instructor has reviewed the AI feedback. Only expose full `ai_feedback` to students after instructor approval. — *`docs/api-spec.md` `GET /submissions/{submission_id}` with-evaluation response; also `docs/design-doc.md` §8 "display style guide version used"*
  > *Depends on: Dom's pipeline extension that populates `ai_feedback_json`.*

- [ ] Add `review_status` and `instructor_notes` columns to `EvaluationResult` model. Add a `review_status` column (string, default `"pending"`, values: `"pending"`, `"approved"`, `"rejected"`) and an `instructor_notes` column (text, nullable) to the `EvaluationResult` model in `server/app/models/evaluation_result.py`. Create an Alembic migration for these new columns. — *`docs/design-doc.md` §1 User Story 6 "review AI-generated feedback before releasing it to students"*

### Frontend (Angular)

- [ ] Implement rubric-aligned criteria scores display component. Create an Angular component that renders the `criteria_scores` array from `ai_feedback_json`. For each criterion, display: criterion name, numeric score (0–100), score level (e.g., "Exemplary", "Proficient"), evidence-based justification text, and confidence indicator. Highlight criteria flagged with `NEEDS_HUMAN_REVIEW`. Sort criteria by rubric order. — *`docs/design-doc.md` §8 "Angular: rubric-aligned criteria scores display"; also §4 "All `criteria_scores` use a 0-100 point scale. Each criterion includes a score level, evidence-based justification, confidence field, and optional `RecommendationObject`"*
  > *Depends on: `GET /submissions/{id}` AI feedback extension task above for the data contract. Developable against mock JSON fixtures in isolation.*

- [ ] Implement `RecommendationObject` diff viewer component. Create an Angular component that renders each `RecommendationObject` as a Git-style inline diff. Display: file path, line range, original snippet (red/removed lines), revised snippet (green/added lines), and the diff. Use a monospace font and syntax highlighting. Group recommendations by file. — *`docs/design-doc.md` §8 "Angular: `RecommendationObject` diff viewer"; also §4 "Recommendation objects include file path, line range, original snippet, revised snippet, and a Git-style diff"*
  > *Depends on: criteria scores display task above (recommendations are nested within criteria).*

- [ ] Implement instructor approve/reject workflow in Angular. On the submission detail page, when the user is an instructor and `review_status` is `"pending"`, display "Approve" and "Reject" buttons. On "Approve", call `POST /submissions/{id}/review` with `action: "approve"`. On "Reject", show a text area for instructor notes and call the same endpoint with `action: "reject"` and the notes. After the action completes, refresh the submission display to reflect the updated status. Disable the AI feedback section for students until `review_status` is `"approved"`. — *`docs/design-doc.md` §8 "instructor approve/reject AI feedback before release to students"; also §1 User Story 6*
  > *Depends on: `POST /submissions/{id}/review` API endpoint task above. Depends on criteria scores display and diff viewer tasks above.*

- [ ] Display style guide version used in evaluation. In the submission detail page's evaluation metadata section, display the `style_guide_version` value from `evaluation.ai_feedback.metadata`. Show the style guide name and version (e.g., "PEP 8 (rev. 2024-06-01)") alongside the language version already displayed from M2. If multiple style guides were consulted, list all with their versions. — *`docs/design-doc.md` §8 "display style guide version used"; also §3 §II "the style guide version parsed from the ingested document [is] stored in `metadata_json` and displayed to the instructor in the review UI"*
  > *Depends on: `GET /submissions/{id}` AI feedback extension task above.*

- [ ] Add `Awaiting Review` and `EVALUATION_FAILED` to terminal statuses in status polling. Update `TERMINAL_STATUSES` in `client/src/pages/status-page/status-page.component.ts` (currently `['Completed', 'Failed']`) to also include `'Awaiting Review'` and `'EVALUATION_FAILED'` so that polling stops when the AI evaluation finishes or fails. — *`docs/design-doc.md` §8 "mark `EVALUATION_FAILED` if second output is still invalid"; also §4 `NEEDS_HUMAN_REVIEW` → `Awaiting Review` status*
  > *No cross-section dependencies. Quick change to existing component.*

---

## Integration Point

The Milestone 3 deliverable connects all three workstreams in a layered architecture. Jayden's infrastructure provides the foundational services (LLM calls with retry/fallback, RAG storage and retrieval, linter execution); Dom's pipeline logic orchestrates those services into a three-pass evaluation sequence, validates the output, and persists the result; Sylvie's API contracts and Angular UI surface the AI feedback to instructors for review before release to students.

Each workstream is scoped for independent testing before full integration:

1. **Jayden** — verify `llm.complete()` against mock/real LLM providers (retry, fallback, timeouts); verify pgvector CRUD operations and cosine similarity retrieval against test embeddings; verify linter execution produces structured JSON from Docker containers. No pipeline business logic required.
2. **Dom** — unit test each AI pass against mock `llm.complete()` responses; verify JSON schema validation with intentionally malformed fixtures; verify `NEEDS_HUMAN_REVIEW` flag triggers against edge-case inputs. Full integration requires Jayden's LLM wrapper and RAG retrieval.
3. **Sylvie** — verify API contracts with pytest against mock data; develop Angular components against JSON fixtures matching the Pass 3 output schema. Full end-to-end requires Dom's pipeline to populate `ai_feedback_json`.

**End-to-end verification:** Instructor creates assignment with `enable_lint_review: true` and rubric → student submits GitHub URL via Angular form → `POST /evaluate` returns `submission_id` → deterministic scoring runs (M2 pipeline) → pipeline enters `"Evaluating"` phase → Pass 1 classifies test failures against rubric → linters run inside Docker, RAG retrieves style excerpts → Pass 2 appends style findings → Pass 3 synthesizes MAPLE Standard Response Envelope → `ai_feedback_json` persisted → submission status set to `Awaiting Review` (if `NEEDS_HUMAN_REVIEW`) or `Completed` → Angular polls and renders criteria scores + recommendation diffs → instructor approves or rejects → feedback released to student — all within the evaluation pipeline. *(Source: `docs/design-doc.md` §8 Milestone 3 deliverable; §1 User Story 6; §4 AI Integration Specification)*

---

## Traceability Summary

| # | Task (short label) | Assignee | Source file | Marker | Verdict |
|---|---|---|---|---|---|
| 1 | LLM `complete()` retry + backoff | Jayden | `docs/design-doc.md` | §8 "2-retry-per-model logic with exponential backoff"; §4 "Retry Policy" | pending |
| 2 | Model fallback chain + timeouts | Jayden | `docs/design-doc.md` | §8 "timeouts (30s standard, 60s complex); model fallback chain"; §4 fallback spec | pending |
| 3 | pgvector schema for style chunks | Jayden | `docs/design-doc.md` | §3 §II chunk metadata fields; §8 "store in pgvector" | pending |
| 4 | Style guide fetch + ingestion | Jayden | `docs/design-doc.md` | §8 "Fetch and ingest style guides"; §3 §II source URLs | pending |
| 5 | Semantic chunking + embedding | Jayden | `docs/design-doc.md` | §8 "Chunk by semantic heading/rule block; embed with text-embedding-3-large" | pending |
| 6 | Cosine similarity retrieval | Jayden | `docs/design-doc.md` | §8 "cosine similarity retrieval: top-5 chunks, threshold 0.75"; §4 retrieval spec | pending |
| 7 | Linter execution in Docker | Jayden | `docs/design-doc.md` | §8 "Run pylint/eslint inside Docker container"; §3 §II "Static Analysis" | pending |
| 8 | Linter tooling in base images | Jayden | `docs/design-doc.md` | §3 §II "linters (pylint/eslint)" | pending |
| 9 | JSON schemas for pass outputs | Dom | `docs/design-doc.md` | §4 output schema; RecommendationObject spec | pending |
| 10 | Schema validation + repair retry | Dom | `docs/design-doc.md` | §8 "JSON schema validation; one repair retry"; §4 repair spec | pending |
| 11 | Pass 1 test reconciliation | Dom | `docs/design-doc.md` | §8 "Implement Pass 1"; §4 Pass 1 prompt + spec | pending |
| 12 | AST-aware code chunk extraction | Dom | `docs/design-doc.md` | §3 §II "AST-Aware Chunking strategy" | pending |
| 13 | Pass 2 style review (conditional) | Dom | `docs/design-doc.md` | §8 "Implement Pass 2"; §4 Pass 2 trigger conditions + prompt | pending |
| 14 | Pass 3 synthesis | Dom | `docs/design-doc.md` | §8 "Implement Pass 3"; §4 Pass 3 prompt + RecommendationObject rules | pending |
| 15 | `NEEDS_HUMAN_REVIEW` flag logic | Dom | `docs/design-doc.md` | §8 "NEEDS_HUMAN_REVIEW flag"; §4 "mark criterion as NEEDS_HUMAN_REVIEW" | pending |
| 16 | Pipeline orchestration (AI passes) | Dom | `docs/design-doc.md` | §8 pipeline orchestration (implicit); §2 `ai_feedback_json` field | pending |
| 17 | Update `persist_evaluation_result` | Dom | `docs/design-doc.md` | §2 "Data Model — EvaluationResult" `ai_feedback_json` | pending |
| 18 | `POST /submissions/{id}/review` API | Sylvie | `docs/design-doc.md` | §1 User Story 6; §8 "approve/reject AI feedback" | pending |
| 19 | `GET /submissions/{id}` AI fields | Sylvie | `docs/api-spec.md` + `docs/design-doc.md` | `GET /submissions/{id}` response; §8 "display style guide version" | pending |
| 20 | `review_status` model columns | Sylvie | `docs/design-doc.md` | §1 User Story 6 (instructor review before release) | pending |
| 21 | Criteria scores display (Angular) | Sylvie | `docs/design-doc.md` | §8 "rubric-aligned criteria scores display"; §4 criteria_scores spec | pending |
| 22 | RecommendationObject diff viewer | Sylvie | `docs/design-doc.md` | §8 "RecommendationObject diff viewer"; §4 RecommendationObject spec | pending |
| 23 | Instructor approve/reject UI | Sylvie | `docs/design-doc.md` | §8 "instructor approve/reject"; §1 User Story 6 | pending |
| 24 | Style guide version display | Sylvie | `docs/design-doc.md` | §8 "display style guide version used"; §3 §II version detection | pending |
| 25 | Terminal statuses update (Angular) | Sylvie | `docs/design-doc.md` | §8 "EVALUATION_FAILED"; §4 `NEEDS_HUMAN_REVIEW` → `Awaiting Review` | pending |
| E2E | End-to-end three-pass AI evaluation | All | `docs/design-doc.md` | §8 M3 deliverable | pending |
