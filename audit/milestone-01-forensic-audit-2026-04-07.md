# Milestone 1 — Forensic Technical Audit

**Auditor role:** Senior technical auditor and QA engineer  
**Scope:** Verification of the workspace against [`docs/milestones/milestone-01-tasks.md`](../docs/milestones/milestone-01-tasks.md) and cross-check with implementation, tests, and security posture.  
**Method:** Claims below are tied to specific files and line ranges as they existed at audit time (2026-04-07).  
**Note:** An `audits/` directory already contains earlier milestone-01 audits; this report is the canonical output for the `/audit` command in `audit/`.

**Ownership (from [`docs/milestones/milestone-01-tasks.md`](../docs/milestones/milestone-01-tasks.md)):** **Jayden** — Infrastructure & Deployment; **Dom** — Backend API, Database & Security; **Sylvie** — Repository Ingestion Pipeline & Frontend. Where an issue spans layers, multiple names are listed (integration order matches the milestone “Integration Point”).

---

## 1. Feature synthesis and modular architecture

### 1.1 Milestone checklist vs repository state

| Area | Milestone expectation | Observed implementation |
|------|---------------------|-------------------------|
| Repo layout | `docs/`, `server/app/`, `client/src/`, `data/`, `eval/`, `prompts/` | Present. `eval/README.md` documents MAPLE layout; `prompts/` populated with dev prompts. |
| Backend schema | `User`, `Assignment`, `Rubric`, `Submission`, `EvaluationResult` via Alembic | [`alembic/versions/010126822022_create_initial_schema.py`](../alembic/versions/010126822022_create_initial_schema.py) creates all five tables with FKs. |
| Rubrics API | `POST /api/v1/code-eval/rubrics` with A5-compatible JSON validation | [`server/app/routers/rubrics.py`](../server/app/routers/rubrics.py) implements `POST` with Pydantic models (`RubricCreateRequest`, criteria, levels, `total_points` consistency). **No JWT** on this route (see §4). |
| Regex redactor | Strip PATs, env vars, emails before external calls | [`server/app/services/llm.py`](../server/app/services/llm.py): `redact()` applies GitHub PAT pattern, email pattern, and `KEY=value` env-style redaction. Used on clone stderr in [`server/app/main.py`](../server/app/main.py) (e.g. around the `redact` call after failed clone). `redact_dict` exists but is not yet on the LLM path (`complete()` is `NotImplementedError` — correct for M1). |
| GitHub PAT cloning | Clone into `data/raw/` via API + git | [`server/app/main.py`](../server/app/main.py): `validate_github_repo_access`, `resolve_repository_head_commit_hash`, `clone_repository` with `GIT_ASKPASS` + `MAPLE_GITHUB_PAT`. Paths under `RAW_REPOS_ROOT` → `data/raw`. |
| Pre-processor | Strip `node_modules`, `venv`, compiled binaries, `.git` | [`server/app/preprocessing.py`](../server/app/preprocessing.py): `STRIP_DIRECTORY_NAMES` includes `.git`, `node_modules`, `venv`, `.venv`, `__pycache__`; `COMPILED_BINARY_SUFFIXES` removes common binary extensions. |
| Cache | SHA + normalized rubric digest; skip re-clone on hit | [`server/app/cache.py`](../server/app/cache.py): `fingerprint_rubric_content`, `build_repository_cache_key`, file-backed index with `fcntl` exclusive lock. [`main.py`](../server/app/main.py) `evaluate_submission` checks cache before cloning. |
| End-to-end deliverable | Student submits URL → clone/preprocess → `submission_id` | **Implemented:** `POST /api/v1/code-eval/evaluate` persists a `Submission` via `create_submission` and returns `submission_id` as the database UUID string (see ```532:553:server/app/main.py``` and ```598:618:server/app/main.py```). |
| Angular | Form (URL + assignment ID) + status polling | **Partial:** [`client/src/pages/submit-page/`](../client/src/pages/submit-page/) implements form + rubric file + navigation to status. [`client/src/pages/status-page/`](../client/src/pages/status-page/) displays data from **router state only**; explicit TODO for `GET /submissions/:id` and polling. **Milestone markdown still shows this task unchecked** ([`milestone-01-tasks.md` line 41](../docs/milestones/milestone-01-tasks.md)) — documentation drift. |
| Auth scaffold | (Milestone: Dom backend) | [`server/app/routers/auth.py`](../server/app/routers/auth.py) register/login; [`middleware/auth.py`](../server/app/middleware/auth.py) JWT bearer; `evaluate` and assignment routes use `get_current_user`. |

### 1.2 Dependency map (high level)

```mermaid
flowchart TB
  subgraph client [Angular client]
    Submit[SubmitPageComponent]
    Status[StatusPageComponent]
    EvalSvc[EvaluationService]
  end
  subgraph api [FastAPI main.py + routers]
    Eval[POST /evaluate]
    Sub[GET /submissions/id]
    Rub[POST /rubrics]
    Asg[POST|GET /assignments]
    AuthR[POST /auth/*]
  end
  subgraph services [Services]
    SubSvc[submissions.create_submission]
    AsgSvc[assignments.*]
    LLM[llm.redact]
  end
  subgraph data [Persistence and disk]
    PG[(PostgreSQL)]
    Cache[repository-cache-index.json]
    Raw[data/raw clones]
  end
  EvalSvc --> Eval
  Submit --> EvalSvc
  Status -.->|TODO: poll| Sub
  Eval --> LLM
  Eval --> SubSvc
  Eval --> Cache
  Eval --> Raw
  SubSvc --> PG
  Sub --> PG
  Rub --> PG
  Asg --> AsgSvc --> PG
  AuthR --> PG
```

**Assessment:** The ingestion pipeline is centralized in `main.py` (`evaluate_submission`), while rubrics, assignments, submissions, and auth are modular routers. This is workable for M1 but concentrates orchestration logic in a single large module (~625 lines), which will complicate Milestone 2+ testing and feature flags unless split into a dedicated service layer.

### 1.3 What is implemented well

- **Cache correctness:** Locking around the JSON index reduces corruption risk under concurrent writers; missing on-disk repo invalidates stale index entries (see ```95:111:server/app/cache.py```).
- **GitHub error taxonomy:** Distinct handling for 401 PAT, 403 rate limit vs access, 404, and generic 502 paths in `validate_github_repo_access` and `resolve_repository_head_commit_hash`.
- **Submission authorization:** [`server/app/routers/submissions.py`](../server/app/routers/submissions.py) `_can_view_submission` enforces owner, `admin`, or assignment instructor match (with `selectinload` for assignment).
- **Assignment ID validation:** `parse_assignment_id` / `validate_assignment_exists` prevent orphan FK attempts before clone work (see ```478:494:server/app/main.py```).

---

## 2. Gap analysis — ambiguities, predictive errors, interface mismatches

| Severity | Owner(s) | Error cause | Explanation | Origin location(s) |
|----------|----------|-------------|-------------|-------------------|
| **High** | **Sylvie** (evaluate + Angular env); **Dom** (JWT / auth contract) | Client JWT `sub` must be a UUID | `evaluate_submission` parses `current_user["sub"]` with `uuid.UUID(...)`. Any token whose `sub` is not a UUID returns **401** (`AUTHENTICATION_ERROR`). The Angular env examples tell developers to use `{'sub': 'dev', 'role': 'user'}` — **`dev` is not a valid UUID**, so local SPA submission will fail after login/token generation per those instructions. Role `user` also does not match seeded role strings used elsewhere (`Student`, `Instructor`, `Admin` in tests). | ```496:503:server/app/main.py```; ```1:8:client/src/environments/environment.ts```; ```1:8:client/src/environments/environment.development.ts.example``` |
| **High** | **Sylvie** (ingestion / `evaluate` contract); **Dom** (backend tests & persistence) | Integration tests out of sync with API contract | `test_evaluate_submission_integration.py` overrides `get_current_user` with `{"sub": "test-user", ...}` (invalid UUID for evaluate path), uses `assignment_id="asgn_abc123"` (not a UUID — fails `parse_assignment_id`), and asserts `submission_id.startswith("sub_")` while production returns **database UUID strings** from `create_submission`. If dependencies were installed, these tests would not pass without extensive rewriting. **This is predictive technical debt:** CI cannot gate quality on this file as written. | ```26:27:server/tests/test_evaluate_submission_integration.py```; ```664:664:server/tests/test_evaluate_submission_integration.py```; ```9:35:server/app/services/submissions.py``` |
| **High** | **Dom** | Unauthenticated rubric creation | `POST /rubrics` has **no** `Depends(get_current_user)` or role check. Anyone who can reach the API can insert rubric rows (DoS via spam, data poisoning). Milestone text calls out “security”; this endpoint is a gap. | ```48:49:server/app/routers/rubrics.py``` |
| **High** | **Dom** | Open registration role escalation | `RegisterRequest` accepts **any** `role` string defaulting to `Student` but not restricted to allowed values. A caller can register as `admin` or `Instructor` without proof, then obtain a JWT with that role (see `create_access_token` in login). | ```15:33:server/app/routers/auth.py``` |
| **Medium** | **Sylvie** (Angular status UX + polling); **Dom** (`GET /submissions` — already implemented) | “Status polling page” incomplete | Milestone asks for status polling. Status page shows a **stale** user message claiming `GET /submissions/:id` is “pending,” but the router **is implemented**. No HTTP polling, no refresh on deep link — direct navigation to `/status/:uuid` shows empty state unless `history.state` was populated by in-app navigation. | ```18:27:client/src/pages/status-page/status-page.component.ts```; ```34:41:client/src/pages/status-page/status-page.component.html```; ```36:89:server/app/routers/submissions.py``` |
| **Medium** | **Sylvie** (Angular auth wiring); **Jayden** (production secrets / deployment alignment) | Production Angular auth | `environment.prod.ts` sets `devToken: ''`. Production builds will send `Authorization: Bearer ` (empty) unless replaced by a proper auth flow or build-time secret — evaluate will 401. Expected for M1 scaffold but blocks real deployment without additional work. | ```1:6:client/src/environments/environment.prod.ts```; ```28:30:client/src/services/evaluation.service.ts``` |
| **Medium** | **Dom** | A5 schema wording vs implementation | Milestone requires “A5-compatible JSON schema validation.” Implementation validates a **custom** criterion/level shape (`max_points`, `levels[].points`). Design doc references A5 fields (`rubric_id`, `criteria`, `levels`) at a high level. Without a shared JSON Schema artifact or contract tests against the real A5 module, **drift** is likely when A5 ships. | [`server/app/routers/rubrics.py`](../server/app/routers/rubrics.py); [`docs/design-doc.md`](../docs/design-doc.md) §2 API |
| **Medium** | **Dom** (schema + docs accuracy) | Design doc vs DB rubric model | Design text suggests `Rubric` may include `assignment_id`; Alembic `rubrics` has no `assignment_id` — link is `assignments.rubric_id` → `rubrics.id`. Documentation inconsistency only, but misleads new contributors. | [`docs/design-doc.md`](../docs/design-doc.md) §2 Data Model; [`alembic/versions/010126822022_create_initial_schema.py`](../alembic/versions/010126822022_create_initial_schema.py) |
| **Low** | **Dom** | Import style inconsistency | `rubrics.py` uses `from server.app.models import ...` while sibling routers use relative `..models`. Works if `PYTHONPATH` includes project root; fragile for alternate run configurations. | ```9:10:server/app/routers/rubrics.py``` vs [`assignments.py`](../server/app/routers/assignments.py) imports |
| **Low** | **Dom** | `success_response` return type | `success_response` in [`responses.py`](../server/app/utils/responses.py) returns a plain `dict`, while `error_response` returns `JSONResponse`. FastAPI coerces dict responses, but OpenAPI typing and consistency suffer. | ```13:19:server/app/utils/responses.py``` |
| **Informational** | **Sylvie** | Milestone markdown checkbox | Sylvie’s Angular line remains `[ ]` though submit flow exists; should be flipped or scoped to “polling not done” to avoid false audit signals. | [`docs/milestones/milestone-01-tasks.md` line 41](../docs/milestones/milestone-01-tasks.md) |
| **Informational** | **Jayden** | `.env.example` placeholder PAT | Documents `ghp_...` pattern; realistic for examples but triggers secret scanners in some orgs — consider `ghp_REPLACE_ME` style. | [`.env.example`](../.env.example) line 20 |

---

## 3. Remediation — High and Extreme items

*Owners below follow the same milestone split: **Dom** = Backend API, Database & Security; **Sylvie** = Ingestion & Frontend; **Jayden** = Infrastructure & Deployment.*

### 3.1 JWT `sub` and developer onboarding (High)

**Primary:** **Sylvie** (Angular env + docs); **Dom** (optional backend dev ergonomics, token contract).

1. **Single rule:** Document that `sub` **must** equal the user’s UUID string in `users.id` (as produced by `/auth/register` + `/auth/login`).
2. Update `environment.ts` and `environment.development.ts.example` comments to show:  
   `create_access_token({"sub": str(user.id), "role": user.role})` after registering a test user — not literal `'dev'`.
3. Optionally add a **dev-only** dependency override or `/auth/dev-token` behind `APP_ENV!=production` (team policy permitting) so Angular devs are not hand-running Python.

**Definition of done:** Fresh clone → register user → login → paste token → submit form succeeds against local API without editing backend.

### 3.2 Fix or quarantine integration tests (High)

**Primary:** **Sylvie** (`evaluate` / ingestion path); **Dom** (test harness, DB fixtures, `create_submission` expectations).

1. Replace `get_current_user` override with a **valid UUID** `sub` matching a mocked or fixture user that exists for FK constraints (or mock `create_submission` / DB entirely).
2. Replace `assignment_id` strings with **valid UUIDs** and mock `validate_assignment_exists` or provide DB fixture assignment.
3. Change assertion from `startswith("sub_")` to **UUID format** (or parse with `uuid.UUID`).

**Definition of done:** `pytest tests/test_evaluate_submission_integration.py` passes in CI with pinned dependencies.

### 3.3 Secure `POST /rubrics` and registration (High)

**Primary:** **Dom** (rubrics endpoint + auth/register are in Dom’s milestone scope).

1. Require `get_current_user` + `require_role("Instructor")` or `require_role("admin")` (align casing with JWT payload — today registration accepts arbitrary casing in `role` string).
2. For `register`: restrict `role` to an allowlist (`Student` only for public registration; instructor/admin via separate admin flow or invitation).

**Definition of done:** Anonymous `POST /rubrics` returns **401**; anonymous register cannot obtain `Admin` JWT.

### 3.4 Status page and milestone closure (Medium → treat as High for UX parity)

**Primary:** **Sylvie** (Angular scaffold + status polling per milestone); **Dom** (support if response shape changes).

1. Remove incorrect copy in `status-page.component.html` about the GET endpoint being pending.
2. Inject `EvaluationService` (or a small `SubmissionService`) to call `GET /api/v1/code-eval/submissions/:id` with bearer token, poll with `interval` + `takeWhile` until status leaves `Pending` (or cap attempts).
3. Update milestone doc checkbox when polling ships.

**Definition of done:** Hard refresh on `/status/<uuid>` loads submission row from API; polling visible in network tab.

---

## 4. Security and vulnerability assessment

| Topic | Owner(s) (milestone) | Finding |
|-------|----------------------|---------|
| **SQL injection** | **Dom** (ORM / API) | SQLAlchemy ORM used for queries; no raw string SQL observed in audited paths. **Low** risk in current code. |
| **XSS** | **Sylvie** (Angular) | Angular default escaping on templates; `errorMessage` binds text — avoid `innerHTML` without sanitization in future rich errors. |
| **Auth** | **Dom** | JWT HS256 with `SECRET_KEY` from settings — standard for M1; ensure production key rotation and length. |
| **IDOR** | **Dom** | Submission GET enforces `_can_view_submission` — **good**. Evaluate uses authenticated student id for new rows — **good**. |
| **Secrets in logs** | **Dom** (`llm.redact`); **Sylvie** (clone / `main.py` usage) | Clone stderr passed through `redact()` and explicit PAT replacement — **good**. |
| **GitHub PAT** | **Jayden** (ops / secrets); **Sylvie** (ingestion consumes PAT) | Server-wide PAT can read all repos the token can access; document least-privilege (fine-scoped PAT, SSO) in ops runbook. |
| **CORS** | **Jayden** (deployment); **Dom** (`settings` / middleware) | `allow_credentials=True` with configurable origins — ensure production `CORS_ORIGINS` is explicit, not `*`. |
| **Hardcoded secrets** | **Jayden** (`.env.example`); **Sylvie** (prod Angular env) | `.env.example` uses placeholders only — acceptable. `environment.prod.ts` empty token avoids committing secrets — acceptable. |

**Logic vulnerability (business rules):** Unauthenticated rubric spam and role escalation on register (§2) are the standout issues for Milestone 1 scope — **Dom**.

---

## 5. Efficiency and optimization (low-risk, high-reward)

*These paths sit in **Sylvie**’s ingestion / cache / preprocessor scope per milestone.*

1. **GitHub API calls:** `evaluate_submission` calls `validate_github_repo_access` then `resolve_repository_head_commit_hash`. For public metadata, consider using a single commits API call when acceptable, or cache branch SHA briefly in memory keyed by `(owner, repo, branch)` with TTL — **risk:** stale SHA if branch moves; only safe with short TTL or accept double call for correctness (**low risk** if TTL ≤ few seconds and documented).
2. **Preprocessing `os.walk`:** Already prunes directory names via `dirnames[:] = ...` — efficient. No change needed for M1.
3. **File cache index:** Every `load_repository_cache_entry` rewrites the index to update `last_used_at` — can become hot under load. **Low-risk improvement:** update `last_used_at` asynchronously or on a sample (e.g. 1/10 reads) — **risk:** analytics on cache age becomes approximate; defer until metrics require it.
4. **Concurrent cache miss:** Two workers could clone the same repo simultaneously before either writes the index; second clone may hit `409` on non-empty path or duplicate disk usage. **Mitigation (medium engineering effort):** per-cache-key file lock under `data/cache/locks/` before cloning — **risk:** deadlock if lock ordering wrong; needs careful design.

---

## 6. Positive conclusion

Milestone 1’s **core technical story is largely present:** PostgreSQL schema, authenticated evaluate flow with PAT-based clone, preprocessing, rubric fingerprint cache, JSON cache index with locking, regex redaction on failure paths, Angular submit flow, and a submissions read API suitable for polling. The **highest-impact gaps** are **security hardening** on register/rubrics (**Dom**), **client–server JWT contract documentation** (**Sylvie** + **Dom**), **test suite alignment** (**Sylvie** + **Dom**), and **finishing the status page** (**Sylvie**) so the milestone checklist and UX match the already-deployed backend (**Jayden** hosts the integrated stack per milestone).

---

## 7. Verification notes (environment)

- Local `python3 -m pytest` failed at collection with `ModuleNotFoundError: fastapi` / `server` — dependencies and `PYTHONPATH` were not configured in the audit shell. Findings on test staleness are from **static review** of [`server/tests/test_evaluate_submission_integration.py`](../server/tests/test_evaluate_submission_integration.py) against [`server/app/main.py`](../server/app/main.py).
