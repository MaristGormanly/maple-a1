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
