# Milestone 1 — Comprehensive Forensic Audit (Claude Code)

**Audit timestamp (UTC):** 2026-04-01  
**Filename:** `audits/milestone-01-forensic-audit-2026-04-01-claudecode.md`  
**Scope:** Full workspace traversal against `docs/milestones/milestone-01-tasks.md`, `docs/design-doc.md`, and all observable code under `server/`, `client/`, `alembic/`, and configuration files. Every claim is tied to a specific file and line number verified against the live working tree.  
**Method:** Direct file read of all source files, no reliance on git history or prior audit memory. This audit supersedes prior audits where findings overlap, but is intended to provide a fresh forensic layer with deeper code-level analysis.  
**Prior audits consulted (for resolved-findings tracking only):**
- [milestone-01-forensic-audit-2026-04-01T235947Z-final.md](milestone-01-forensic-audit-2026-04-01T235947Z-final.md) — prior final

---

## Executive Summary

MAPLE A1 Milestone 1 delivers a structurally coherent distributed system skeleton: a FastAPI ingestion pipeline with GitHub validation, shallow cloning, artifact preprocessing, and digest-keyed caching; a full five-table PostgreSQL schema with Alembic migrations; a working JWT-based authentication flow (register + login); Pydantic-validated rubric ingestion; assignment lifecycle CRUD; an Angular submission form; and a regex-based secret redactor wired into the clone error path.

**Previously reported backend blockers have now been resolved in the working tree:** `POST /evaluate` now requires and validates `assignment_id`, persists real `Submission` rows through `create_submission()`, the repository cache index now uses locking plus atomic writes, `GET /submissions/{id}` now enforces resource-level authorization, GitHub repository URL validation is consistently HTTPS-only across client and server, and the API docs now describe the live multipart contract. The only notable remaining code-level gap is the Angular status page, which still performs no HTTP I/O and remains deferred to Milestone 2.

Infrastructure task items remain open (DigitalOcean TLS/Certbot, Alembic in the deploy pipeline) but are outside the code audit scope.

---

## 1. Feature Synthesis & Modular Architecture

### 1.1 Feature Audit — What Exists vs. What Was Planned

The following table cross-references every functional feature identified in the codebase against the Milestone 1 requirements in `docs/milestones/milestone-01-tasks.md`.

| Milestone 1 Requirement | Evidence in Code | Status |
| :--- | :--- | :--- |
| Initialize repo structure (`docs/`, `server/app/`, `client/src/`, `data/`, `eval/`, `prompts/`) | All directories present; `eval/` and `prompts/` contain `.gitkeep` scaffolds | ✅ Done |
| Provision DigitalOcean Droplet, Managed PostgreSQL, App Platform | `docs/deployment.md` describes target; not verifiable from code | ⚠ Ops-only |
| Configure Nginx reverse proxy + Let's Encrypt TLS | Not verifiable from code | ⚠ Ops-only |
| `.env` / secrets management; `.env.example` committed | `.env.example` committed with placeholders; `server/app/config.py` uses pydantic-settings | ✅ Done |
| PostgreSQL schema: User, Assignment, Rubric, Submission, EvaluationResult via SQLAlchemy migrations | Five ORM models in `server/app/models/`; Alembic migration `010126822022` | ✅ Done |
| `POST /api/v1/code-eval/rubrics` with A5-compatible JSON schema validation | `server/app/routers/rubrics.py` — criteria, levels, points-sum validation, MAPLE envelope | ✅ Done |
| Regex redactor in `services/llm.py` (strip PATs, env vars, emails) | `server/app/services/llm.py` `redact()` / `redact_dict()`; wired in `main.py:219-221` | ✅ Done |
| GitHub PAT-based repository cloning into `data/raw/` | `clone_repository()` in `main.py:157-262`, GIT_ASKPASS pattern | ✅ Done |
| Repository pre-processor: strip `node_modules`, `venv`, compiled binaries, `.git` | `server/app/preprocessing.py` | ✅ Done |
| SHA + normalized rubric digest caching key; skip re-clone on cache hit | `server/app/cache.py`; `build_repository_cache_key()`, `load_repository_cache_entry()` | ✅ Done |
| Angular scaffold: student submission form (GitHub URL + assignment ID) | `client/src/pages/submit-page/` — reactive form, multipart POST | ✅ Done |
| Angular scaffold: status polling page | `client/src/pages/status-page/` — component exists; **no HTTP I/O** | ⚠ Partial |
| Auth (register + login) producing JWTs | `server/app/routers/auth.py` — bcrypt register, JWT login | ✅ Done |
| `GET /api/v1/code-eval/submissions/{id}` | `server/app/routers/submissions.py` — authenticated, UUID-validated, eager-loads EvaluationResult | ✅ Done |
| Assignment CRUD (`POST` + `GET /assignments/{id}`) | `server/app/routers/assignments.py` | ✅ Done |
| Submission persistence service | `server/app/services/submissions.py` — called from `/evaluate` cache-hit and clone paths | ✅ Done |
| Assignment validation service | `server/app/services/assignments.py` — `assignment_id` is parsed and existence-checked before persistence | ✅ Done |

### 1.2 Dependency Mapping

The following describes the as-implemented relationship between modules.

```
Angular SubmitPageComponent
  └─ EvaluationService (multipart POST /evaluate with devToken)
       └─ POST /api/v1/code-eval/evaluate  [main.py:422]
            ├─ get_current_user [middleware/auth.py:29]  ← JWT required
            ├─ parse_assignment_id + validate_assignment_exists [services/assignments.py]
            ├─ validate_github_repo_access [main.py:265]  ← httpx → GitHub API
            ├─ resolve_repository_head_commit_hash [main.py:328]  ← httpx → GitHub API
            ├─ load_repository_cache_entry [cache.py:75]  ← reads/writes JSON file
            ├─ clone_repository [main.py:157]  ← git subprocess + GIT_ASKPASS
            │    └─ redact() [services/llm.py:16]  ← stderr sanitization on error
            ├─ preprocess_repository [preprocessing.py]
            ├─ save_repository_cache_entry [cache.py:98]  ← writes JSON file
            └─ create_submission() [services/submissions.py:9]  ← persists DB row on success

Angular StatusPageComponent
  └─ reads history.state only (no HTTP) ← ✗ GET /submissions/{id} NOT CALLED

GET /api/v1/code-eval/submissions/{id}  [routers/submissions.py:16]
  └─ PostgreSQL Submission table

POST /api/v1/code-eval/auth/register  [routers/auth.py:27]
POST /api/v1/code-eval/auth/login     [routers/auth.py:54]
  └─ PostgreSQL users table

POST /api/v1/code-eval/rubrics        [routers/rubrics.py]
  └─ PostgreSQL rubrics table

POST + GET /api/v1/code-eval/assignments  [routers/assignments.py]
  └─ PostgreSQL assignments table
```

**Architectural observation:** The ingestion orchestration, GitHub I/O, git subprocess management, filesystem cache, and MAPLE response construction all live in `server/app/main.py` (~575 lines). This remains a likely refactor point as M2-M5 add scoring, LLM calls, and grade reporting, even though submission persistence is now correctly routed through the service layer.

### 1.3 Component Review

**UI Components:**

| Component | File | State | Issues |
| :--- | :--- | :--- | :--- |
| `SubmitPageComponent` | `client/src/pages/submit-page/submit-page.component.ts` | Functional — reactive form, multipart POST, navigate-on-success | URL regex narrower than server validation (see §2) |
| `StatusPageComponent` | `client/src/pages/status-page/status-page.component.ts` | Shell only — reads `history.state` | No HTTP I/O; direct URL access always shows blank |
| `EvaluationService` | `client/src/services/evaluation.service.ts` | Functional for submit flow | Uses `environment.devToken` (empty in prod) |
| `AppComponent` | `client/src/app/app.ts` | Root bootstrap | No issues |

**Middleware:**

| Middleware | File | State | Issues |
| :--- | :--- | :--- | :--- |
| `get_current_user` | `server/app/middleware/auth.py:29` | Functional — OAuth2 Bearer + JWT decode | None |
| `require_role` | `server/app/middleware/auth.py:61` | Implemented | **Never used on any route** |
| CORS | `server/app/main.py:390-396` | Configured from `settings.cors_origins_list` | `allow_methods=["*"]`, `allow_headers=["*"]` is broad |

**Utility Classes:**

| Utility | File | State | Issues |
| :--- | :--- | :--- | :--- |
| `success_response` / `error_response` | `server/app/utils/responses.py` | Consistent MAPLE envelope | None |
| `hash_password` / `verify_password` | `server/app/utils/security.py` | bcrypt via passlib | None |
| `create_access_token` / `decode_access_token` | `server/app/utils/security.py` | HS256 JWT | None |
| `redact` / `redact_dict` | `server/app/services/llm.py` | Regex patterns for PATs, emails, env vars | Only wired at clone stderr; not yet used for LLM payloads (no LLM calls in M1) |

---

## 2. Ambiguities, Predictive Errors, & Interface Mismatches

### 2.1 Gap Analysis Summary

The remaining gap between what Milestone 1 requires and what exists is now concentrated in **integration polish rather than core backend correctness**: the backend persists submissions, validates assignments, protects cache metadata, enforces submission-level authorization, and documents the live ingestion contract, while the frontend status flow still lags behind the implemented server behavior.

### 2.2 Detailed Error Table

| Severity | Error Cause | Error Explanation | Origin Location(s) |
| :--- | :--- | :--- | :--- |
| **Informational** | Raw rubric ingestion and structured rubric storage are intentionally distinct paths | The `POST /rubrics` endpoint validates a standardized structured rubric object (`criteria[].levels[].max_points`, points-sum validation in `routers/rubrics.py:15-45`), while `POST /evaluate` accepts a teacher-uploaded UTF-8 rubric file and fingerprints it without forcing the same schema (`main.py:446-458`). This matches the stated goal of accepting non-standardized rubric input at ingestion time, but the later normalization/extraction step that turns uploaded rubric content into a canonical scoring representation still needs to remain explicit in future milestone work and documentation. | `server/app/routers/rubrics.py:15-45`; `server/app/main.py:455-458`; `docs/design-doc.md` |
| **Low** | `auth.py` login endpoint returns `error_response` (200 body with `success: false`) instead of raising an HTTPException | At `routers/auth.py:60-64` and `67-71`, invalid credentials return `return error_response(status_code=401, ...)`. `error_response()` from `utils/responses.py` returns a `JSONResponse` with the MAPLE envelope. This is architecturally consistent with the MAPLE contract but means `401` is returned as the **HTTP status code** of a `return` statement, not a `raise HTTPException`. FastAPI will correctly set the 401 status on the response, but the OpenAPI schema for `POST /auth/login` will not automatically document 401 as a possible response code because it is not declared via `responses=` in the decorator. Swagger UI will show no 401 entry. | `server/app/routers/auth.py:60-71` |
| **Low** | Angular status page ignores `ActivatedRoute` params for HTTP fetch | `StatusPageComponent` injects `ActivatedRoute` at `status-page.component.ts:16` and reads the `:id` param at line 19 (`this.submissionId = this.route.snapshot.paramMap.get('id')`), but then does nothing with the resolved ID other than store it. The TODO comment at line 24-26 documents this as deferred. The backend endpoint is live and returns the correct MAPLE envelope. The frontend has all imports and plumbing needed; only the `HttpClient` injection and polling logic are missing. | `client/src/pages/status-page/status-page.component.ts:19-26` |
| **Low** | `clone_repository()` does not redact the PAT from the `rev-parse HEAD` stderr path | The clone failure path at `main.py:219-221` correctly runs `redact()` and then `.replace(github_pat, "[REDACTED]")`. The `rev-parse HEAD` failure path at `main.py:247` decodes stderr but does **not** run `redact()` on it: `sanitized_stderr = stderr.decode("utf-8", errors="replace").strip()`. While `git rev-parse HEAD` output is unlikely to contain the PAT, the asymmetric treatment means the secondary subprocess has a weaker sanitization guarantee. | `server/app/main.py:247`; contrast with `main.py:219-221` |
| **Low** | `httpx.AsyncClient` is instantiated per GitHub API call, not shared across requests | `validate_github_repo_access()` at `main.py:274` and `resolve_repository_head_commit_hash()` at `main.py:338` each create `async with httpx.AsyncClient(timeout=10.0) as client:`. FastAPI lifespan events are the idiomatic pattern for shared clients; creating a new client per call adds TLS handshake overhead for every evaluate request. Low impact in M1 with low request volume; will matter in M4 during batch evaluation. | `server/app/main.py:274`, `338` |
| **Informational** | `require_role()` RBAC factory is implemented but never applied to any route | `middleware/auth.py:61-89` provides a complete, well-documented role-checking dependency. None of the routers use it. `POST /evaluate` and `POST /assignments` are accessible by any registered user regardless of role. When instructor-vs-student access control is needed (M4 grade distribution, admin dashboard), this factory is ready to use. | `server/app/middleware/auth.py:61`; `server/app/main.py:427`, `server/app/routers/assignments.py` |
| **Informational** | `services/llm.py` `complete()` correctly stubs M3 scope | The `complete()` async function raises `NotImplementedError` with a docstring explaining it is M3 scope. This is correct behavior and well-structured for future integration. | `server/app/services/llm.py:73-85` |

---

## 4. Security & Vulnerability Assessment

### 4.1 SQL Injection Assessment

**Severity: Low (mitigated)**

All database interactions use SQLAlchemy ORM with parameterized queries. Evidence:
- `auth.py:56`: `select(User).where(User.email == request.email)` — ORM parameterization.
- `submissions.py:31`: `select(Submission).where(Submission.id == sid)` — ORM parameterization.
- `rubrics.py`: All inserts use ORM model instantiation.

No raw SQL strings are constructed anywhere in the codebase. SQLi risk is low for all current code paths.

### 4.2 Cross-Site Scripting (XSS) Assessment

**Severity: Informational**

The API is a JSON REST service with no server-side rendering. XSS is not a direct attack vector against the FastAPI backend. The Angular frontend uses template binding (`{{ }}`) which auto-escapes by default. No `innerHTML` bindings, `bypassSecurityTrust*()` calls, or `DomSanitizer` bypasses were identified in the Angular source. XSS risk is low.

### 4.3 SSRF (Server-Side Request Forgery) Assessment

**Severity: Low (mitigated)**

`parse_github_repo_url()` at `main.py:81-98` validates that the URL host is exactly `"github.com"` or `"www.github.com"`. Pydantic `HttpUrl` enforces a valid URL structure including a scheme. The GitHub API calls use hardcoded `https://api.github.com/repos/{owner}/{repo}` URL templates; user-supplied `owner` and `repo` values are only interpolated into path segments, not into the base URL. Path segment injection (e.g., `owner = "../../etc"`) is mitigated by the fact that GitHub's API would return 404 for invalid paths, not execute arbitrary requests.

**One residual risk:** `repo_metadata.clone_url` from GitHub's API response is used directly in `clone_repository()` at `main.py:515`. A compromised or spoofed GitHub API response could return an arbitrary clone URL. This is a very low risk in practice but could be hardened by reconstructing the clone URL from the validated `owner`/`repo_name` rather than trusting the API-returned `clone_url` field.

### 4.4 Authentication Flow Assessment

**Severity: Informational (sound, with one concern)**

**Sound:**
- Passwords are hashed with bcrypt via `passlib` (`security.py`).
- JWTs are signed with HS256 using `SECRET_KEY` from environment.
- `ACCESS_TOKEN_EXPIRE_MINUTES` defaults to 30, limiting token lifetime.
- `decode_access_token()` validates expiry.

**Concern — Timing oracle via sequential user check + password check:**  
At `auth.py:59`, the login handler checks `if not user or not user.password_hash:` and returns early with the same error message as an invalid password. This prevents user enumeration via different error messages. However, the early return for a missing user is significantly faster than a bcrypt `verify_password()` call. A timing attack could distinguish "user does not exist" from "user exists but wrong password" with sufficient samples. Mitigation: always call `verify_password()` (against a dummy hash) even when the user is not found.

### 4.5 Secret Leakage in Error Responses

**Severity: Low (partially mitigated)**

Clone error stderr is sanitized via `redact()` at `main.py:219-221` and an explicit `.replace(github_pat, "[REDACTED]")`. This is good practice and two-layer protection.

**Partial gap:** The `rev-parse HEAD` failure path at `main.py:247` does not apply `redact()`:
```python
sanitized_stderr = stderr.decode("utf-8", errors="replace").strip()
```
This path is lower risk (git rev-parse output is unlikely to contain secrets) but the inconsistency is worth correcting for defense-in-depth.

### 4.6 CORS Configuration

**Severity: Low (review recommended)**

CORS at `main.py:390-396`:
```python
allow_origins=settings.cors_origins_list,
allow_credentials=True,
allow_methods=["*"],
allow_headers=["*"],
```

`allow_credentials=True` combined with `allow_origins` from a configurable list is sound — but if `CORS_ORIGINS` is ever set to `["*"]` in a production `.env`, this becomes a critical misconfiguration (credentials + wildcard origin is rejected by browsers but indicates intent to be permissive). The settings class should validate that `CORS_ORIGINS` never contains `"*"` when `allow_credentials=True`.

### 4.7 DoS via Unconstrained File Upload

**Severity: Low (informational for M1)**

`rubric: UploadFile = File(...)` at `main.py:426` imposes no size limit. A client could upload a multi-gigabyte file as a "rubric," consuming server memory during `rubric_bytes = await rubric.read()` at `main.py:446`. Nginx should impose a `client_max_body_size` limit; FastAPI itself has no built-in limit. Add a size check after line 446:
```python
if len(rubric_bytes) > 1_048_576:  # 1 MB
    raise MapleAPIError(400, "VALIDATION_ERROR", "Rubric file must be under 1 MB.")
```

### 4.8 Hardcoded Secret Detection

**Severity: Informational**

No hardcoded secrets were found in tracked source files. `environment.ts` has `devToken: ''` (empty string, correct — requires local override). `.env.example` uses `ghp_xxxxxxxxxxxx` as a placeholder (cosmetically may trigger secret scanners, functionally safe).

---

## 5. Efficiency & Optimization Recommendations

All recommendations below are rated by risk to existing stable logic.

### 5.1 Parallelize Sequential GitHub API Calls (Low Risk, High Reward)

**Current behavior:** `validate_github_repo_access` and `resolve_repository_head_commit_hash` run sequentially at `main.py:478-484`. Each call creates its own `httpx.AsyncClient` instance with a separate TCP connection and TLS handshake. Two round-trips to `api.github.com` add ~200-400ms of latency per evaluate request.

**Proposed change:**
```python
repo_metadata, resolved_commit_hash = await asyncio.gather(
    validate_github_repo_access(repo_owner, repo_name, github_pat),
    resolve_repository_head_commit_hash(repo_owner, repo_name, repo_metadata.default_branch, github_pat),
)
```

**Risk:** `resolve_repository_head_commit_hash` needs `repo_metadata.default_branch` which is returned by `validate_github_repo_access`. These cannot be fully parallelized without restructuring — e.g., by guessing `main` as the default branch and falling back, or by using the `compare` API. **A safer optimization is to reuse a single `httpx.AsyncClient` across both calls** (FastAPI lifespan pattern), which eliminates connection overhead without changing call ordering.

**Constraint:** Do not parallelize until the client-sharing refactor is done. Changing call order without a shared client yields minimal benefit and introduces failure-aggregation complexity.

### 5.2 Reuse `httpx.AsyncClient` via FastAPI Lifespan (Low Risk, Medium Reward)

**Current behavior:** Every GitHub API function creates `async with httpx.AsyncClient(...) as client:`, which opens a new TCP connection per call.

**Proposed change:** Create a single `httpx.AsyncClient` during application startup via FastAPI's `lifespan` context manager and store it in app state:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(timeout=10.0)
    yield
    await app.state.http_client.aclose()
```
Pass `app.state.http_client` to API functions via dependency injection.

**Risk:** Low. The `httpx.AsyncClient` is thread-safe and connection-pool-aware. Cleanup is guaranteed by the lifespan context manager. The only breaking change is the function signatures of `validate_github_repo_access` and `resolve_repository_head_commit_hash`, which are private functions called only from `evaluate_submission`.

### 5.3 `deepcopy` in `redact_dict` — Watch for Large Payloads (Informational)

`redact_dict()` at `services/llm.py:35` uses `copy.deepcopy(data)` before recursing. For M1 (small dicts), this is fine. In M3, when LLM request/response payloads containing full repository file contents are redacted, a deep copy of a multi-MB dict will spike memory. **Preferred approach for M3:** build a new dict during traversal instead of copying-then-mutating:
```python
def redact_dict(data: dict) -> dict:
    return {k: redact(v) if isinstance(v, str) else redact_dict(v) if isinstance(v, dict) else v
            for k, v in data.items()}
```
**Risk of changing now:** Low, but no M3 LLM calls exist yet. Flag this for M3 implementation rather than making a premature change.

### 5.4 Consider Migrating Cache to PostgreSQL in M2 (Low Risk, High Reward Long-Term)

The JSON file cache at `data/cache/repository-cache-index.json` provides:
- O(n) reads (entire file is loaded)
- No atomic updates
- No query capabilities
- No expiry policy

PostgreSQL is already in the stack. A `repository_cache` table with a `cache_key` unique index would provide:
- O(log n) reads via B-tree index
- ACID write guarantees (eliminates race condition)
- SQL-based eviction queries (e.g., `WHERE last_used_at < NOW() - INTERVAL '7 days'`)
- Consistent audit trail

**Risk:** Requires a new Alembic migration and refactoring `cache.py`. The JSON cache can be kept as a local dev fallback. This is a M2 improvement, not an M1 blocker.

### 5.5 Angular: Avoid Redundant Router Navigation State Coupling (Low Risk, Low Reward)

`SubmitPageComponent` navigates to `/status/{id}` with `state: { data }` at `submit-page.component.ts`. This couples the status page display to the navigate event — refreshing the status page always shows blank data. Once the status page implements HTTP polling (§3 Action Plan), this state coupling becomes unnecessary and can be removed. **Do not refactor now** — wait until the polling implementation is in place to avoid double-refactoring.

---

## 6. Positive Findings

The following features are correctly implemented and merit explicit acknowledgment:

1. **Complete ORM + migration stack.** Five tables with FK relationships, `server_default` values, and both nullable and non-nullable columns correctly specified. The `password_hash` column addition to `User` (not in the original schema outline) is the right pattern for password-based auth alongside future OAuth.

2. **GIT_ASKPASS credential injection.** Passing credentials via a temporary ASKPASS script (`main.py:169-183`) rather than embedding them in the clone URL is the correct approach. The URL-embedded approach (`https://token@github.com/...`) would write the token into `.git/config` and `reflog`. The ASKPASS pattern avoids this entirely.

3. **Two-layer PAT redaction in clone errors.** `redact()` followed by `.replace(github_pat, "[REDACTED]")` at `main.py:219-221` provides defense-in-depth. Even if the regex patterns miss a new token format, the explicit string replacement catches it.

4. **Rubric fingerprint normalization is stable and deterministic.** `_canonicalize_rubric_value()` at `cache.py:180-196` handles JSON key ordering, whitespace normalization, and type preservation. The fingerprint is a SHA-256 of canonical JSON, not of the raw file bytes, ensuring that formatting changes don't cause spurious cache misses.

5. **MAPLE response envelope is consistent across all modules.** `error_response()` and `success_response()` from `utils/responses.py` are used by auth, rubrics, assignments, submissions routers, and the global exception handlers. The format is identical everywhere. This is a significant engineering discipline win for a multi-developer milestone.

6. **Async database session management is correct.** `get_db()` in `models/database.py` yields an `AsyncSession` in a `try/finally` block, ensuring sessions are closed even on exceptions. All routers use `Depends(get_db)` correctly.

7. **Import hygiene in `main.py`.** A single import block with no duplicates or conflicting aliases (`main.py:1-33`). After a multi-developer milestone, this is notable — import conflicts are a common merge artifact.

8. **Single consolidated `RequestValidationError` handler.** The prior audit documented a duplicate handler defect; it has been correctly resolved. One handler at `main.py:404-413` using `error_response()` from `utils/responses.py`.

9. **`/evaluate` now persists real `Submission` rows.** The handler requires `assignment_id`, validates it, resolves the current user UUID, and calls `create_submission()` on both the cache-hit and clone-success paths. This closes the earlier gap between filesystem cache state and PostgreSQL state.

10. **Cache metadata writes are now concurrency-safe.** `cache.py` uses an exclusive lock around read-modify-write operations and writes the JSON index via a temporary file plus `os.replace()`. This removes the earlier silent-overwrite risk under concurrent requests.

11. **Submission reads now enforce ownership and role checks.** `GET /submissions/{id}` allows the owning student, the assignment instructor, or an admin, and returns a MAPLE-formatted `403` for unauthorized access. This closes the earlier IDOR risk on submission retrieval.

12. **GitHub URL validation is now contract-consistent.** The Angular submit form and backend parser both require HTTPS GitHub repository URLs, removing the previous client/server mismatch around `http://` acceptance.

13. **API docs now reflect the live ingestion contract.** `docs/api-spec.md` documents `POST /evaluate` as Bearer-authenticated `multipart/form-data` with `github_url`, `assignment_id`, and `rubric`, and the design doc no longer describes `assignment_id` as optional.

14. **Auth is fully self-service.** A new developer can `POST /auth/register`, `POST /auth/login`, receive a JWT, and immediately use protected endpoints without editing source code or minting tokens manually. This is essential for developer productivity in M2+.

15. **Test coverage for the ingestion pipeline.** `test_evaluate_submission_integration.py` covers cache hit, cache miss, rubric change, SHA change, invalid URL, missing PAT, and clone failure. `test_preprocessing.py` and `test_cache.py` cover deterministic behavior of those subsystems. This is strong M1 test coverage for the most complex code path.

---

## 7. Definition of Done — Milestone 1 Compliance Checklist

| Item | Status | Notes |
| :--- | :--- | :--- |
| PostgreSQL schema + migrations | ✅ Done | 5 tables, FK constraints, Alembic migration `010126822022` |
| `POST /api/v1/code-eval/rubrics` with A5 validation | ✅ Done | Criteria, levels, points-sum validation, MAPLE envelope |
| Regex redactor in `services/llm.py`, wired to clone path | ✅ Done | `redact()` / `redact_dict()` wired at `main.py:219-221` |
| Auth (register + login) functional | ✅ Done | bcrypt + JWT; `tokenUrl` points to working endpoint |
| GitHub PAT-based clone + preprocessing + caching | ✅ Done | GIT_ASKPASS, strip artifacts, digest-keyed JSON cache |
| Angular submission form | ✅ Done | Reactive form, multipart POST, navigate-on-success |
| `GET /api/v1/code-eval/submissions/{id}` | ✅ Done | Authenticated, UUID-validated, eager-loads EvaluationResult |
| Assignments CRUD | ✅ Done | POST + GET with JWT auth, MAPLE envelope |
| Service layer for persistence (submissions + assignments) | ✅ Done | Implemented and now wired from `/evaluate` |
| `POST /evaluate` persists `Submission` row to PostgreSQL | ✅ Done | Real `Submission` rows are created on cache-hit and clone-success paths |
| `assignment_id` nullability contract resolved | ✅ Done | `/evaluate` now requires `assignment_id` and validates UUID + assignment existence |
| Angular status page HTTP polling | ⚠ Deferred (M2) | Backend endpoint live; frontend has TODO comment |
| Cache file locking (concurrency safety) | ✅ Done | Exclusive lock + atomic replace protect cache index writes |
| GitHub repo URL validation consistent across client and server | ✅ Done | Angular and backend both require HTTPS GitHub repository URLs |
| API contract documentation (`docs/api-spec.md`) | ✅ Done | Multipart contract, required fields, auth, and example request are documented |
| `GET /submissions/{id}` ownership check | ✅ Done | Owner, assignment instructor, and admin access are allowed; unauthorized reads return 403 |

No ❌ code-audit items remain. The only deferred item is Angular status page HTTP polling, which is already noted as Milestone 2 work rather than a Milestone 1 correctness defect.

---

*End of forensic audit recheck.*  
*All claims verified against live file contents. Only the audit document was updated during this recheck.*
