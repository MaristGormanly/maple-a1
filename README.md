# M3: MAPLE A1 Code Submission Evaluator

The MAPLE A1 Code Submission Evaluator is an AI-powered grading tool for programming courses. Students submit a GitHub repository URL to an assignment ID; the backend clones and preprocesses the code, runs instructor-provided test suites in an isolated Docker sandbox, and uses a three-pass LLM pipeline to produce rubric-aligned feedback. Instructors review AI-generated scores and recommendations before releasing results to students.

## Architecture Overview

This module combines deterministic test execution with a Retrieval-Augmented Generation (RAG) pipeline. After sandboxed test runs produce structured results, the LLM evaluation layer performs three sequential passes: test reconciliation (Pass 1), conditional style review against RAG-retrieved style guide excerpts (Pass 2), and final synthesis into the MAPLE Standard Response Envelope (Pass 3). Style guide embeddings are stored in a `pgvector` retrieval subsystem within PostgreSQL. All LLM calls are routed through a centralized wrapper that enforces retry/fallback logic and redacts secrets before any data leaves the system.

* **Design doc:** [docs/design-doc.md](./docs/design-doc.md)
* **API specification:** [docs/api-spec.md](./docs/api-spec.md)
* **Deployment runbook:** [docs/deployment.md](./docs/deployment.md)

## Tech Stack

* **Backend:** Python with FastAPI (async, Uvicorn)
* **Frontend:** Angular 21 (standalone components)
* **Database:** PostgreSQL 16 with `pgvector` extension
* **AI Models:** Gemini 3.1 Pro Preview (Passes 1 & 3), Gemini 3.1 Flash Lite (Pass 2 style review), GPT-4o (final fallback); `text-embedding-3-large` for RAG embeddings
* **Sandbox:** Docker SDK (ephemeral sibling containers via `/var/run/docker.sock`)
* **Auth:** OAuth2 Bearer JWT (HS256)

## Setup & Running Locally

### 1. Prerequisites

* Python 3.12+
* Node.js (v18+)
* PostgreSQL 16 with the `pgvector` extension installed and running
* Docker (for sandboxed test execution)
* A GitHub Personal Access Token with `repo` scope

### 2. Environment Configuration

Copy the environment template and fill in your credentials:

```bash
cp .env.example .env
```

Required variables: `DATABASE_URL`, `SECRET_KEY`, `GITHUB_PAT`. Optional: `GEMINI_API_KEY`, `OPENAI_API_KEY` (Milestone 3 AI passes), `CORS_ORIGINS` (default `http://localhost:4200`).

### 3. Initialize the Database

Run from the **repository root**. Applies the Alembic migration that creates all five tables (`users`, `assignments`, `rubrics`, `submissions`, `evaluation_results`):

```bash
alembic upgrade head
```

### 4. Run the Backend Server

```bash
cd server
pip install -r requirements.txt   # Only on first run
uvicorn server.app.main:app --reload
# Server runs on http://localhost:8000
```

### 5. Run the Frontend Client

```bash
cd client
npm install   # Only on first run
ng serve
# Frontend runs on http://localhost:4200
```

## Deployment

**Production:** DigitalOcean Droplet (4 GB RAM / 2 vCPU, Ubuntu 24.04 LTS) at `161.35.125.120`. Nginx terminates TLS and reverse-proxies `/api/` to Uvicorn. The API is accessible at `https://api.maple-a1.com`. PostgreSQL is DigitalOcean Managed PostgreSQL 16 with `pgvector` enabled. Secrets live in `.env` on the Droplet — never committed. Full procedures in [docs/deployment.md](./docs/deployment.md).

## Evaluation

AI feedback quality is measured against a golden-query set as described in the design doc (§5): rubric alignment accuracy (≥80% of criteria within ±5/100 points of instructor grade), evaluation consistency (score variance ≤3 points across 5 identical runs), and instructor-rated feedback usefulness (target ≥4/5). Full evaluation scripts and results live in `eval/`.

Current Status (Milestone 3 Prototype)
---------------------------------------

* **Working:** Three-pass AI pipeline logic (Pass 1 test reconciliation, Pass 2 style review, Pass 3 synthesis) in `services/ai_passes.py`; JSON schema validation with one repair retry (`services/llm_validator.py`); `NEEDS_HUMAN_REVIEW` flag logic; pipeline orchestration (`services/pipeline.py`) storing `ai_feedback_json`; `POST /submissions/{id}/review` approve/reject endpoint; Angular criteria scores display, `RecommendationObject` diff viewer, instructor approve/reject workflow, and style guide version display; `Awaiting Review` and `EVALUATION_FAILED` terminal statuses in status polling.

* **Stubbed/Pending:** The `complete()` function in `services/llm.py` (the LLM call wrapper with retry/fallback logic) is still a `NotImplementedError` stub — Milestone 3 tasks 1 and 2 (Jayden). The RAG infrastructure (pgvector schema for style guide chunks, style guide fetch and ingestion, semantic chunking and embedding, cosine similarity retrieval) is not yet implemented — tasks 3–6. Linter execution inside Docker containers and linter tooling in base images are not yet implemented — tasks 7–8.

* **Planned:** Full end-to-end AI evaluation (all three passes live against real LLM providers with RAG-retrieved style excerpts and in-container linting), once Jayden's infrastructure tasks are complete.

Frontend Status (Milestone 3 Prototype)
-----------------------------------------

* **Implemented:** Rubric-aligned criteria scores component renders per-criterion name, score, level, justification, and confidence indicator; `NEEDS_HUMAN_REVIEW` criteria are highlighted. `RecommendationObject` diff viewer renders Git-style inline diffs grouped by file. Instructor approve/reject workflow calls `POST /submissions/{id}/review` and refreshes on completion. Style guide name and version are displayed in the evaluation metadata section.
* **Environment-based API config:** API base URL is externalized in `client/src/environments/environment.ts`.

AI Integration Summary
-----------------------

The pipeline uses a three-pass orchestrated LLM chain with conditional RAG. Based on whether `enable_lint_review` is set and linter violations exist (or the rubric explicitly requires style review), Pass 2 is either run or skipped. Style guide excerpts are retrieved from pgvector using cosine similarity with a 0.75 threshold; if no chunk clears the threshold, retrieval is skipped and `retrieval_status: "no_match"` is logged rather than passing unsupported context to the model. If Pass 3 output fails JSON schema validation, one repair retry is attempted; persistent failures mark the submission `EVALUATION_FAILED` for human review. All prompts are sanitized by the Regex Redactor before any external API call.

Milestone 3 Deviations & Architectural Notes
----------------------------------------------

To meet the Milestone 3 Lab 3 Prototype requirement for functional MVP flows, the following intentional scope adjustments were made:

1. **LLM service stub:** `services/llm.py` `complete()` raises `NotImplementedError` in the prototype. The three AI passes and pipeline orchestration are fully implemented and tested against mock responses; full end-to-end activation requires Jayden's `complete()` implementation (retry, fallback, timeouts).

2. **RAG pipeline not yet populated:** The `style_guide_chunks` pgvector table migration and ingestion pipeline are pending. Pass 2 is gated on retrieval availability; until the pipeline runs, Pass 2 returns no style findings and sets `retrieval_status: "no_match"`.

3. **Linter execution pending:** `pylint`/`eslint` integration inside Docker containers is pending. The Pass 2 trigger condition for linter violations evaluates to false when no violations are returned, so Pass 2 falls through to rubric-triggered style review only.

Team Members
-------------

| Name | Primary Responsibilities |
|---|---|
| Jayden | Infrastructure & Deployment, Docker Container Runtime, LLM Service, RAG Infrastructure, Linter Execution |
| Dom (damansingh27) | Backend API, Database & Security, Pipeline Logic, Three-Pass AI Evaluation |
| Sylvie (sylvieedelstein) | Repository Ingestion Pipeline, Frontend Scaffold, API Contracts & Angular UI (M3) |

AI Disclosure & Tools Used
---------------------------

AI tools (Claude Code) were actively used throughout development.

* **Code Scaffolding:** Used to generate initial FastAPI routing structures, SQLAlchemy models, and Angular component scaffolding.
* **Iterative Debugging:** Used to diagnose async dependency issues and integration failures across the pipeline.
* **Prompt Logs:** Full records of AI-assisted development can be found in the `prompts/dev/` directory.
