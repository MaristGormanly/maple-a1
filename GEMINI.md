# MAPLE A1: Code Submission Evaluator - Project Instructions

This document provides architectural context, development conventions, and operational guidance for the MAPLE A1 module. All agentic and human contributors must adhere to these standards to ensure consistency across the project.

## 1. Project Overview
MAPLE A1 is an AI-powered code evaluation system designed to provide scalable and consistent feedback for programming assignments. It combines deterministic unit testing in secure Docker sandboxes with a three-pass LLM pipeline for rubric-aligned assessment and style review.

### Tech Stack
- **Backend:** Python 3.12+, FastAPI (Async), SQLAlchemy (Asyncpg).
- **Frontend:** Angular 21 (Standalone components), Vitest.
- **Database:** PostgreSQL 16 with `pgvector` for RAG-based style retrieval.
- **AI Models:** Gemini 3.1 Pro (Primary), Gemini 3.1 Flash (Lightweight), GPT-4o (Fallback).
- **Sandbox:** Docker Engine (Ephemeral sibling containers).

## 2. Core Workflows

### The Evaluation Pipeline
The system processes submissions through a deterministic-probabilistic hybrid pipeline:
1. **Ingestion:** Clone student repository via GitHub API, strip bloat (node_modules, .git), and compute a SHA-based cache key.
2. **Testing (Deterministic):** Execute instructor-provided tests in a hardened Docker container. Capture structured JSON results.
3. **Evaluating (Probabilistic):**
    - **Pass 1:** Reconcile test results against rubric criteria (Gemini Pro).
    - **Pass 2 (Conditional):** Perform style/maintainability review using AST-extracted code chunks and RAG-retrieved style guide excerpts (Gemini Flash).
    - **Pass 3:** Synthesize final feedback into the **MAPLE Standard Response Envelope** (Gemini Pro).
4. **Review:** Instructor approves or rejects AI feedback before releasing results.

### Forensic Audit Workflow
The project uses "Forensic Audits" located in `/audits` to track quality and milestone progress. 
- New audits follow the naming convention: `post-ui-forensic-audit-YYYY-MM-DD.md`.
- Historical audits are moved to `/audits/archive/`.

## 3. Command Reference

### Backend (from `/server`)
```bash
# Setup
pip install -r requirements.txt

# Development
uvicorn server.app.main:app --reload --reload-dir server

# Testing
pytest tests/
pytest tests/test_cache.py
```

### Frontend (from `/client`)
```bash
# Setup
npm install

# Development
ng serve

# Testing
npm test
```

### Database & Infrastructure (from root)
```bash
# Migrations
alembic upgrade head
alembic revision --autogenerate -m "description"

# Local Full Stack
docker compose up -d --build
```

## 4. Engineering Standards

### API Conventions (MAPLE Standard Envelope)
All responses must adhere to the following structure (defined in `server/app/utils/responses.py`):
```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "metadata": {
    "timestamp": "ISO-8601",
    "module": "a1",
    "version": "1.0.0"
  }
}
```

### Naming & Style
- **Python:** Snake_case for modules/files. Use type hints and async/await patterns. Adhere to PEP 8.
- **Angular:** Kebab-case for component folders/files, PascalCase for classes (e.g., `status-page.component.ts`).
- **Commits:** Prefer conventional commits (e.g., `feat(client): ...`, `fix(pipeline): ...`).

### Security
- **Redaction:** All content sent to external LLMs must be passed through the **Regex Redactor** (`server/app/services/llm.py`) to strip secrets (GitHub PATs), PII, and environment variables.
- **Secrets:** Never commit `.env` files. Use `GITHUB_TOKEN_ENCRYPTION_KEY` for encrypting PATs at rest.
- **Sandbox:** Containers must run with `--no-new-privileges`, read-only filesystems, and strict resource limits.

## 5. Directory Mapping
- `/server/app`: Core FastAPI application logic.
  - `/models`: SQLAlchemy ORM models.
  - `/routers`: API endpoint definitions.
  - `/services`: Business logic (AI pipeline, Git ingestion, Docker orchestration).
- `/client/src/app`: Angular frontend.
  - `/components`: Reusable UI elements.
  - `/pages`: Route-level components.
- `/docs`: Comprehensive specs (API, Design, Deployment, SRS).
- `/eval`: Evaluation scripts, test cases, and pilot results.
- `/alembic`: Database migration history.

## 6. AI & RAG Configuration
- **RAG Subsystem:** Uses `pgvector` for similarity search. Embeddings generated via `text-embedding-3-large`.
- **Retrieval Threshold:** 0.75 cosine similarity.
- **Model Fallback:** Primary: Gemini 3.1 Pro -> Secondary: Gemini 3.1 Flash -> Final: GPT-4o.
- **Status Flags:** Use `NEEDS_HUMAN_REVIEW` for ambiguous rubric matches or low-confidence AI output.
