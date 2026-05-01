# MAPLE A1 — Comprehensive Forensic Audit (Post-UI Integration)

**Date:** 2026-04-30
**Auditor:** Senior Technical Auditor (Claude, forensic traversal)
**Scope:** Full repository — frontend (`client/`), backend (`server/`), persistence (`alembic/`), configuration, documentation, and test corpus
**Branch:** `dev`
**Working tree state:** dirty (UI integration changes uncommitted; see §0)

---

## Executive Summary

The MAPLE A1 codebase is at a critical juncture. The Angular UI mockup (Submit, Status, Dashboard, Login, Assignment, Shell with sidebar/routing) is fully scaffolded and visually production-ready. The Milestone 1–3 backend is conceptually complete on paper (cache, preprocessing, pipeline, AI passes, schemas, validators, RAG retriever, linter runner, Docker runner, sandbox profiles, scoring, deterministic phase, and review-flag computation are all present). Milestone 4.A (deployment hardening) is partially merged: rate limiting (4.A.5), CORS production lock (4.A.4), gitignore secrets guard (4.A.3), eval scripts (4.C.2–4.C.6), and the rollback runbook (4.D.3) are in place.

**However**, three EXTREME-severity defects make the application **unrunnable in its current state**:

1. **`server/app/main.py` cannot be imported.** The committed file (`HEAD`) declares only seven imports, but the body references **45+ undefined symbols** (e.g. `MapleAPIError`, `JSONResponse`, `_url_adapter`, `parse_github_repo_url`, `clone_repository`, `APP_VERSION`, `Path`, `asyncio`, `json`, `assignments`, `submissions`, `create_submission`, `run_pipeline`, etc.). The application crashes with `NameError`/`ModuleNotFoundError` before serving its first request.
2. **`server/app/middleware/rate_limit.py:22`** uses the wrong import prefix (`from app.utils.responses ...`) while the rest of the codebase imports as `server.app.*`. Even if main.py were repaired, the rate-limit middleware fails to import (`ModuleNotFoundError: No module named 'app'`).
3. **Two Alembic migration heads exist** (`20260419001` and `c3d4e5f6a7b8`). `alembic upgrade head` aborts with "Multiple head revisions are present" — the production deployment runbook (M4.A.6) cannot complete.

These three defects together mean the system at HEAD does not serve traffic, does not pass tests that import `app.main`, and cannot be migrated. Section 2 catalogs every observed gap; Section 3 prescribes fixes. Sections 4 and 5 cover security and efficiency.

---

## 0. Working-tree State Snapshot

```
D  audit/written-reflection.md          # tracked file deleted (moved to docs/)
M  client/src/app/app.routes.ts         # +18/−3 (new routes for shell/login/dashboard/assignment)
M  client/src/components/criteria-scores/* # major rewrite (52→ HTML, 134→ TS)
M  client/src/components/diff-viewer/*  # rewrite (46→ HTML, 141→ TS)
M  client/src/index.html                # SVG icon sprite, fonts
M  client/src/pages/status-page/*       # 341→ HTML, +150 lines TS (review panel + pipeline stages)
M  client/src/pages/submit-page/*       # 216→ HTML, +46 lines TS (file drop, validators)
M  client/src/services/evaluation.service.ts  # +1 line (devToken fallback)
M  client/src/styles.scss               # +589 lines (full design system)
?? client/src/components/shell/         # NEW — sidebar/topbar layout
?? client/src/pages/assignment-page/    # NEW
?? client/src/pages/dashboard-page/     # NEW
?? client/src/pages/login-page/         # NEW
?? docs/post-ui-integration-gaps.md     # NEW — gap doc co-authored with the UI work
?? docs/written-reflection.md           # moved from audit/
?? prompts/dev/sylvie/mockup-prompt.md
```

**Implication:** The UI work is real and substantive. None of it has been committed yet. Section 2's findings refer to the *working-tree* state (what the next commit would ship).

---

## 1. Feature Synthesis & Modular Architecture

### 1.1 Inventory of implemented features

| Layer | Module | Status (working tree) | Evidence |
|---|---|---|---|
| **Frontend** | Login page (form, SSO button, no API call) | Stubbed | [client/src/pages/login-page/login-page.component.ts:15-22](client/src/pages/login-page/login-page.component.ts#L15-L22) |
| | Dashboard page (table view, fixture data, search, filter, view toggle) | Fixture-only | [client/src/pages/dashboard-page/dashboard-page.component.ts:122-132](client/src/pages/dashboard-page/dashboard-page.component.ts#L122-L132) |
| | Submit page (FormGroup, validators, file drop) | Wired to `POST /evaluate` | [client/src/pages/submit-page/submit-page.component.ts:54-78](client/src/pages/submit-page/submit-page.component.ts#L54-L78) |
| | Status page (polling, terminal-set, pipeline stages, review panel) | Wired to `GET /submissions/{id}` and `POST /submissions/{id}/review` | [client/src/pages/status-page/status-page.component.ts:71-83](client/src/pages/status-page/status-page.component.ts#L71-L83), [200-215](client/src/pages/status-page/status-page.component.ts#L200-L215) |
| | Assignment page (form, save banner) | Stubbed | [client/src/pages/assignment-page/assignment-page.component.ts:18-20](client/src/pages/assignment-page/assignment-page.component.ts#L18-L20) |
| | Shell (sidebar, brand, user card, logout) | Routing-only | [client/src/components/shell/shell.component.ts:13-15](client/src/components/shell/shell.component.ts#L13-L15) |
| | Criteria scores component | Pure presentational | [client/src/components/criteria-scores/criteria-scores.component.ts](client/src/components/criteria-scores/criteria-scores.component.ts) |
| | Diff viewer component | Parses unified diffs from `RecommendationObject` | [client/src/components/diff-viewer/diff-viewer.component.ts:45-58](client/src/components/diff-viewer/diff-viewer.component.ts#L45-L58) |
| | Evaluation service | submitEvaluation / getSubmissionStatus / submitReview | [client/src/services/evaluation.service.ts](client/src/services/evaluation.service.ts) |
| **API routers** | `auth` (`/register`, `/login`) | Functional | [server/app/routers/auth.py](server/app/routers/auth.py) |
| | `assignments` (`POST`, `GET /{id}`) | Functional | [server/app/routers/assignments.py](server/app/routers/assignments.py) |
| | `rubrics` (`POST`) | Functional | [server/app/routers/rubrics.py](server/app/routers/rubrics.py) |
| | `submissions` (`GET /{id}`, `POST /{id}/review`) | Functional **but** depends on a broken model (§2.4) | [server/app/routers/submissions.py:43,139](server/app/routers/submissions.py#L43) |
| | `POST /evaluate` | **Broken** — declared in `main.py` which is missing 45+ symbol imports (§2.1) | [server/app/main.py:53-270](server/app/main.py#L53-L270) |
| **Services** | `pipeline.run_pipeline` | Complete (M2 + M3 phases) | [server/app/services/pipeline.py:120-227](server/app/services/pipeline.py#L120-L227) |
| | `ai_passes.run_pass1/2/3` | Complete | [server/app/services/ai_passes.py](server/app/services/ai_passes.py) |
| | `llm.complete` (Gemini + OpenAI dispatch) | Complete | [server/app/services/llm.py:234-327](server/app/services/llm.py#L234-L327) |
| | `llm_validator.validate_and_repair` | Complete | [server/app/services/llm_validator.py:128-181](server/app/services/llm_validator.py#L128-L181) |
| | `llm_schemas` (Pass 1/2/3 + RecommendationObject) | Complete | [server/app/services/llm_schemas.py](server/app/services/llm_schemas.py) |
| | `review_flags.compute_review_flags` | Complete | [server/app/services/review_flags.py:58-126](server/app/services/review_flags.py#L58-L126) |
| | `ast_chunker.extract_chunks` | Python AST + regex fallback | [server/app/services/ast_chunker.py](server/app/services/ast_chunker.py) |
| | `embeddings.embed_text` (text-embedding-3-large @ 1536d) | Complete | [server/app/services/embeddings.py:16-31](server/app/services/embeddings.py#L16-L31) |
| | `rag_retriever.retrieve_style_chunks` | Complete | [server/app/services/rag_retriever.py:34-81](server/app/services/rag_retriever.py#L34-L81) |
| | `style_guide_ingester` | Complete | [server/app/services/style_guide_ingester.py](server/app/services/style_guide_ingester.py) |
| | `linter_runner.run_linter` | Complete | [server/app/services/linter_runner.py:106-159](server/app/services/linter_runner.py#L106-L159) |
| | `docker_client.run_container` | Complete | [server/app/services/docker_client.py:62-114](server/app/services/docker_client.py#L62-L114) |
| | `docker_runner.run_container` | Complete | [server/app/services/docker_runner.py](server/app/services/docker_runner.py) |
| | `sandbox_images` (Python/Java/JS/TS profiles) | Complete | [server/app/services/sandbox_images.py:28-57](server/app/services/sandbox_images.py#L28-L57) |
| | `language_detector.detect_language_version` | Complete | [server/app/services/language_detector.py](server/app/services/language_detector.py) |
| | `test_parser.parse_test_results` (pytest/junit/jest) | Complete | [server/app/services/test_parser.py](server/app/services/test_parser.py) |
| | `log_normalizer.normalize_logs` (2KB head + 5KB tail) | Complete | [server/app/services/log_normalizer.py](server/app/services/log_normalizer.py) |
| | `scoring.calculate_deterministic_score` | Complete (weighted + simple) | [server/app/services/scoring.py](server/app/services/scoring.py) |
| | `submissions.persist/update_evaluation_result` | Complete | [server/app/services/submissions.py](server/app/services/submissions.py) |
| | `assignments.create/get/parse/validate` | Complete | [server/app/services/assignments.py](server/app/services/assignments.py) |
| **Persistence** | `users`, `assignments`, `rubrics`, `submissions`, `evaluation_results`, `style_guide_chunks` | Migrations exist | [alembic/versions/](alembic/versions/) |
| | `evaluation_results.review_status` + `instructor_notes` columns | Migration exists; **ORM model does not declare them** (§2.4) | [alembic/versions/20260419001_add_review_columns_to_evaluation_results.py](alembic/versions/20260419001_add_review_columns_to_evaluation_results.py) vs. [server/app/models/evaluation_result.py](server/app/models/evaluation_result.py) |
| **Middleware** | `auth.get_current_user`, `require_role` | Functional | [server/app/middleware/auth.py:29-89](server/app/middleware/auth.py#L29-L89) |
| | Rate limiter (slowapi, 30/min, 5/min on `/evaluate`) | **Cannot import** — wrong package prefix (§2.2) | [server/app/middleware/rate_limit.py:22](server/app/middleware/rate_limit.py#L22) |

### 1.2 Dependency map

```
Browser (Angular SPA)
  └─ HttpClient (evaluation.service.ts) ──► Bearer dev-JWT
        ├─ POST /evaluate (multipart) ──► main.evaluate_submission ──► cache.py + preprocessing.py + pipeline.run_pipeline
        ├─ GET  /submissions/{id}     ──► submissions.get_submission ──► Submission ORM ──► EvaluationResult ORM
        └─ POST /submissions/{id}/review ──► submissions.review_submission ──► require_role("Instructor")

Pipeline (run_pipeline)
  ├─ update_submission_status("Testing")
  ├─ docker_client.run_container ──► docker_runner ──► sandbox_images.SANDBOX_PROFILES
  ├─ test_parser.parse_test_results ──► scoring.calculate_deterministic_score
  ├─ persist_evaluation_result
  └─ if _is_llm_ready():
        _run_evaluating_phase
          ├─ ast_chunker.extract_chunks
          ├─ optional linter_runner.run_linter (lazy import)
          ├─ optional rag_retriever.retrieve_style_chunks (lazy import)
          ├─ ai_passes.run_pass1   ──► llm.complete (model=… ⚠ §2.6)
          ├─ ai_passes.run_pass2   ──► RAG + Pass 1 results
          ├─ ai_passes.run_pass3   ──► synthesis ──► review_flags.compute_review_flags
          ├─ update_evaluation_result(ai_feedback_json=envelope)
          └─ update_submission_status("Awaiting Review" | "Completed" | "EVALUATION_FAILED")
```

### 1.3 Notable architectural strengths

- **LLM redaction** (`server/app/services/llm.py:37-44`) is invoked on every `complete()` call before dispatch. GitHub PATs, emails, and uppercase env-style assignments are stripped.
- **Cache file locking** (`server/app/cache.py:78-87`) uses `fcntl.LOCK_EX` for index mutations — concurrent /evaluate calls cannot corrupt the cache index.
- **Pure-function modules** (`scoring.py`, `test_parser.py`, `log_normalizer.py`, `review_flags.py`, `language_detector.py`) carry no DB / IO state, are independently unit-testable, and have a strong test surface in `server/tests/`.
- **MAPLE Standard Envelope** (`server/app/utils/responses.py`) is consistently applied across all routers and across the frontend types in `client/src/utils/api.types.ts`.

---

## 2. Ambiguities, Predictive Errors, & Interface Mismatches

| Severity | Error Cause | Error Explanation | Origin Location(s) |
|:---|:---|:---|:---|
| **Extreme** | `main.py` references 45+ undefined names | The committed file has only seven `from … import …` lines but uses `MapleAPIError`, `JSONResponse`, `_url_adapter`, `APP_VERSION`, `parse_github_repo_url`, `validate_github_repo_access`, `resolve_repository_head_commit_hash`, `clone_repository`, `preprocess_repository`, `create_staging_clone_path`, `determine_raw_clone_path`, `build_repository_cache_key`, `fingerprint_rubric_content`, `load_repository_cache_entry`, `save_repository_cache_entry`, `create_repository_cache_entry`, `CACHE_INDEX_PATH`, `PROJECT_ROOT`, `Path`, `asyncio`, `shutil`, `json`, `UUID`, `Any`, `UploadFile`, `Form`, `File`, `Depends`, `AsyncSession`, `get_db`, `get_current_user`, `parse_assignment_id`, `validate_assignment_exists`, `get_required_github_pat`, `run_pipeline`, `create_submission`, `assignments`, `submissions`, `SubmissionResponse`, `SubmissionData`, `RepositoryCacheError`, `RepositoryPreprocessingError`, `ValidationError`, `build_response_metadata`, `build_error_response`. None are declared. The module raises `NameError` at import time. Tests that `from app.main import GitHubRepoMetadata, MapleAPIError, app` (test_evaluate_submission_integration.py:17) fail at collection. | [server/app/main.py:1-275](server/app/main.py) |
| **Extreme** | Rate-limit middleware uses wrong package root | Line 22 imports `from app.utils.responses import error_response`. The rest of the project consistently uses `from server.app.utils.responses ...`. When `server.app.main` imports the rate-limit module, Python raises `ModuleNotFoundError: No module named 'app'`. This blocks startup *before* main.py's missing-name failures even surface. | [server/app/middleware/rate_limit.py:22](server/app/middleware/rate_limit.py#L22) |
| **Extreme** | Two Alembic migration heads | `20260419001` (review columns) and `b2c3d4e5f6a7 → c3d4e5f6a7b8` (pgvector chain) both descend from `010126822022` without a merge revision. Confirmed: `alembic heads` returns two head revisions. M4.A.6 (`alembic upgrade head`) fails until a merge revision is added. | [alembic/versions/20260419001_add_review_columns_to_evaluation_results.py:15](alembic/versions/20260419001_add_review_columns_to_evaluation_results.py#L15), [alembic/versions/b2c3d4e5f6a7_add_style_guide_chunks.py:13](alembic/versions/b2c3d4e5f6a7_add_style_guide_chunks.py#L13) |
| **High** | `EvaluationResult` ORM does not declare the columns added by `20260419001` | The migration adds `review_status` (NOT NULL DEFAULT `'pending'`) and `instructor_notes` (TEXT NULL). The ORM `EvaluationResult` class still has only six columns and no `review_status` / `instructor_notes` mapped attributes. `submissions.py` reads `er.review_status` (line 100), writes `submission.evaluation_result.review_status = "approved"` (line 185), and `instructor_notes = body.instructor_notes` (line 189). At runtime SQLAlchemy raises `AttributeError: 'EvaluationResult' object has no attribute 'review_status'` for the read path; the write path silently sets a Python attribute that is never persisted. The status page review panel can therefore *never* be activated against this build. | [server/app/models/evaluation_result.py:1-24](server/app/models/evaluation_result.py), [server/app/routers/submissions.py:100,185,189,206-207](server/app/routers/submissions.py#L100) |
| **High** | `ai_passes` calls `llm.complete(model=…)` but the function does not accept `model` | `_invoke_complete` in `ai_passes.py:160-183` builds `kwargs={"system_prompt", "messages", "model", "max_tokens", "temperature"}` and forwards them. The `inspect.signature` check only opportunistically adds `timeout`; it never *removes* unsupported kwargs. The real `llm.complete` (`llm.py:234`) takes `(system_prompt, messages, *, complexity, max_tokens, temperature)` — `model` is not declared, so calling it raises `TypeError: complete() got an unexpected keyword argument 'model'` (and `complexity` is silently never specified). When `_is_llm_ready()` returns True (i.e. the moment the M3 phase is supposed to come online), every Pass-1 call fails. The pipeline catches generic exceptions inside `_run_evaluating_phase` and routes them to `EVALUATION_FAILED` → submissions silently mass-fail. | [server/app/services/ai_passes.py:160-196,256](server/app/services/ai_passes.py#L160-L196), [server/app/services/llm.py:234-241](server/app/services/llm.py#L234-L241) |
| **High** | `pipeline.py` imports `clone_repository` from `..main` but main.py does not declare it | `_run_pipeline` at line 148 does `from .. import main as app_main` then `await app_main.clone_repository(suite_url, …)`. Combined with §2.1, this means even if main.py is partially repaired, `clone_repository` must also be re-implemented or the test-suite clone step crashes the pipeline. | [server/app/services/pipeline.py:147-150](server/app/services/pipeline.py#L147-L150) |
| **High** | `auth.register` accepts arbitrary `role` strings from the request body | `RegisterRequest.role: str = "Student"` allows any string, including `"Instructor"` or `"Admin"`. Anyone hitting `POST /auth/register` (no auth required) can self-elevate to Instructor and then approve/reject any submission belonging to any assignment they create themselves. With the cross-assignment ownership check at `submissions.py:170` this is bounded, but the `POST /assignments` endpoint requires only `get_current_user` (no role check) — an Instructor self-registered through this hole becomes an end-to-end backdoor. | [server/app/routers/auth.py:15-19,27-45](server/app/routers/auth.py#L15-L19), [server/app/routers/assignments.py:40-67](server/app/routers/assignments.py#L40-L67) |
| **High** | Front-end has no auth guards | Routes `/dashboard`, `/submit`, `/status/:id`, `/assignment` are all reachable without a valid `devToken`. A user with just the SPA URL can navigate the instructor surface; only the backend stops them — and only when `devToken` is empty (production builds). For local dev, the empty `devToken` produces `Authorization: Bearer ` which the backend rejects as `AUTH_ERROR`, but for any deployed build with a valid token baked into the bundle the SPA effectively has no client-side gate. | [client/src/app/app.routes.ts:9-23](client/src/app/app.routes.ts#L9-L23), [client/src/services/evaluation.service.ts:30,55,82](client/src/services/evaluation.service.ts#L30) |
| **Medium** | `submit-page.component.ts` requires `studentId` form field that the backend does not accept | `studentId` is a `Validators.required` control, but the form value is not sent to `POST /evaluate` (`evaluation.service.ts:22-25` only appends `github_url`, `assignment_id`, `rubric`). The backend has no field for it (the response derives `student_id` from the JWT `sub` claim). The required validator forces the instructor to type something that is silently dropped. The submitted value is preserved only in `history.state.studentLabel` for the next page's breadcrumb — useful for the UI, but the SRS treats it as a data-collection field that does not exist. | [client/src/pages/submit-page/submit-page.component.ts:17,64-77](client/src/pages/submit-page/submit-page.component.ts#L17), [client/src/services/evaluation.service.ts:17-32](client/src/services/evaluation.service.ts#L17-L32) |
| **Medium** | `dashboard-page` uses entirely fixture data | `SUBMISSIONS` is a hardcoded array of nine pretend rows; there is no `GET /submissions` endpoint. An instructor pointed at a live backend will see fake rows and stale "Awaiting Review" / "Completed" badges with no path to real records. The `viewStatus()` handler navigates to `/status/:id` with `FIXTURE_STATUS[r.id]` — clicking on any row except `a3f1c82e-…` produces a status page with `null` data and an infinite poll loop. | [client/src/pages/dashboard-page/dashboard-page.component.ts:122-186](client/src/pages/dashboard-page/dashboard-page.component.ts#L122-L186) |
| **Medium** | `assignment-page` is not wired to `POST /assignments` | `create()` sets `saved=true` and renders a hardcoded UUID (`a7f3c21e-80b4-4d9c-9e15-6b2d8f4c9a01`) that never came from the backend. The form is missing `rubric_id` and includes `dueDate` (the API does not accept `dueDate`). | [client/src/pages/assignment-page/assignment-page.component.ts:18-20](client/src/pages/assignment-page/assignment-page.component.ts#L18-L20), [client/src/pages/assignment-page/assignment-page.component.html:27-50](client/src/pages/assignment-page/assignment-page.component.html#L27-L50) |
| **Medium** | `login-page` does not call `POST /auth/login` | `onSubmit()` and `continueWithSSO()` both navigate directly to `/dashboard`. The form ships with hardcoded `value="elena.marsh@marist.edu"` and `value="••••••••••"` — if/when these are wired, the literal string `••••••••••` would be POSTed as the password unless the template values are cleared. | [client/src/pages/login-page/login-page.component.ts:15-22](client/src/pages/login-page/login-page.component.ts#L15-L22), [client/src/pages/login-page/login-page.component.html:38-55](client/src/pages/login-page/login-page.component.html#L38-L55) |
| **Medium** | `Submission.assignment_id` is NOT NULL but `/evaluate` allows it to be NULL | `models/submission.py:14` declares `assignment_id` `nullable=False`, but `main.py:112-128` and the spec at `api-spec.md:128` allow `assignment_id` to be omitted on `POST /evaluate` — yielding `parsed_assignment_id = None`. `create_submission` is called with `assignment_id=None`, which would fail the NOT NULL constraint on commit (or, given §2.1, never reach commit). The cached path also does this. The frontend submit form requires it, so the SPA path doesn't trigger this — but the API contract is broken. | [server/app/models/submission.py:14-16](server/app/models/submission.py#L14-L16), [docs/api-spec.md:128](docs/api-spec.md#L128) |
| **Medium** | `submissions.get_submission` returns `"None"` for missing assignment_id | `data["assignment_id"] = str(submission.assignment_id)` (line 90). When `submission.assignment_id is None`, this yields the string `"None"` rather than `null`. The frontend type declares `assignment_id: string \| null` and would show `"None"` literally. | [server/app/routers/submissions.py:90](server/app/routers/submissions.py#L90) |
| **Medium** | `rubric_digest` is on `SubmissionData` but not on `SubmissionStatusData` | A direct `/status/:id` link (no `history.state`) reaches the status page with `data=null`, so any UI element that reads `data?.rubric_digest` shows blank. The API spec lists `rubric_digest` only in the `POST /evaluate` response. | [client/src/utils/api.types.ts:1-9,72-81](client/src/utils/api.types.ts#L1-L9) |
| **Medium** | `github_url` vs. `github_repo_url` field-name mismatch across endpoints | `SubmissionData.github_url` (POST /evaluate response, `api.types.ts:3`) and `SubmissionStatusData.github_repo_url` (GET /submissions/{id} response, `api.types.ts:76`) are the same value with different field names. The DB column is `github_repo_url`. The backend deliberately translates one to the other for the POST response (`main.py:185`). Any code that needs to read this from either response shape must branch. | [client/src/utils/api.types.ts:3,76](client/src/utils/api.types.ts#L3) |
| **Medium** | `CriterionScore.recommendation?` is dead | Backend at `submissions.py:117-122` strips the per-criterion `recommendation` and surfaces a flattened top-level `recommendations[]`. The TypeScript type still declares the per-criterion `recommendation?: RecommendationObject` and `criteria-scores.component` does not render it. Code that newly reads `c.recommendation` will silently see `undefined`. | [server/app/routers/submissions.py:117-122](server/app/routers/submissions.py#L117-L122), [client/src/utils/api.types.ts:48](client/src/utils/api.types.ts#L48) |
| **Medium** | LLM model identifiers do not exist in Google's API | `llm.py:97-98` and `ai_passes.py:60` reference `gemini-3.1-pro-preview` and `gemini-3.1-flash-lite`. No such Gemini model identifier exists at the Google Generative Language API endpoint; the closest current identifiers are `gemini-2.5-pro` and `gemini-2.5-flash`. Once `_is_llm_ready()` activates, the first POST to `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-pro-preview:generateContent` returns 404. The model chain falls through to `gpt-4o` (assuming `OPENAI_API_KEY` is set) — silently bypassing the design's primary model. | [server/app/services/llm.py:96-100](server/app/services/llm.py#L96-L100), [server/app/services/ai_passes.py:60](server/app/services/ai_passes.py#L60) |
| **Medium** | LLM readiness probe is fragile (source-string inspection) | `pipeline.py:107-113` calls `inspect.getsource(llm.complete)` and looks for the literal `"raise NotImplementedError"`. The current `llm.complete` does not contain that string at all (it's a real implementation that raises `EvaluationFailedError` after retries). So `_is_llm_ready()` already returns True, meaning the AI phase fires on every submission — even though the model identifiers are wrong (§ above). Result: every M3 evaluation goes straight to `EVALUATION_FAILED`. The probe should be replaced with an explicit configuration flag. | [server/app/services/pipeline.py:97-113](server/app/services/pipeline.py#L97-L113) |
| **Medium** | Status page polling never stops on `Rejected` | `TERMINAL_STATUSES = {Completed, Failed, Awaiting Review, EVALUATION_FAILED}`. After an instructor rejection, the backend sets `submission.status = "Rejected"` (`submissions.py:187`). A student or third party viewing the status page will poll forever. | [client/src/pages/status-page/status-page.component.ts:13](client/src/pages/status-page/status-page.component.ts#L13) |
| **Medium** | `_redact_recursive` mutates dict keys' values but does not redact keys | `redact_dict` deep-copies and rewrites string *values*. If a key happens to be a sensitive identifier (e.g. an API key used as a JSON property name), it is preserved verbatim. Unlikely to matter in practice but worth noting. | [server/app/services/llm.py:46-65](server/app/services/llm.py#L46-L65) |
| **Low** | Frontend `evaluation.service.ts` always sends `Authorization: Bearer ` (empty) when `devToken` is falsy | The header is constructed as `` `Bearer ${environment.devToken ?? ''}` ``. In production, `environment.devToken` is intentionally absent (`environment.prod.ts`) — JS evaluates `undefined ?? ''` → `''`, producing `Authorization: Bearer `. Backend rejects with 401, but the request reaches the server first. Sending an obviously-malformed header makes WAF / log triage noisier. | [client/src/services/evaluation.service.ts:30,55,82](client/src/services/evaluation.service.ts#L30) |
| **Low** | `Submission.status` is a free-form `String` | No DB-level CHECK or enum constraint. Any string can be persisted (e.g. typo `"Cmpleted"`). Frontend `TERMINAL_STATUSES` and `displayStatus` would silently treat the typo as "in progress" forever. | [server/app/models/submission.py:22](server/app/models/submission.py#L22) |
| **Low** | `EvaluationResult.review_status` accepts arbitrary strings | Same shape as Submission.status — migration declares it `sa.String(), nullable=False, server_default='pending'` with no enum. | [alembic/versions/20260419001_add_review_columns_to_evaluation_results.py:23](alembic/versions/20260419001_add_review_columns_to_evaluation_results.py#L23) |
| **Low** | Rate-limit `X-Forwarded-For` trust | `_client_ip` returns the leftmost forwarded IP without validating the upstream proxy. If Nginx sets the header (good), this is correct. If a non-Nginx deployment ever forwards the request, attackers can spoof the IP via header injection and bypass rate limits. The deployment runbook (M4.A.5) sets up Nginx; just keep it that way and document the assumption inside `rate_limit.py`. | [server/app/middleware/rate_limit.py:25-29](server/app/middleware/rate_limit.py#L25-L29) |
| **Low** | `_load_cache_index` does not validate `local_repo_path` traversal | `cached_repo_path = project_root / entry.local_repo_path` (`cache.py:102`). If the cache index file were ever compromised (e.g. via a separate write path), `local_repo_path = "../../../etc"` would escape `PROJECT_ROOT`. Today the index is only written by trusted code. Defensive `Path.resolve()` + `is_relative_to()` check is a one-line addition. | [server/app/cache.py:102-110](server/app/cache.py#L102-L110) |
| **Low** | Env-value redaction misses lowercase keys | `_ENV_VALUE_PATTERN = r"([A-Z][A-Z_]{2,}=)(\S+)"` only catches uppercase-prefixed assignments. A log line like `db_password=hunter2` is *not* redacted. | [server/app/services/llm.py:34](server/app/services/llm.py#L34) |
| **Low** | `Assignment.enable_lint_review` migration nullability mismatch | Migration: `Boolean(), nullable=True`. ORM: `default=False` (no `nullable=False`). The DB allows NULL but Python defaults to False, so existing rows from the migration could be NULL while new rows are False. Inconsistent. | [server/app/models/assignment.py:21](server/app/models/assignment.py#L21), [alembic/versions/010126822022_create_initial_schema.py:51](alembic/versions/010126822022_create_initial_schema.py#L51) |
| **Low** | Login form uses literal `••••••••••` as password value | The Angular template hardcodes `value="••••••••••"` on the password input. When the form is wired to `POST /auth/login`, the literal bullets will be sent unless cleared first. | [client/src/pages/login-page/login-page.component.html:47](client/src/pages/login-page/login-page.component.html#L47) |
| **Low** | `audit/written-reflection.md` deletion not yet committed | Tracked file shown deleted in `git status`; replacement appears at `docs/written-reflection.md` (untracked). Trivial but should be reconciled before the next push. | working tree |
| **Informational** | `pgvector(1536)` migration drops & re-adds the column | `c3d4e5f6a7b8` does `DROP COLUMN IF EXISTS embedding` then re-creates as `vector(1536)`. The note acknowledges the table is empty at migration time. If the table gains rows before this migration runs in any environment, those rows lose their embeddings. The combined head problem (§2.3) makes ordering ambiguous. | [alembic/versions/c3d4e5f6a7b8_resize_embedding_vector_add_hnsw.py:21-23](alembic/versions/c3d4e5f6a7b8_resize_embedding_vector_add_hnsw.py#L21-L23) |
| **Informational** | `_MAX_CHUNKS_PER_REPO=200` is a magic number | Carried inside `pipeline.py:82`; not configurable through `settings`. Large repos may be silently truncated below the rubric's evidence threshold. | [server/app/services/pipeline.py:82](server/app/services/pipeline.py#L82) |
| **Informational** | `pipeline.py` blends generic exceptions with schema failures | The `except Exception` at `pipeline.py:215` lands on `Failed`, while `EvaluationFailedError` lands on `EVALUATION_FAILED`. With §2.6 active, *every* M3 failure is a `TypeError` (generic exception), so submissions land on `Failed` instead of `EVALUATION_FAILED`. Operationally the two terminal statuses are distinct; this collapses them. | [server/app/services/pipeline.py:215](server/app/services/pipeline.py#L215) |
| **Informational** | Hardcoded UUIDs / fake data inside Angular components | Dashboard `copyId()` writes a literal UUID; assignment success banner shows a literal UUID; submit-page placeholder is a literal UUID. None affect runtime, but copy-paste from production demos may surface. | [client/src/pages/dashboard-page/dashboard-page.component.ts:188](client/src/pages/dashboard-page/dashboard-page.component.ts#L188), [client/src/pages/assignment-page/assignment-page.component.html:27](client/src/pages/assignment-page/assignment-page.component.html#L27) |

---

## 3. Ambiguity Resolution & Action Plan

### 3.1 EXTREME — restore main.py to a working state

**Root cause:** The committed `main.py` reflects an in-progress refactor where all symbol-defining code was deleted but the call sites were left in. There is no module elsewhere in the tree that defines `MapleAPIError`, `_url_adapter`, `parse_github_repo_url`, `validate_github_repo_access`, etc. — these are *new* symbols that the next commit was supposed to define.

**Remediation strategy:**

1. **Recover** the prior working `main.py` from git history (the Milestone 2/3 audits passed against it; check `git log --oneline -- server/app/main.py` and pick the last green commit). The modern API contract differs only by the `/review` endpoint, so the older file is the truth-of-record for the `/evaluate` shape.
2. **Re-introduce** the M4.A.5 rate-limit decorator (`@limiter.limit("5/minute")`) on `/evaluate`.
3. **Move** `MapleAPIError`, `GitHubRepoMetadata`, `_url_adapter`, and the GitHub-PAT helpers into a dedicated module (e.g. `server/app/utils/api_errors.py` and `server/app/services/github_client.py`) so this never recurs.
4. **Add** an import-smoke test (`tests/test_main_imports.py`):
   ```python
   def test_main_module_imports():
       from server.app import main  # must not raise
       assert main.app is not None
   ```
5. **Wire** that test into CI as a fail-fast gate — every PR must pass module import before any other test runs.

**Definition of Done:**
- `python -c "from server.app import main"` succeeds in the project venv.
- `pytest server/tests/test_main_imports.py` passes.
- `pytest server/tests/test_main_url_validation.py` and `pytest server/tests/test_evaluate_submission_integration.py` pass (or are demonstrably re-pinned to the new module structure).
- `uvicorn server.app.main:app --reload` opens `http://localhost:8000/api/v1/code-eval/health` returning `{"status":"ok"}`.

---

### 3.2 EXTREME — fix the rate-limit middleware import path

**Remediation:** Change line 22 in [server/app/middleware/rate_limit.py](server/app/middleware/rate_limit.py) from:
```python
from app.utils.responses import error_response
```
to:
```python
from ..utils.responses import error_response
```
(or the absolute equivalent `from server.app.utils.responses import error_response` to match the convention the rest of the file uses). Then add an import-smoke test for the rate-limit module identical to §3.1.

**Definition of Done:** `python -c "from server.app.middleware.rate_limit import install_rate_limiting"` succeeds without `ModuleNotFoundError`.

---

### 3.3 EXTREME — merge the two Alembic heads

**Remediation:**
```bash
alembic merge -m "merge_review_columns_with_pgvector_chain" 20260419001 c3d4e5f6a7b8
```
This generates an empty merge revision whose `down_revision = ('20260419001', 'c3d4e5f6a7b8')`. After commit, `alembic heads` returns one head. The migration is empty — no schema change — but it linearises the graph so `alembic upgrade head` works.

**Definition of Done:**
- `alembic heads` returns exactly one revision id.
- `alembic upgrade head` against a fresh database completes without "Multiple head revisions" error.
- The new merge revision is committed to `alembic/versions/`.

---

### 3.4 HIGH — declare `review_status` and `instructor_notes` on `EvaluationResult` ORM

**Remediation:** Add the missing columns to [server/app/models/evaluation_result.py](server/app/models/evaluation_result.py):

```python
review_status: Mapped[str] = mapped_column(
    String, nullable=False, server_default="pending", default="pending"
)
instructor_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
```

(Add `Text` to the imports; don't change `JSON`.) Optional but recommended: switch `String` to `sa.Enum("pending", "approved", "rejected", name="review_status_enum")` for parity with the migration's intent and to fix §2 Low ("review_status accepts arbitrary strings"). If you switch, generate a follow-up migration to install the Postgres enum type and convert the column.

**Definition of Done:**
- `pytest server/tests/test_submissions_router.py` exercises an approve flow end-to-end and asserts `er.review_status == "approved"` after commit.
- The status page review panel renders against a real backend submission whose evaluation has `review_status = "pending"`.

---

### 3.5 HIGH — reconcile `ai_passes ↔ llm.complete` interface

**Two options. Choose one and apply consistently:**

**Option A (preferred): make `llm.complete` accept an optional `model` kwarg** that overrides the chain. This lets `ai_passes` express "use Pass-1 model" without bypassing the redact / retry / log machinery.

```python
async def complete(
    system_prompt: str,
    messages: list[dict],
    *,
    model: str | None = None,        # NEW
    complexity: Literal["standard", "complex"] = "standard",
    max_tokens: int = 1024,
    temperature: float = 0.7,
    timeout: int | None = None,      # NEW (currently consumed by complexity)
) -> LLMResponse:
    chain = (
        [next(s for s in MODEL_CHAIN if s.name == model)]
        if model
        else MODEL_CHAIN
    )
    ...
```

**Option B:** drop the `model=` kwarg from `_invoke_complete` and rely on `complexity` to pick a chain (`complex` for Pass 1/3, `standard` for Pass 2). Update `MODEL_CHAIN` to be selected by complexity tier. Simpler but less surgical.

**Definition of Done:**
- Calling `await llm.complete(system_prompt="x", messages=[{"role":"user","content":"x"}], model="gemini-3.1-pro-preview")` does not raise `TypeError`.
- An integration test that monkeypatches `llm._dispatch` to a no-op and runs `run_pass1` returns a valid Pass-1 schema instance.

**Pair with the model-name fix:** simultaneously update the chain to use real model identifiers (`gemini-2.5-pro`, `gemini-2.5-flash`, `gpt-4o-mini` or `gpt-4o`) and bump the design doc.

---

### 3.6 HIGH — replace source-inspection LLM probe with an explicit flag

**Remediation:** in `llm.py`, add a module-level constant and let `pipeline.py` consult it:

```python
# llm.py
LLM_READY: bool = bool(settings.GEMINI_API_KEY or settings.OPENAI_API_KEY)
```
```python
# pipeline.py
def _is_llm_ready() -> bool:
    return getattr(llm, "LLM_READY", False)
```

This (a) eliminates the false-positive that already activates the AI phase against unreachable Gemini 3.1 names, (b) couples readiness to actual configuration, (c) survives any future renaming of the stub message string.

**Definition of Done:** `inspect` is no longer imported by `pipeline.py`. A test sets `llm.LLM_READY=False`, calls `run_pipeline`, and asserts the submission terminates at `Completed` (deterministic only) without invoking any LLM hook.

---

### 3.7 HIGH — gate `auth.register` role to a whitelist

**Remediation:**

```python
ALLOWED_REGISTRATION_ROLES: set[str] = {"Student"}  # tighten as needed

class RegisterRequest(BaseModel):
    email: EmailStr
    password: SecretStr
    role: Literal["Student"] = "Student"   # remove free-form widening
```

Then move Instructor / Admin provisioning to a manual `seed_admin.py` script invoked once per environment, or behind a `require_role("Admin")` self-bootstrap endpoint.

**Definition of Done:**
- `POST /auth/register` with `{"role": "Instructor"}` returns 422.
- An integration test asserts the privilege escalation path is closed.
- M4.A.2 deployment runbook has a callout: "instructor accounts are created via `python -m server.scripts.seed_admin`, never via the public register endpoint."

---

### 3.8 HIGH — add front-end auth guard

**Remediation:** Add an `AuthGuard` `CanActivateFn` that redirects to `/login` when no token is in `localStorage`. Apply it to every authenticated route in `app.routes.ts`. Leave `/login` open. Pair with B1 in `docs/post-ui-integration-gaps.md` (the `POST /auth/login` wiring story).

```typescript
// auth.guard.ts
export const authGuard: CanActivateFn = (route, state) => {
  const router = inject(Router);
  if (!localStorage.getItem('access_token')) {
    router.navigate(['/login']);
    return false;
  }
  return true;
};
```

**Definition of Done:** unauthenticated user navigating to `/dashboard` is redirected to `/login` before the shell renders.

---

### 3.9 Medium / Low remediations (batch)

| ID | Action | Definition of Done |
|---|---|---|
| 2-medium-A | Remove `studentId` `Validators.required`; relabel as "Student name (optional, for display)" | Submitting with empty `studentId` succeeds; UI breadcrumb falls back to `submissionId.slice(0,8)` |
| 2-medium-B | Wire `assignment-page` to `POST /assignments`; add `rubric_id` field, drop `dueDate` | Banner displays the real returned UUID; spec / form match exactly |
| 2-medium-C | Wire `login-page` to `POST /auth/login`; clear hardcoded `value=` attributes | Successful login stores JWT; failed login shows error banner |
| 2-medium-D | Make `/evaluate` enforce `assignment_id` required (matching `Submission.assignment_id NOT NULL`) **or** make the column nullable | Pydantic / SQLAlchemy / OpenAPI all agree |
| 2-medium-E | Use `submission.assignment_id` test before stringifying: `str(submission.assignment_id) if submission.assignment_id else None` | `GET /submissions/{id}` returns JSON `null`, not `"None"` |
| 2-medium-F | Add `rubric_digest` to `GET /submissions/{id}` response, or remove from the status-page KV grid | Direct-link `/status/:id` shows correct digest |
| 2-medium-G | Normalize `github_url` ↔ `github_repo_url`. Recommend: backend always returns `github_url`; ORM column stays `github_repo_url`; field is renamed in the response only | One name across both endpoint shapes |
| 2-medium-H | Stop stripping per-criterion `recommendation` in router; derive top-level `recommendations[]` on the frontend instead | Backend is single source; frontend reduces |
| 2-medium-I | Add `'Rejected'` to `TERMINAL_STATUSES` on the status page | Polling halts after rejection |
| 2-medium-J | Replace fixture dashboard with either (a) a banner stating the data is sample, or (b) a real `GET /submissions` endpoint behind `require_role("Instructor")` | Instructor never confused about source |
| 2-low-A | Add `Path.resolve()`-based traversal guard in `_load_cache_index` | Crafted index entry cannot escape PROJECT_ROOT |
| 2-low-B | Convert `_ENV_VALUE_PATTERN` to case-insensitive | `db_password=…` is also redacted |
| 2-low-C | Promote `_MAX_CHUNKS_PER_REPO` to `settings.AST_MAX_CHUNKS` | Configurable per environment |
| 2-low-D | Make `Submission.status` and `EvaluationResult.review_status` Postgres enums | Typo statuses become DB-rejected |
| 2-low-E | Reconcile `audit/written-reflection.md` deletion (rename to `docs/written-reflection.md`) in a small commit | Working tree clean |

---

## 4. Security & Vulnerability Assessment

### 4.1 Authentication & authorization

- ✅ JWT signing uses `HS256` with `settings.SECRET_KEY` (`utils/security.py:22`). Production deployment runbook (M4.A.2) requires a strong key. **Verify** the runbook explicitly forbids the placeholder `changeme`. (`.env.example:13` ships `SECRET_KEY=changeme`.) Add a startup-time check:
  ```python
  if settings.APP_ENV == "production" and settings.SECRET_KEY in {"changeme", ""}:
      raise ValueError("SECRET_KEY must not be the default in production.")
  ```
- ✅ `require_role("Instructor")` correctly gates `POST /submissions/{id}/review` (`submissions.py:144`), and the cross-assignment ownership check (`submissions.py:170`) prevents Instructor-A from approving Instructor-B's submission.
- ❌ **`POST /auth/register` is unauthenticated and accepts an arbitrary `role` string** (§2 High). This is the single most exploitable hole in the system: anyone with network access to `/api/v1/code-eval/auth/register` can self-provision an Instructor account, then create assignments and approve their own submissions.
- ❌ **No frontend auth guard** (§2 High). Defense-in-depth issue: the SPA hands sensitive routes to anonymous users, even if the backend rejects the underlying API calls.
- ⚠️ **Dev token in dev environment files** is empty by convention. Verify `environment.development.ts` is gitignored (it is, per `.gitignore`) and that no real JWT is ever committed.

### 4.2 Code injection & sandboxing

- ✅ Docker container runs with `network_disabled=True`, `cap_drop=["ALL"]`, `security_opt=["no-new-privileges:true"]`, `read_only=True`, 256MB RAM, 50% CPU, 30s timeout. (`docker_client.py:88-107`). Strong defense.
- ✅ `_build_shell_command` uses `sh -c " && ".join(parts)` — but `parts` are not user-controlled (they come from frozen `SandboxProfile` constants). No injection surface.
- ✅ `redact()` strips PATs, emails, and uppercase-prefixed env values before any LLM call.
- ⚠️ `bash` is not invoked inside main.py's `clone_repository` (function not visible due to §2.1). Once main.py is restored, audit the clone command for PAT-in-URL leakage. The standard pattern `https://x-access-token:${PAT}@github.com/owner/repo.git` is safe iff the PAT is never logged. Confirm `subprocess.run(...)` calls do not echo the URL.

### 4.3 Input validation

- ✅ Rubric upload is decoded as UTF-8 with a 400 on `UnicodeDecodeError` (main.py:80-88, blocked by §2.1 but visibly correct).
- ✅ JSON parse failure of rubric falls back to text (acceptable; cache still keys on canonicalized form).
- ✅ `assignment_id` is parsed as a UUID with explicit 400 on bad format.
- ⚠️ **No size limit on the rubric upload.** A 1GB file would be loaded into memory by `await rubric.read()`. Add a Content-Length / `MAX_RUBRIC_BYTES = 256 * 1024` guard.
- ⚠️ **No size limit on cloned repo.** A 5GB student repo would fill the Droplet disk. Consider clamping clone depth (`--depth 1` already saves history) and total bytes via `du`.
- ⚠️ **GitHub URL regex on the frontend** allows trailing slash but otherwise restricts to `github.com/<owner>/<repo>`. Backend uses a Pydantic URL validator + `parse_github_repo_url` (function unavailable per §2.1). Once main.py is restored, ensure the backend regex matches the frontend's strictness.

### 4.4 Secrets management

- ✅ `.env` is gitignored (`./gitignore:13`); `.env.example` ships only placeholder values.
- ✅ `redact()` strips PAT-style strings from any string flowing into the LLM.
- ❌ `.env.example` ships `GITHUB_PAT=ghp_xxxxxxxxxxxx` (a literal `ghp_` prefix). Some scanners/grep-based checks flag the prefix even though the suffix is fake. Consider `GITHUB_PAT=<your-pat>` to avoid noise.
- ⚠️ Frontend `environment.prod.ts` is checked in. It does not contain secrets, but the comment "production API key" pattern (currently absent) is one keystroke from a compromise. Keep the file devToken-free, as it is today.

### 4.5 Logic vulnerabilities

- **Privilege escalation via `/auth/register`** (§4.1) — the most material issue.
- **State-machine bypass via `Submission.status` having no enum** (§2 Low) — an attacker who gained DB write would not need to set `status='Awaiting Review'`; they could spoof `'Approved'` (a status the system never produces but the frontend would display). With current ACLs only the backend writes status, but defence in depth wants a CHECK constraint.
- **Cache-key collision risk** is well-defended (`build_repository_cache_key` uses SHA-256 over `commit_hash + rubric_digest`; collisions are negligible at any expected scale).
- **Polling never stops on `Rejected`** (§2 Medium) — not a vulnerability but a UX trap.

### 4.6 Dependencies

- `slowapi==0.1.9`, `fastapi>=0.135`, `pydantic-settings>=2.13`, `passlib[bcrypt]>=1.7.4`, `pyjwt>=2.12`, `pgvector>=0.3`, `openai>=1.0`, `jsonschema>=4.21`. All recent. No known CVEs as of the audit date.
- Angular `@angular/core@21.1.0` is current. `vitest@4.0.8` is current. No `npm audit` review performed but the lockfile is committed; run `npm audit --omit=dev` against it before pilot.

---

## 5. Efficiency & Optimization Recommendations

### 5.1 Low-risk, high-reward

1. **Eager-load relationships on `GET /submissions/{id}`** — already done at `submissions.py:60-61` (`selectinload(assignment) + selectinload(evaluation_result)`). ✅ No action.
2. **Promote AST chunk cap to a setting** (§2 Informational) — one-line change; config-aware tuning per environment.
3. **Cache `decode_access_token`** for short-lived requests using `functools.lru_cache` keyed by token string (with TTL = token expiry). For high-traffic deployments, this halves JWT verification cost. Risk: must invalidate on logout. Skip until pilot shows JWT verification as a hot path.
4. **Run pylint/eslint in parallel for multi-language repos.** `linter_runner.run_linter` invokes per language. If a future repo is mixed Python+JS, two separate Docker containers run sequentially. Switch to `asyncio.gather([…])` for multi-language detection. Risk: 2× peak Docker memory; bound concurrency to 2.
5. **Stream the rubric file** instead of `await rubric.read()`. For typical 1KB rubrics this is irrelevant; for the 256KB cap recommended in §4.3 it still doesn't matter. Skip.
6. **Pre-warm the AST chunker cache for repeated commits.** Today every cache hit re-runs `extract_chunks` against the cached repo. Memoize the chunks alongside the cache entry (`local_repo_path/.maple_chunks.json`) — saves ~200ms × file-count per re-evaluation. Risk: cached chunks may go stale if `extract_chunks` itself changes; key by chunker version.

### 5.2 Recommendations that touch hot paths (verify before applying)

7. **Replace `inspect.signature(llm_complete)` per pass call** (`ai_passes.py:169`). Done once per pipeline run, but still invokes Python's `inspect` machinery 3+ times. Cache the answer at module load time. Risk: low; tests mock `llm_complete` per test, so the cache must be invalidated per call. Consider applying after §3.5.
8. **Memoize redact pattern compilation.** The patterns at `llm.py:29-34` are compiled once at module load. ✅ No action.
9. **Drop `inspect.getsource` from `_is_llm_ready`** — addressed by §3.6.
10. **Batch embedding for style-guide ingestion.** `embeddings.embed_batch` already exists and is used by the ingester. ✅ No action.

### 5.3 Risks explicitly flagged

- Switching `Submission.status` to a Postgres ENUM (recommended) is a destructive migration on an existing column — write the migration carefully (`USING status::text::status_enum` with a safety check that no current value is outside the enum domain). **Risk: production rows with stale typo'd statuses would block the migration.** Audit `SELECT DISTINCT status FROM submissions;` before applying.
- Removing `studentId` `Validators.required` (§3.9 2-medium-A) is safe — purely UI relaxation.
- Adding the `model` kwarg to `llm.complete` is safe — additive.

---

## 6. Conclusion

**The MAPLE A1 codebase is conceptually 90% complete and operationally 0% complete.** The architecture is sound, the design discipline is visible (pure-function modules, JSON-schema validation, redaction pre-LLM, sandboxed Docker, RAG with `style_guide_version` provenance, structured logs), and the UI mockup is impressive in scope. But three EXTREME-severity bugs (broken `main.py`, broken `rate_limit.py` import, dual Alembic heads) and two HIGH-severity bugs (missing ORM columns, `ai_passes ↔ llm.complete` mismatch) mean the system at HEAD does not start, does not migrate, and does not evaluate.

**Critical-path fix sequence (estimated ≤ 4 engineer-hours):**

1. Recover/repair `main.py` (§3.1).
2. Fix `rate_limit.py` import path (§3.2).
3. Add Alembic merge revision (§3.3).
4. Add `review_status` and `instructor_notes` to the `EvaluationResult` ORM (§3.4).
5. Reconcile `ai_passes` ↔ `llm.complete` and switch model identifiers (§3.5).
6. Replace LLM-readiness probe (§3.6).
7. Lock down `auth.register` role (§3.7).
8. Add frontend auth guard (§3.8).

Once those land, the MEDIUM/LOW gaps (front-end wiring of login + assignment forms, dashboard fixture replacement, polling-on-Rejected, naming consistency) are well-understood per `docs/post-ui-integration-gaps.md` and can be parallelised. The system will be pilot-ready (M4.A.8 smoke test) within a week of the critical-path fixes, **assuming** the model-identifier correction lands before any LLM key is provisioned in production — a single misconfigured `gemini-3.1-pro-preview` request burns no tokens (it 404s), but the silent fallthrough to GPT-4o would generate cost without anyone noticing the primary model was never reached.

This audit supersedes `audit/milestone-03-audit-2026-04-19.md` (which was correct on 2026-04-19 against a buildable HEAD) and incorporates `audit/ui-spec-audit.md` (which captured UI↔spec drift). Together they form the complete picture; this document is the single source of truth as of 2026-04-30.
