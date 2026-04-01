My Prompt: """Task: Review the tasks for Dom in @milestone-01-tasks.md. Break down and implement Dom's three tasks following the implementation plan in @dom_milestone_1_plan_ecb9a209.plan.md. Refer to @design-doc.md and the MAPLE Architecture Guide for specifications. Do NOT modify or overwrite any of Jayden's or Sylvie's existing code."""

Meta Prompt:

**Objective**

Execute the **implementation plan** defined in `prompts/dev/dom/dom_milestone_1_plan_ecb9a209.plan.md` to complete **Dom's Backend API, Database & Security** scope in `milestone-01-tasks.md`. Stay aligned with the **Milestone 1 goal** (deployable skeleton: DB, auth scaffold, repo ingestion; local E2E: URL → clone/pre-process → `submission_id`) and the **cross-team Integration Point** described at the bottom of that file.

**Inputs to use**

1. **`prompts/dev/dom/dom_milestone_1_plan_ecb9a209.plan.md`** — The primary implementation guide. Follow the task order, file paths, model schemas, acceptance criteria, and "Existing Code Inventory (DO NOT MODIFY)" section exactly. This document is authoritative for what to build, where to put it, and what not to touch.
2. **`docs/milestones/milestone-01-tasks.md`** — Dom's three checkboxes define the scope boundary. Do not implement tasks from Jayden's or Sylvie's sections. Use the **Goal**, **Deliverable**, and **Integration Point** sections to ensure Dom's outputs support the end-to-end flow.
3. **`docs/design-doc.md`** — The canonical design document. Use Section 2 (Data Model) for exact entity fields and relationships, Section 2 (API Design) for the `POST /rubrics` request/response contract, and Sections 3–4 for Regex Redactor targets. Resolve ambiguities using this document; do not invent requirements that contradict it.
4. **MAPLE Architecture Guide** — Use Section 3 for the Standard Response Envelope and error codes, Section 4 for the A5 rubric JSON schema that the `/rubrics` endpoint must validate against, and Section 6 for the security baseline (no hardcoded secrets, input validation).

**What to produce**

Complete the three tasks in order, producing only the files listed below. Each task must pass its acceptance criteria from the plan before moving to the next.

1. **Task 1 — PostgreSQL Schema + Alembic Migrations**
   - Create `server/app/models/database.py` (async engine, session factory, `Base`, `get_db` dependency)
   - Create five model files in `server/app/models/`: `user.py`, `assignment.py`, `rubric.py`, `submission.py`, `evaluation_result.py` — with exact fields, types, foreign keys, and relationships specified in the plan
   - Create `server/app/models/__init__.py` re-exporting all models, `Base`, and `get_db`
   - Initialize Alembic with the async template (`alembic init -t async alembic`), configure `env.py` to use `settings.DATABASE_URL` and `Base.metadata`
   - Generate the initial migration via `alembic revision --autogenerate -m "create_initial_schema"`

2. **Task 2 — `POST /api/v1/code-eval/rubrics` Endpoint**
   - Create `server/app/routers/rubrics.py` with Pydantic schemas (`RubricLevel`, `RubricCriterion`, `RubricCreateRequest`) validating against the A5 rubric JSON schema from the Architecture Guide
   - Implement the `POST /rubrics` handler: validate request, persist to DB via `get_db`, return MAPLE success envelope using `success_response()` from `server.app.utils.responses`; return `error_response(400, "VALIDATION_ERROR", ...)` on invalid input
   - Wire the router into `server/app/main.py` by adding **only** the import and `app.include_router(rubrics.router, prefix="/api/v1/code-eval")` — do not modify any existing lines

3. **Task 3 — Regex Redactor in `services/llm.py`**
   - Create `server/app/services/__init__.py` (empty package init)
   - Create `server/app/services/llm.py` with `redact(text: str) -> str` and `redact_dict(data: dict) -> dict` covering: GitHub PATs (`ghp_*`, `ghs_*`), email addresses, environment variable key=value pairs
   - Include a placeholder stub for the future `complete()` LLM wrapper (Milestone 3 scope, no implementation)

**Constraints**

- **DO NOT modify** any file listed under "Existing Code Inventory" in the plan: `config.py`, `main.py` (except the one additive router line), `utils/security.py`, `utils/responses.py`, `middleware/auth.py`, `routers/auth.py`, `requirements.txt`
- **DO NOT implement** tasks belonging to other owners: no GitHub cloning, no repository pre-processor, no Angular scaffold, no infrastructure provisioning, no auth login/register replacement
- **DO NOT add** dependencies to `requirements.txt` — all required packages (`sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic-settings`) are already present
- All API responses must use the MAPLE Standard Response Envelope via the existing `success_response()` and `error_response()` helpers
- All database primary keys must be UUIDs
- Prefer **verbs and artifacts** in commit messages and code comments (e.g., "Create X", "Validate Y") rather than narration

Next prompt

> You are completing the remaining fixes for Dom's Milestone 1 tasks in the MAPLE A1 codebase. All three core deliverables (SQLAlchemy schema + migrations, POST /rubrics endpoint, Regex Redactor) are implemented but have integration and correctness gaps identified by forensic audits. You must fix ONLY these specific issues — do NOT modify any of Sylvie's ingestion pipeline logic (the evaluate_submission handler, clone/cache/preprocessing code) or Jayden's scaffold files (config.py, security.py, middleware/auth.py, routers/auth.py, utils/responses.py, requirements.txt).
>
> DO NOT OVERWRITE OR REMOVE JAYDEN OR SYLVIE'S CODE/CHANGES.
>
> Files you may modify: server/app/main.py (only the import block and exception handlers), server/app/routers/rubrics.py, alembic/versions/010126822022_create_initial_schema.py (or create a new migration).
>
> Tasks (in order):
>
> 1. Fix duplicate imports in server/app/main.py: Lines 1-6 and lines 7-38 have overlapping imports (FastAPI, Request, CORSMiddleware, settings, success_response, RequestValidationError, auth). Merge into a single clean import block. Keep all symbols needed by both Dom's code (rubrics router, exception handlers) and Sylvie's code (evaluate handler, cache, preprocessing, etc.). Use relative imports (.config, .routers, etc.) consistently since the file is inside the server/app/ package.
> 2. Fix duplicate RequestValidationError handlers in server/app/main.py: There are two @app.exception_handler(RequestValidationError) registrations (lines 407-416 and lines 425-432). FastAPI only keeps the last one, making the first dead code. Remove the second handler (lines 425-432) and keep the first handler (lines 407-416) which uses error_response from utils/responses.py for proper MAPLE envelope formatting. Ensure the kept handler's error detail formatting works for both rubrics and evaluate validation errors.
> 3. Fix unhandled ValueError for invalid rubric_id in server/app/routers/rubrics.py: At line 58, uuid.UUID(request.rubric_id) can raise ValueError if the string is non-empty but not a valid UUID. Wrap it in a try/except and return error_response(status_code=400, code="VALIDATION_ERROR", message="rubric_id must be a valid UUID").
> 4. Fix migration ORM/SQL nullability mismatch: In alembic/versions/010126822022_create_initial_schema.py, the enable_lint_review column in assignments and the status column in submissions are nullable=True but the ORM models define Python-side defaults. Add server_default=sa.false() to enable_lint_review and server_default='Pending' to status so the database enforces defaults even for raw SQL inserts. Also change both columns to nullable=False to match the ORM model intent.
> 5. Wire redactor into one application path: In server/app/main.py, import redact from server.app.services.llm and replace the manual PAT scrubbing at the clone error stderr line (stderr.decode(...).replace(github_pat, "[REDACTED]")) with a call through redact() followed by any additional PAT-specific replacement (since redact() handles PAT patterns but the specific runtime PAT value also needs direct replacement). This proves the redactor is integrated into an actual code path.
>
> Constraints:
>
> - Do NOT modify any logic inside evaluate_submission, clone_repository, validate_github_repo_access, resolve_repository_head_commit_hash, or any other Sylvie-owned function bodies beyond the specific stderr sanitization line in task 5.
> - Do NOT modify config.py, security.py, auth.py, responses.py, requirements.txt.
> - Do NOT delete or rename Sylvie's Pydantic models (SubmissionData, SubmissionResponse, etc.) or the MapleAPIError class.
> - After all changes, run ReadLints to verify no new linter errors
