# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MAPLE A1 is a code submission evaluator: students submit GitHub repo URLs, the backend clones and preprocesses them, and AI evaluates submissions against instructor rubrics. The system is at Milestone 1 (core infrastructure complete); Milestone 2+ covers Docker sandbox execution, LLM evaluation, and RAG-based rubric retrieval.

## Commands

### Backend (FastAPI — run from `server/`)
```bash
pip install -r requirements.txt
uvicorn server.app.main:app --reload        # Dev server on :8000
pytest tests/                               # All tests
pytest tests/test_cache.py                  # Single test file
```

### Frontend (Angular — run from `client/`)
```bash
npm install
ng serve                                    # Dev server on :4200
ng build                                    # Production build
npm test                                    # Vitest test suite
```

### Database Migrations (from repo root)
```bash
alembic upgrade head                        # Apply migrations
alembic revision --autogenerate -m "desc"  # New migration
```

## Architecture

```
Angular (client/)  →  FastAPI (server/)  →  PostgreSQL + pgvector
                                         →  Docker (sandbox, Milestone 2+)
```

### Request Flow
1. Angular `SubmitPageComponent` POSTs multipart/form-data (GitHub URL, assignment ID, rubric) to `POST /api/v1/code-eval/evaluate`
2. FastAPI clones repo via GitHub PAT, runs `preprocessing.py` to strip `.git`, `node_modules`, binaries
3. Cache system (`cache.py`) keys on `commit_hash::rubric_digest` → 16-char SHA256 path token, with `fcntl` file locking
4. Returns `submission_id`; Angular `StatusPageComponent` polls for results

### Response Envelope
All API responses use the MAPLE Standard Envelope (`server/app/utils/responses.py`):
```json
{ "success": bool, "data": {...}, "error": null|string, "metadata": {...} }
```

### Authentication
- OAuth2 Bearer JWT (`HS256`, signed with `SECRET_KEY`)
- RBAC via `require_role()` in `server/app/middleware/auth.py`
- Frontend uses a hardcoded `devToken` in `environments/environment.ts` — to be replaced with auth service in Milestone 2

### LLM Redactor
Before any external LLM call, `server/app/services/llm.py` strips GitHub PATs (`gh[ps]_[A-Za-z0-9_]{36,}`), email addresses, and env var values from content.

## Key Configuration

Backend settings loaded via `pydantic-settings` from `.env` or environment:
- **Required:** `DATABASE_URL`, `SECRET_KEY`, `GITHUB_PAT`
- **Optional:** `APP_ENV`, `CORS_ORIGINS` (comma-separated), `ACCESS_TOKEN_EXPIRE_MINUTES` (default 30)

See `.env.example` for the full template.

Frontend environments:
- Dev: `client/src/environments/environment.ts` → `apiBaseUrl: 'http://localhost:8000'`
- Prod: `client/src/environments/environment.prod.ts` → `apiBaseUrl: 'https://api.maple-a1.com'`

## Database

5 tables: `users`, `assignments`, `rubrics`, `submissions`, `evaluation_results`. ORM models in `server/app/models/`. Single Alembic migration: `alembic/versions/010126822022_create_initial_schema.py`. Uses `asyncpg` for async PostgreSQL access.

## Production

DigitalOcean Droplet (Ubuntu LTS, 4GB/2vCPU). Systemd service `maple-a1.service`, Nginx reverse proxy → `127.0.0.1:8000`. See `docs/deployment.md` for full procedures.

## Docs

- `docs/design-doc.md` — full system architecture and design decisions
- `docs/api-spec.md` — complete endpoint reference
- `docs/milestones/milestone-01-tasks.md` — ownership (Jayden: infra, Dom: backend, Sylvie: ingestion/cache/Angular scaffold)
