# Repository Guidelines

## Project Structure & Module Organization

MAPLE A1 is split into an Angular client and FastAPI backend. Frontend code lives in `client/src/`, with reusable UI in `components/`, route pages in `pages/`, API helpers in `services/`, guards/interceptors in their own folders, and global styles in `styles.scss`. Backend code lives in `server/app/`, with routers and app entry in `main.py`, ORM models in `models/`, business logic in `services/`, auth/rate-limit middleware in `middleware/`, and shared helpers in `utils/`. Backend tests are in `server/tests/`; frontend specs sit beside components as `*.spec.ts`. Alembic migrations are in `alembic/`, evaluation utilities in `eval/`, and architecture/API/deployment docs in `docs/`.

## Build, Test, and Development Commands

Run backend commands from `server/` unless noted:

```bash
pip install -r requirements.txt
uvicorn server.app.main:app --reload --reload-dir server
pytest tests/
pytest tests/test_cache.py
```

Run frontend commands from `client/`:

```bash
npm install
npm start
npm run build
npm test
```

Run database migrations from the repository root:

```bash
alembic upgrade head
alembic revision --autogenerate -m "describe change"
```

## Coding Style & Naming Conventions

Use Python 3.12+ with async FastAPI and SQLAlchemy patterns already present in `server/app`. Keep Python modules and test files snake_case. Angular code uses standalone components; keep component folders kebab-case and class names PascalCase, for example `status-page.component.ts` and `StatusPageComponent`. TypeScript formatting follows the project Prettier config: 100-character print width and single quotes.

## Testing Guidelines

Backend tests use `pytest`; add tests under `server/tests/test_*.py`. Mark opt-in end-to-end smoke tests with `@pytest.mark.smoke` because they require a running backend. Frontend tests use Vitest through Angular CLI; name specs `*.spec.ts` next to the implementation. Cover API envelope behavior, auth paths, status transitions, and pipeline edge cases when changing shared backend flows.

## Commit & Pull Request Guidelines

Recent history mixes conventional commits (`feat:`, `fix(client):`, `feat(pipeline):`) with short imperative summaries. Prefer conventional commits with an optional scope, for example `fix(client): handle failed status polling`. Pull requests should include a concise description, linked issue or milestone task when available, test commands run, migration notes, and screenshots for UI changes.

## Security & Configuration Tips

Never commit `.env` or real credentials. Start from `.env.example` and set `DATABASE_URL`, `SECRET_KEY`, and `GITHUB_PAT`; optional LLM keys belong only in local or deployment environments. Keep production host, Nginx, and systemd changes documented in `docs/deployment.md`.
