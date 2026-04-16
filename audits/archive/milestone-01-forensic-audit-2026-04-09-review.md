# Milestone 1 — Second-Pass Forensic Audit (Review of 2026-04-07 Report)

**Auditor role:** Senior Technical Auditor — second-pass verification  
**Scope:** Line-by-line verification of every claim in [`audits/milestone-01-forensic-audit-2026-04-07.md`](./milestone-01-forensic-audit-2026-04-07.md) against actual source files as they exist on 2026-04-09. All citations below are traced to the exact line in the file that was read during this audit.  
**Method:** Every file referenced by the prior audit was opened independently. No claim was taken on faith. Where the prior audit's cited line range did not match actual file content, this report records the discrepancy with a direct quote from both the prior audit and the actual code.

---

## Executive Summary

The 2026-04-07 audit is partially reliable. Its **security findings** (unauthenticated `/rubrics`, open role registration, JWT contract documentation gap) are accurate and remain actionable. Its **positive observations** on the cache, GitHub error taxonomy, submission authorization, and preprocessing are confirmed.

However, the audit contains **two entirely false High-severity findings** that must be retracted, **one misidentified error code**, and **one false Low-severity finding** — all of which were apparently based on a version of the codebase that does not match the current repository. These errors are not minor: one of the false findings consumed the largest block of remediation text in §3.2 and would cause the team to waste engineering time fixing tests that are already correct and comprehensive.

Additionally, the audit **missed five substantive findings** that are present in the code today, including a PAT redaction gap, a stale TODO comment with a false premise, an unguarded UUID parse in `assignments.py`, a `str(None)` serialization defect in the submissions response, and a casing inconsistency in the role-check infrastructure.

---

## Part 1 — Corrections: False or Inaccurate Claims

### 1.1 RETRACTION — "Integration tests out of sync with API contract" (§2, High, Dom + Sylvie)

**Prior audit claim:**
> `test_evaluate_submission_integration.py` overrides `get_current_user` with `{"sub": "test-user", ...}` (invalid UUID for evaluate path), uses `assignment_id="asgn_abc123"` (not a UUID — fails `parse_assignment_id`), and asserts `submission_id.startswith("sub_")` while production returns **database UUID strings** from `create_submission`. These tests would not pass without extensive rewriting.

**What the file actually contains:**

Opening `server/tests/test_evaluate_submission_integration.py`:

```python
# lines 22–24
MOCK_STUDENT_ID = "00000000-0000-0000-0000-000000000001"
MOCK_SUBMISSION_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
MOCK_ASSIGNMENT_ID = "11111111-2222-3333-4444-555555555555"
```

```python
# line 33
app.dependency_overrides[get_current_user] = lambda: {"sub": MOCK_STUDENT_ID, "role": "user"}
```

`MOCK_STUDENT_ID` is `"00000000-0000-0000-0000-000000000001"` — a syntactically valid UUID string. The `evaluate_submission` handler calls `UUID(current_user["sub"])` at `main.py:480`; this call succeeds. The prior audit's claim that the sub was `"test-user"` is false.

`MOCK_ASSIGNMENT_ID` is `"11111111-2222-3333-4444-555555555555"` — also a valid UUID. The prior audit's claim that it was `"asgn_abc123"` is false.

On the `submission_id` assertion, the contract validator reads:

```python
# lines 769–772
try:
    uuid.UUID(payload["data"]["submission_id"])
except ValueError:
    self.fail(f"submission_id '{payload['data']['submission_id']}' is not a valid UUID")
```

The test validates that `submission_id` **is** a valid UUID — it does not assert `startswith("sub_")`. The prior audit's claim to the contrary is false.

**Scope of the test suite (not acknowledged by prior audit):**  
The file contains eleven test methods covering: non-GitHub URL rejection, missing PAT, invalid PAT (401), inaccessible repo (400), empty rubric, cache miss with preprocessing verification, cache hit (clone/preprocess skipped), stale commit SHA triggers re-clone, stale rubric triggers re-clone, unreadable cache JSON (500), preprocessing failure (500), clone failure (502), nonexistent assignment (404), and existing assignment (200). The tests properly mock all external dependencies and validate both the success response shape and side effects (filesystem state, cache index entries). This is a well-engineered test suite.

**Impact on §3.2:** The entire remediation section "Fix or quarantine integration tests" is unnecessary. **No action is required on the test file.** The team should not spend time on this.

---

### 1.2 RETRACTION — "Import style inconsistency" (§2, Low, Dom)

**Prior audit claim:**
> `rubrics.py` uses `from server.app.models import ...` while sibling routers use relative `..models`. Works if `PYTHONPATH` includes project root; fragile for alternate run configurations. (cited: `9:10:server/app/routers/rubrics.py`)

**What the file actually contains:**

```python
# server/app/routers/rubrics.py, lines 9–10
from ..models import Rubric, get_db
from ..utils.responses import success_response, error_response
```

These are **relative imports**, identical in style to every other router. There is no absolute `from server.app.models import ...` anywhere in the file. The prior audit's specific claim is false.

**What IS a genuine (though minor) inconsistency:**  
`rubrics.py` imports `get_db` from `..models` (the package `__init__.py`), while every other router imports it from the more specific `..models.database`:

```
# assignments.py:9, auth.py:7, submissions.py:8
from ..models.database import get_db

# rubrics.py:9
from ..models import Rubric, get_db
```

This works if `models/__init__.py` re-exports `get_db`, but it is an inconsistency in import depth — the opposite of what the prior audit described. Severity remains Low; the real fix is to align `rubrics.py` with its siblings by importing from `..models.database`.

---

### 1.3 CORRECTION — Error code mislabeled in JWT sub finding (§2, High)

**Prior audit claim:**
> Any token whose `sub` is not a UUID returns **401** (`AUTHENTICATION_ERROR`).

**What the code actually raises** (`server/app/main.py:479–486`):

```python
try:
    student_id = UUID(current_user["sub"])
except (ValueError, KeyError):
    raise MapleAPIError(
        status_code=401,
        code="AUTH_ERROR",
        message="Invalid user identity in token.",
    )
```

The error code is `"AUTH_ERROR"`, not `"AUTHENTICATION_ERROR"`. This distinction matters because any client-side error handling, tests, or monitoring that keys on the string `"AUTHENTICATION_ERROR"` will not match this path. GitHub access errors in `validate_github_repo_access` (`main.py:294`) do use `"AUTHENTICATION_ERROR"` — so there are already two different 401 codes in this handler, and they are semantically different. Client code must distinguish them.

Additionally, the prior audit cites line range `496:503:server/app/main.py` for this block. The actual lines are **479–486** in the current file. This is a minor but forensically significant discrepancy.

---

### 1.4 CORRECTION — `resolve_repository_head_commit_hash` 403/404 handling described imprecisely (§1.3)

**Prior audit claim:**
> Distinct handling for 401 PAT, 403 rate limit vs access, 404, and generic 502 paths in `validate_github_repo_access` and `resolve_repository_head_commit_hash`.

This is **partially accurate**. In `validate_github_repo_access` (`main.py:293–327`), 403 is bifurcated into rate-limit vs access-denied based on the `X-RateLimit-Remaining` header. That distinction is correctly described.

However, in `resolve_repository_head_commit_hash` (`main.py:357–370`), 403 and 404 are **combined** into a single handler:

```python
# main.py:364–369
if response.status_code in {403, 404}:
    raise MapleAPIError(
        status_code=400,
        code="VALIDATION_ERROR",
        message="Repository commit SHA could not be resolved for the current default branch.",
    )
```

There is no rate-limit check in this second function. A 403 caused by rate-limiting on the commits API returns a generic `VALIDATION_ERROR` instead of the correct `EXTERNAL_SERVICE_ERROR`. This is a logic gap the prior audit did not distinguish — it implied symmetrical error handling across both functions, which is not the case.

---

### 1.5 CORRECTION — Status page HTML message attribution (§2, Medium)

**Prior audit claim** (line reference `34:41:client/src/pages/status-page/status-page.component.html`):
> Status page shows a **stale** user message claiming `GET /submissions/:id` is "pending"

The finding is **correct in substance** but the line range is off. The stale message lives at line 37:

```html
<!-- status-page.component.html:37 -->
<p>Submission <strong>{{ submissionId }}</strong> was received, but live status lookup is not yet
 available. A <code>GET /api/v1/code-eval/submissions/:id</code> endpoint is pending backend
 implementation.</p>
```

The `GET /submissions/{id}` router is fully implemented in `server/app/routers/submissions.py` (lines 36–89). The HTML claim that the endpoint is "pending backend implementation" is false. This remains a valid Medium finding — the copy must be corrected.

---

## Part 2 — Confirmed Findings (Prior Audit Was Correct)

These findings were verified against actual file content and are accurate:

### 2.1 Unauthenticated `POST /rubrics` (High, Dom) — CONFIRMED

```python
# server/app/routers/rubrics.py:48–49
@router.post("")
async def create_rubric(request: RubricCreateRequest, db: AsyncSession = Depends(get_db)):
```

No `Depends(get_current_user)` present. Any caller with network access to the API can insert rubric rows. The `require_role` dependency exists in `middleware/auth.py` (lines 61–89) and is not wired here. This is a real security gap.

### 2.2 Open registration role escalation (High, Dom) — CONFIRMED

```python
# server/app/routers/auth.py:15–18
class RegisterRequest(BaseModel):
    email: str
    password: str
    role: str = "Student"
```

No allowlist validation. A POST to `/auth/register` with `{"email": "...", "password": "...", "role": "admin"}` succeeds and stores `"admin"` in `users.role`. The subsequent login issues a JWT with `"role": "admin"` in the payload. This is a real security gap.

### 2.3 JWT `sub` developer onboarding problem (High, Sylvie + Dom) — CONFIRMED

```typescript
// client/src/environments/environment.ts:4–6
// devToken is intentionally empty here. Create environment.development.ts (gitignored)
// with your local signed JWT. To generate one, run from the server virtualenv:
//   python -c "from app.utils.security import create_access_token; print(create_access_token({'sub': 'dev', 'role': 'user'}))"
```

```typescript
// client/src/environments/environment.development.ts.example:2–3
//   python -c "from app.utils.security import create_access_token; print(create_access_token({'sub': 'dev', 'role': 'user'}))"
```

A developer who follows this instruction generates a token with `sub: 'dev'`. At `main.py:480`, `UUID('dev')` raises `ValueError`, and the handler returns 401 `AUTH_ERROR`. The developer's Angular form submission will fail. This is a real onboarding friction issue. Note that the correct flow — register via `/auth/register`, login via `/auth/login`, paste the resulting token — does produce a valid UUID sub because `auth.py:73` uses `str(user.id)`.

### 2.4 Status polling page incomplete (Medium, Sylvie) — CONFIRMED

```typescript
// client/src/pages/status-page/status-page.component.ts:18–27
ngOnInit(): void {
  this.submissionId = this.route.snapshot.paramMap.get('id');
  const state = history.state as { data?: SubmissionData };
  this.data = state?.data ?? null;

  // TODO (Milestone 2): If data is null, fetch submission status from
  // GET /api/v1/code-eval/submissions/:id using this.submissionId.
  // Poll on an interval until status transitions out of a pending state.
}
```

Hard navigation to `/status/<uuid>` produces an empty state card. No HTTP call is made. No polling exists. The backend `GET /submissions/{id}` is live and returns a full response shape (see `submissions.py:36–89`). The UI and the backend are not connected. This remains an open milestone deliverable.

### 2.5 Design doc `Rubric.assignment_id` discrepancy (Medium, Dom) — CONFIRMED

```
# docs/design-doc.md:172
**Rubric:** Stores the grading criteria. Contains `id`, `assignment_id`, and `schema_json`.
```

```python
# alembic/versions/010126822022_create_initial_schema.py:35–43
op.create_table(
    "rubrics",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("title", sa.String(), nullable=False),
    sa.Column("total_points", sa.Integer(), nullable=False),
    sa.Column("schema_json", sa.JSON(), nullable=False),
    sa.Column("created_at", ...),
    sa.PrimaryKeyConstraint("id"),
)
```

No `assignment_id` in the `rubrics` table. The relationship runs the other direction: `assignments.rubric_id → rubrics.id`. The design doc is wrong on the data model. New contributors who read the design doc will be misled.

### 2.6 `success_response` / `error_response` type mismatch (Low, Dom) — CONFIRMED

```python
# server/app/utils/responses.py:13–19
def success_response(data: dict) -> dict:
    return {
        "success": True,
        "data": data,
        "error": None,
        "metadata": _build_metadata(),
    }

def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(...)
```

`success_response` returns a raw `dict`, `error_response` returns a `JSONResponse`. FastAPI serializes both, but the return types are semantically inconsistent, the function signatures are misleading, and any code that tries to use the return values uniformly (e.g., in tests or middleware that inspect response objects before they are serialized) will behave differently depending on which function was called.

### 2.7 Cache locking and stale-entry invalidation (positive finding) — CONFIRMED

```python
# server/app/cache.py:90–111
def load_repository_cache_entry(...):
    with _exclusive_lock(index_path):
        index = _load_cache_index(index_path)
        payload = index["entries"].get(cache_key)
        if payload is None:
            return None

        entry = RepositoryCacheEntry(**payload)
        cached_repo_path = project_root / entry.local_repo_path
        if not cached_repo_path.exists() or not cached_repo_path.is_dir():
            del index["entries"][cache_key]
            _write_cache_index(index_path, index)
            return None
        ...
```

The locking model is correct. The stale-entry invalidation on missing on-disk path is correct. The use of `os.replace()` for atomic index writes (`_write_cache_index`, line 167) is good practice.

One note the prior audit **did not make**: `fcntl.flock` is POSIX-only and will raise `AttributeError` on Windows. For a Linux/macOS server deployment this is fine, but it should be documented so that developers who attempt local development on Windows are not silently broken.

---

## Part 3 — New Findings (Missed by Prior Audit)

### 3.1 Fine-grained PAT prefix not covered by `redact()` (Medium, Dom/Sylvie)

```python
# server/app/services/llm.py:17
("github_pat", re.compile(r"gh[ps]_[A-Za-z0-9_]{36,}"), "[REDACTED_GITHUB_PAT]"),
```

The pattern `gh[ps]_` matches `ghp_` (classic personal access tokens) and `ghs_` (installation/server tokens). It does **not** match `github_pat_` — the prefix used by GitHub's modern **fine-grained personal access tokens**, introduced 2022. A fine-grained PAT like `github_pat_11ABCDEFG0...` will pass through `redact()` intact and could be emitted in logged error messages.

The design doc (`design-doc.md:192`) explicitly calls out "GitHub tokens (`ghp_*`, `ghs_*`)" — so even by the spec's own scope, `github_pat_` is not covered. If the team migrates to fine-grained PATs (recommended for least-privilege scoping), any clone failure error message will leak the credential.

**Remediation:** Add `("github_pat_fg", re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "[REDACTED_GITHUB_PAT]")` to `_PATTERNS` in `llm.py`.

---

### 3.2 `EvaluationService` TODO comment contains a false premise (Low, Sylvie)

```typescript
// client/src/services/evaluation.service.ts:14–15
// TODO: Replace devToken stub with a real token from the auth service once
// POST /api/v1/code-eval/auth/login is implemented (Milestone 2).
```

`POST /api/v1/code-eval/auth/login` **is already implemented in Milestone 1** (`server/app/routers/auth.py:54–78`). This TODO comment's premise — that the login endpoint is pending — is wrong. A developer reading this comment will believe the auth flow is unfinished on the backend when it is not. The correct statement of what is missing is that the Angular client does not yet have a login flow that calls the existing endpoint and stores the resulting token for use in subsequent requests. The comment should be rewritten to accurately describe the frontend work remaining.

---

### 3.3 Unguarded `uuid.UUID()` call in `assignments.py` produces unhandled 500 (Medium, Dom)

The `evaluate_submission` handler wraps `UUID(current_user["sub"])` in a try/except and returns a structured 401. But `assignments.py` does not:

```python
# server/app/routers/assignments.py:57
instructor_id = uuid.UUID(current_user["sub"])
```

No try/except. If a token reaches this line with a non-UUID `sub` (which is exactly what the developer onboarding instructions produce — see §2.3 above), Python raises `ValueError` inside FastAPI's dependency chain, which FastAPI catches and converts to an unstructured **500 Internal Server Error** — not a 401 or a `AUTH_ERROR`. This is a security posture regression: a bad token on the `/assignments` route leaks server internals (FastAPI's default 500 body) instead of returning a standard auth error. The inconsistency also makes client-side error handling harder.

**Remediation:** Wrap `uuid.UUID(current_user["sub"])` in a try/except `ValueError` and raise a 401 `MapleAPIError` (matching the pattern at `main.py:479–486`), or extract a shared helper function that both handlers call.

---

### 3.4 `str(None)` serialization defect in `GET /submissions/{id}` response (Low, Dom)

```python
# server/app/routers/submissions.py:74–75
data = {
    "submission_id": str(submission.id),
    "assignment_id": str(submission.assignment_id),
    ...
}
```

`submission.assignment_id` is nullable (`alembic:60`: `sa.Column("assignment_id", sa.Uuid(), nullable=True)`). When a submission was created without an assignment ID, `submission.assignment_id` is `None`. Python's `str(None)` returns the string `"None"` — so the JSON response contains `"assignment_id": "None"` (a string) rather than `"assignment_id": null` (JSON null).

A client parsing this response and attempting `uuid.UUID(response.data.assignment_id)` will raise `ValueError` on the string `"None"`. The Angular client's `SubmissionData` type treats `assignment_id` as a string, so it will render the string `"None"` in the UI rather than the intended null display. The submit-page's response (`SubmissionResponse`) correctly passes `assignment_id` through from the form field, but the round-trip from `GET /submissions/{id}` is broken for unassigned submissions.

**Remediation:** Change line 75 to `"assignment_id": str(submission.assignment_id) if submission.assignment_id else None`.

---

### 3.5 Role-check casing inconsistency between `_can_view_submission` and `require_role` (Low, Dom)

```python
# server/app/routers/submissions.py:17–18
def _can_view_submission(submission: Submission, current_user: dict) -> bool:
    role = str(current_user.get("role", "")).strip().lower()
    ...
    if role == "admin":          # case-insensitive: "Admin", "ADMIN", "admin" all pass
        return True
    if role == "instructor" ...: # case-insensitive
        ...
```

```python
# server/app/middleware/auth.py:82
if current_user.get("role") != required_role:  # exact string match — case-sensitive
    raise HTTPException(status_code=403, ...)
```

`_can_view_submission` normalizes with `.lower()`, so `"Admin"` and `"admin"` are both accepted. `require_role("admin")` does an exact match, so a user registered with role `"Admin"` (the default casing from `auth.py:18` — `role: str = "Student"` — which stores whatever case the caller sends) would pass `_can_view_submission` but fail `require_role("admin")`.

The practical impact depends on whether the team uses `"admin"` or `"Admin"` as the canonical admin role string. The auth router default is `"Student"` (capital S). If `"Admin"` is also capitalized in canonical usage, then `require_role("admin")` will deny legitimate admins on any future protected route. The inconsistency should be resolved by picking a canonical casing and enforcing it at registration time.

---

### 3.6 Defense-in-depth double-redaction in `clone_repository` (Positive observation, missed)

```python
# server/app/main.py:228–231
sanitized_stderr = redact(
    stderr.decode("utf-8", errors="replace")
).replace(github_pat, "[REDACTED]").strip()
```

After calling `redact()` (regex-based), the code applies a second `.replace(github_pat, "[REDACTED]")` using the literal PAT string. This is good security engineering: even if the PAT format is non-standard and evades the regex pattern (e.g., a future fine-grained `github_pat_` token — see §3.1), the literal substitution catches it. The prior audit noted `redact()` on clone stderr but missed the additional explicit literal redaction. This is worth documenting as an intentional defense-in-depth measure so it is not removed as "redundant" during refactoring.

---

### 3.7 `assignment_id` is optional in `evaluate` but the design doc says required (Low, Sylvie + Dom)

```python
# server/app/main.py:434
assignment_id: str | None = Form(default=None),
```

```
# docs/design-doc.md:122
assignment_id (string, required) — the assignment UUID
```

The implementation accepts `assignment_id` as optional (tests confirm this: `assignment_id=None` is a valid call path). The design doc marks it required. This is either an undocumented API relaxation (reasonable for M1 where students may not always have a pre-created assignment) or a design doc error. Either way, the discrepancy creates a contract ambiguity: clients reading the spec will always send the field; clients reading the code may omit it. The correct state of the API should be decided and both documents should agree.

---

## Part 4 — Updated Gap Table

| Severity | Owner(s) | Finding | Status vs Prior Audit |
|----------|----------|---------|----------------------|
| **High** | **Sylvie** (Angular env + docs); **Dom** (token contract) | Dev onboarding comment instructs `sub: 'dev'` which is not a valid UUID; evaluate returns 401 `AUTH_ERROR` (not `AUTHENTICATION_ERROR` as prior audit stated) | **CONFIRMED** — error code corrected |
| **High** | **Dom** | Unauthenticated `POST /rubrics` — no `get_current_user` dependency | **CONFIRMED** |
| **High** | **Dom** | Open role registration — `RegisterRequest.role` accepts any string including `"admin"` | **CONFIRMED** |
| **RETRACTED** | ~~Sylvie + Dom~~ | ~~Integration tests use invalid UUID stubs and wrong assertions~~ | **FALSE — tests are correct and comprehensive** |
| **Medium** | **Dom** | `resolve_repository_head_commit_hash` does not distinguish rate-limit 403 from access 403 — returns `VALIDATION_ERROR` for rate-limit exhaustion on the commits API | **NEW (missed by prior audit)** |
| **Medium** | **Dom** | Unguarded `uuid.UUID(current_user["sub"])` in `assignments.py` — produces unhandled 500 instead of 401 when sub is non-UUID | **NEW (missed by prior audit)** |
| **Medium** | **Sylvie** | Status page HTML claims `GET /submissions/:id` is "pending backend implementation" — it is implemented | **CONFIRMED** |
| **Medium** | **Sylvie** | Status polling page not implemented; hard-nav to `/status/<uuid>` shows empty state | **CONFIRMED** |
| **Medium** | **Sylvie** (env docs); **Jayden** (prod) | `devToken: ''` in `environment.prod.ts` sends `Authorization: Bearer ` (empty string) in production | **CONFIRMED** |
| **Medium** | **Dom/Sylvie** | Fine-grained PAT prefix `github_pat_` not matched by `redact()` regex | **NEW (missed by prior audit)** |
| **Low** | **Dom** | `str(None)` serialization defect — `"assignment_id": "None"` returned as string instead of JSON null | **NEW (missed by prior audit)** |
| **Low** | **Dom** | Role-check casing inconsistency — `_can_view_submission` normalizes with `.lower()`, `require_role()` is case-sensitive | **NEW (missed by prior audit)** |
| **Low** | **Dom** | A5 schema shape — implementation diverges from design doc field names; no contract tests | **CONFIRMED** |
| **Low** | **Dom** | Design doc `Rubric.assignment_id` is wrong — DB has no such column | **CONFIRMED** |
| **Low** | **Dom** | `success_response` returns `dict`, `error_response` returns `JSONResponse` — inconsistent return types | **CONFIRMED** |
| **Low** | **Dom** | `rubrics.py` imports `get_db` from `..models` while other routers use `..models.database` | **CORRECTED — prior audit's absolute-import claim was wrong; real issue is import depth inconsistency** |
| **Low** | **Sylvie** | `EvaluationService` TODO claims `auth/login` is not yet implemented — it is | **NEW (missed by prior audit)** |
| **Low** | **Sylvie + Dom** | `assignment_id` is `Optional` in evaluate API but design doc says required | **NEW (missed by prior audit)** |
| **Informational** | **Sylvie** | Milestone checkbox for Angular form + polling remains unchecked in `milestone-01-tasks.md:41` | **CONFIRMED** |
| **Informational** | **Jayden** | `.env.example` PAT placeholder `ghp_xxxxxxxxxxxx` may trigger some secret scanners | **CONFIRMED** |
| **Positive** | **Sylvie** | Double-redaction defense-in-depth on clone stderr (`redact()` + literal `.replace()`) | **NEW (missed by prior audit)** |
| **Positive** | **Dom** | `_can_view_submission` enforces owner/admin/instructor check with selectinload | **CONFIRMED** |
| **Positive** | **Sylvie** | Cache atomic write via `os.replace()`, exclusive lock via `fcntl.flock` | **CONFIRMED** (noting `fcntl` is POSIX-only — undocumented) |

---

## Part 5 — Revised Remediation Priorities

*The numbering below replaces §3 of the prior audit. §3.2 is removed entirely.*

### 5.1 JWT `sub` developer onboarding — correct the comment and the code (High)

**Owner: Sylvie** (Angular env docs); **Dom** (auth contract)

1. Remove or replace the `create_access_token({'sub': 'dev', 'role': 'user'})` command from both `environment.ts:6` and `environment.development.ts.example:3`. The replacement should direct developers to: register a real user via `POST /auth/register`, login via `POST /auth/login`, and paste the returned `access_token`.
2. Rewrite the `EvaluationService` TODO comment (`evaluation.service.ts:14–15`) to accurately state: the backend login endpoint is live; the Angular work remaining is to add a login page/flow that calls it and stores the token.
3. Fix the error code in client-facing documentation: `AUTH_ERROR`, not `AUTHENTICATION_ERROR`, is what the evaluate endpoint returns when UUID parsing fails (`main.py:483`).

**Definition of done:** Fresh clone → register → login → paste token → submit form succeeds. Developer does not need to write Python.

### 5.2 Secure `POST /rubrics` and `POST /auth/register` (High)

**Owner: Dom**

1. Add `Depends(get_current_user)` and a role guard (`require_role("Instructor")` or `require_role("admin")`) to `rubrics.py:48`.
2. Restrict `RegisterRequest.role` to an allowlist — e.g., `Literal["Student"]` for public registration. Instructor/Admin provisioning must go through a separate flow or admin-only endpoint.
3. Decide and document canonical role casing (`"admin"` vs `"Admin"` vs `"ADMIN"`) and enforce it at registration. Align `require_role()` casing with the casing stored in the database.

**Definition of done:** Anonymous `POST /rubrics` returns 401. `POST /auth/register` with `role: "admin"` returns 400 validation error.

### 5.3 Fix unguarded `uuid.UUID()` in assignments router (Medium)

**Owner: Dom**

```python
# server/app/routers/assignments.py:57 — current
instructor_id = uuid.UUID(current_user["sub"])

# proposed fix
try:
    instructor_id = uuid.UUID(current_user["sub"])
except (ValueError, KeyError):
    return error_response(status_code=401, code="AUTH_ERROR",
                          message="Invalid user identity in token.")
```

Consider extracting a shared `extract_user_id(current_user)` helper to keep this logic in one place.

### 5.4 Fix `str(None)` in `GET /submissions/{id}` response (Low → fix before status page wiring)

**Owner: Dom**

```python
# server/app/routers/submissions.py:75 — fix
"assignment_id": str(submission.assignment_id) if submission.assignment_id else None,
```

This must be fixed before Sylvie connects the Angular status page to the API (§5.5), otherwise the Angular client will receive `"None"` as a string for unassigned submissions.

### 5.5 Complete the status page (Medium)

**Owner: Sylvie** (Angular); **Dom** (confirm response shape — depends on §5.4)

1. Fix the stale HTML copy at `status-page.component.html:37` — the GET endpoint is live.
2. Inject `HttpClient` (or reuse `EvaluationService`) into `StatusPageComponent`. On `ngOnInit`, if `this.data` is null, call `GET /api/v1/code-eval/submissions/{this.submissionId}` with the stored bearer token.
3. Add polling via `interval` + `takeWhile` until `status` leaves `"Pending"` or `"Testing"`.
4. Flip the milestone checkbox at `milestone-01-tasks.md:41`.

### 5.6 Extend PAT redaction to cover fine-grained tokens (Medium)

**Owner: Dom** (llm.py is in Dom's LLM service scope); **Sylvie** (ingestion path consumes the PAT)

```python
# server/app/services/llm.py — add to _PATTERNS
("github_pat_fg", re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "[REDACTED_GITHUB_PAT]"),
```

---

## Part 6 — Architecture Observations (Unchanged from Prior Audit)

The prior audit's architectural concern about `main.py` (~627 lines, confirmed) centralizing orchestration is valid and becomes more acute in Milestone 2 when test execution logic must be added. The recommendation to extract a dedicated `EvaluationOrchestrator` service layer stands.

The cache's `fcntl`-based locking, correct on Linux/macOS, should be documented as a POSIX-only dependency. The atomic write via `os.replace()` is correct and should be preserved.

---

## Part 7 — Verification Notes

All files were read directly from the working directory on 2026-04-09. No shell execution was performed. The test file analysis is based on full static review of all 820 lines of `server/tests/test_evaluate_submission_integration.py`. The prior audit's test-related claims were verifiably inconsistent with the file's contents at every cited line.
