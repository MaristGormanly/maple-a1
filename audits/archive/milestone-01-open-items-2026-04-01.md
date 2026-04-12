# Milestone 1 — Open Items (Post-Checkpoint Audit)

**Original auditor:** Jayden (2026-04-01T20:43:11Z)  
**This document authored by:** Sylvie  
**Date:** 2026-04-01  
**Basis:** Re-verification of every finding in `milestone-01-forensic-audit-jayden-2026-04-01T204311Z.md` against the current working tree.

---

## What was fixed

The following findings from the original audit are **closed**:

| Original severity | Finding | How resolved |
| :--- | :--- | :--- |
| Extreme | No ORM models or DB session factory | `server/app/models/` package exists with all 5 tables (`User`, `Assignment`, `Rubric`, `Submission`, `EvaluationResult`) and an async SQLAlchemy session factory in `database.py` |
| High | `POST /api/v1/code-eval/rubrics` absent | Router implemented in `server/app/routers/rubrics.py`; included in `main.py` |
| High | `services/llm.py` absent | File exists with `redact()` and `redact_dict()` covering GitHub PATs, emails, and env var values |
| Medium | `services/llm.py` `redact()` never called | `redact()` imported in `main.py` and called in `clone_repository` to sanitize clone error stderr before surfacing in API responses |
| High | API contract mismatch (JSON body vs multipart) | `docs/design-doc.md` updated this session to document `multipart/form-data` as the canonical contract |
| Low | `submission_id` shown as request field in design doc | Design doc updated this session; response note now reads "server-generated" |
| Low | `python-multipart` missing from `requirements.txt` | Present at line 11 (`python-multipart>=0.0.9,<1.0`) |
| Low | Committed JWT in `client/src/environments/environment.ts` | `devToken` is now `''`; file contains instructions to create a gitignored `environment.development.ts` local override |

---

## Remaining open items

| Severity | Owner | Issue | Location |
| :--- | :--- | :--- | :--- |
| **Extreme** | Dom + Sylvie | `submission_id` is still ephemeral — generated in memory at lines 494 and 552 of `main.py`, never written to the DB. The `Submission` ORM model exists but is unused in `evaluate_submission`. Any future `GET /submissions/{id}` or audit keyed by this ID will find nothing. | `server/app/main.py:494,552` |
| **High** | Dom | No Alembic migrations — `alembic>=1.18.0` is in `requirements.txt` but no `alembic.ini` and no `server/alembic/` migrations directory exist. Models are defined but the schema cannot be applied to any database. | `server/requirements.txt:5`; absence of `server/alembic/` |
| **High** | Dom | Auth 501 — `/auth/login` and `/auth/register` still return `501 NOT_IMPLEMENTED`. `/evaluate` requires a Bearer JWT. No self-service token issuance path exists for real users or automated test runs. | `server/app/routers/auth.py:16–30` |
| **High** | Dom | `GET /api/v1/code-eval/submissions/{id}` does not exist. Status page reads only from `history.state`; a page refresh or deep-link shows only the submission ID placeholder with no data. The component has a `TODO (Milestone 2)` comment explicitly deferring this. | `server/app/main.py` (route absent); `client/src/pages/status-page/status-page.component.ts:24–27` |
| **Medium** | Dom + Sylvie | `assignment_id` type mismatch — `/evaluate` form accepts an arbitrary string (`str \| None`). The `Submission` ORM model declares `assignment_id` as a non-nullable `UUID` foreign key to `assignments.id`. Any attempt to persist a `Submission` row will fail unless this is resolved (nullable FK, validation layer, or string-to-UUID lookup). | `server/app/main.py:104`; `server/app/models/submission.py:14–15` |
| **Medium** | Dom | `DATABASE_URL` is required at startup even for runs that only exercise the ingestion path. Blocks local dev without a running Postgres instance. | `server/app/config.py:37`; `server/app/models/database.py:5` |
| **Medium** | Dom | `docs/api-spec.md` is a three-line placeholder. No authoritative API reference exists for integrators beyond the FastAPI auto-docs. | `docs/api-spec.md` |

---

## Predictive errors (unchanged from original audit)

1. **DB writes after the fact** — Adding `Submission` persistence later will require a migration story for existing cache-only entries and a breaking change to `submission_id` semantics.
2. **Concurrent evaluate requests** — `load_repository_cache_entry` rewrites the JSON index on every cache read to bump `last_used_at`. Under parallel traffic this is a last-write-wins race condition on the index file.
3. **Production Angular build** — `environment.prod.ts` sets `devToken: ''`; production bundle will fail auth until real token issuance exists.
4. **Redactor coverage** — `redact()` is currently called only on clone error stderr. Future milestones that emit to an LLM or external logging will need additional call sites.

---

## Definition of Done (remaining)

Milestone 1 is SRS-aligned when:

1. `POST /evaluate` persists a `Submission` row and returns a durable DB-backed `submission_id`
2. Alembic migrations exist and `alembic upgrade head` applies cleanly on an empty database
3. Auth path is functional for the chosen model (JWT login or documented dev bypass)
4. `GET /api/v1/code-eval/submissions/{id}` exists; Angular status page can retrieve data on refresh
5. `assignment_id` has a defined validation strategy (nullable FK, UUID coercion, or string lookup)
7. `docs/milestones/milestone-01-tasks.md` checkboxes reflect reality

---

*References: `milestone-01-forensic-audit-jayden-2026-04-01T204311Z.md` (original); `milestone-01-forensic-audit-jayden-2026-04-01T204311Z-revised.md` (prior open-items pass)*
