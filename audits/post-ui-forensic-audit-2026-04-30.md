# MAPLE A1 — Post-UI Integration Forensic Audit

**Date:** 2026-04-30
**Auditor:** Senior Technical Auditor (forensic traversal)
**Scope:** Full repository, with primary focus on the newly developed Angular UI (untracked + uncommitted) and its alignment with the FastAPI backend at `HEAD = 2ab9c7a` ("M4 audit remediation — restore evaluator, layering, RBAC")
**Branch:** `dev`
**Working tree state:** dirty — UI redesign uncommitted; see [§0](#0-working-tree-state-snapshot)

---

## Executive Summary

The Milestone 4 remediation commit ([2ab9c7a](audits/archive/comprehensive-forensic-audit-2026-04-30.md)) closed the three EXTREME-severity defects that the prior comprehensive audit flagged: `main.py` is restored ([server/app/main.py:1-559](server/app/main.py)), `rate_limit.py` uses a relative import ([server/app/middleware/rate_limit.py:22](server/app/middleware/rate_limit.py#L22)), and `EvaluationResult` now declares `review_status` and `instructor_notes` ([server/app/models/evaluation_result.py:20-23](server/app/models/evaluation_result.py#L20-L23)). The `auth.register` privilege-escalation hole was also closed (role is hardcoded to `"Student"`, [server/app/routers/auth.py:31](server/app/routers/auth.py#L31)) and `ai_passes._invoke_complete` now filters kwargs against the callee signature ([server/app/services/ai_passes.py:168-184](server/app/services/ai_passes.py#L168-L184)). Server tests pass (commit message reports 426 passed, 4 skipped).

The newly developed UI is impressive in scope: a Login page, Dashboard with table/card views and search, an Assignment-creation page, a Submit page with reactive forms and file drop, a Status page with a 5-stage pipeline visualization and a complete review panel, plus a Shell with sidebar and topbar. Two real wired flows already work (Submit → POST /evaluate, Status polling + review).

The remaining defects after subsequent fixes are limited to **three MEDIUM and several LOW/Informational items** — predominantly field-shape mismatches between the wired UI and the backend (`github_url` ↔ `github_repo_url` divergence across endpoints, `rubric_digest` only on POST and not GET, `Submission.assignment_id` ORM `nullable=False` versus `/evaluate` accepting `None`). The Dashboard remains fixture-only (with a clear "Sample data" banner) until the list endpoint lands.

The system is now runnable end-to-end for Login → Submit → Status → Approve. Login is wired against `POST /auth/login` via a real `AuthService`; the `authGuard` gates every protected route; the `authInterceptor` attaches the stored JWT to every outbound request. The Submit + Status flow survives an instructor approval or rejection without the post-action shape incoherence: both `GET /submissions/{id}` and `POST /submissions/{id}/review` now go through a shared `_serialize_submission` helper.

---

## 0. Working-tree State Snapshot

```
D  audit/milestone-03-audit-2026-04-19.md   # tracked deletes (folder renamed → audits/archive/)
D  audit/milestone-04-audit-2026-04-30.md
D  audit/written-reflection.md
M  client/package-lock.json                  # +18/−18 (no functional change)
M  client/src/app/app.routes.ts              # +18/−3 routes for shell + login + dashboard + assignment
M  client/src/index.html                     # icon sprite, fonts
M  client/src/styles.scss                    # +589 lines design system
M  client/src/services/evaluation.service.ts # devToken nullish coalescing
M  client/src/pages/submit-page/*            # reactive forms, file drop validators
M  client/src/pages/status-page/*            # pipeline stages, review panel
M  client/src/components/criteria-scores/*   # major rewrite (presentation-only)
M  client/src/components/diff-viewer/*       # major rewrite (parses unified diffs)
?? audits/archive/comprehensive-forensic-audit-2026-04-30.md  # prior audit
?? audits/archive/milestone-03-audit-2026-04-19.md
?? audits/archive/milestone-04-audit-2026-04-30.md
?? audits/archive/ui-spec-audit.md
?? client/src/components/shell/              # NEW — sidebar + topbar
?? client/src/pages/assignment-page/         # NEW — instructor assignment creation
?? client/src/pages/dashboard-page/          # NEW — submission table, fixture-only
?? client/src/pages/login-page/              # NEW — sign-in form, no API call
?? docs/post-ui-integration-gaps.md          # gap doc co-authored with this UI work
?? docs/written-reflection.md                # moved from audit/ (deleted there)
?? prompts/dev/sylvie/mockup-prompt.md       # design-prompt provenance
```

**Implication.** The UI work is real, substantive, and unstaged. None of the four new page directories nor the shell are committed. Five of the six modified files have non-trivial diffs (>40 lines). The audit folder rename is a separate concern that should be reconciled in a small commit.

---

## 1. Feature Synthesis & Modular Architecture

### 1.1 Inventory of UI features and backend wiring status

| Feature | Status | UI evidence | Backend evidence |
|---|---|---|---|
| Login form (email + password) | **Wired** | [login-page.component.ts](client/src/pages/login-page/login-page.component.ts), [auth.service.ts](client/src/services/auth.service.ts) | `POST /auth/login` ([auth.py:53-77](server/app/routers/auth.py#L53-L77)) |
| Dashboard table + filter + search | **Fixture-only (banner-flagged)** | [dashboard-page.component.ts:122-132](client/src/pages/dashboard-page/dashboard-page.component.ts#L122-L132) | No `GET /submissions` list endpoint exists (D1 in [post-ui-integration-gaps.md](docs/post-ui-integration-gaps.md)) |
| Assignment creation form | **Wired** | [assignment-page.component.ts](client/src/pages/assignment-page/assignment-page.component.ts), [assignment.service.ts](client/src/services/assignment.service.ts) | `POST /assignments` ([assignments.py:40-69](server/app/routers/assignments.py#L40-L69)) |
| Submit form (GitHub URL + assignment + rubric file) | **Wired** | [submit-page.component.ts:54-78](client/src/pages/submit-page/submit-page.component.ts#L54-L78) | `POST /evaluate` ([main.py:334-554](server/app/main.py#L334-L554)) |
| Status polling (3s interval) | **Wired** | [status-page.component.ts:62-67](client/src/pages/status-page/status-page.component.ts#L62-L67) | `GET /submissions/{id}` ([submissions.py:43-137](server/app/routers/submissions.py#L43-L137)) |
| Pipeline-stage visualization | **Presentation-only** | [status-page.component.ts:150-180](client/src/pages/status-page/status-page.component.ts#L150-L180) | Stages computed from `status` string |
| Criteria-scores panel | **Wired** | [criteria-scores.component.ts](client/src/components/criteria-scores/criteria-scores.component.ts) | `evaluation.ai_feedback.criteria_scores` |
| Diff viewer (parses unified diffs) | **Wired** | [diff-viewer.component.ts](client/src/components/diff-viewer/diff-viewer.component.ts) | `evaluation.ai_feedback.recommendations[].diff` |
| Instructor approve | **Wired** | [status-page.component.ts:192,200-215](client/src/pages/status-page/status-page.component.ts#L192) | `POST /submissions/{id}/review` ([submissions.py:140-212](server/app/routers/submissions.py#L140-L212)) |
| Instructor reject (with notes) | **Wired** | [status-page.component.ts:196-198](client/src/pages/status-page/status-page.component.ts#L196-L198) | `POST /submissions/{id}/review` with `instructor_notes` |
| Shell sidebar + nav | **Wired (RouterLink)** | [shell.component.ts](client/src/components/shell/shell.component.ts) | n/a |
| Logout | **Wired** — clears stored JWT, navigates to `/login` | [shell.component.ts:24-27](client/src/components/shell/shell.component.ts#L24-L27) | n/a |

### 1.2 Module dependency map (post-UI)

```
Browser (Angular SPA)
  ├─ ShellComponent (RouterOutlet, RouterLink) ─ canActivate: authGuard ─►
  │    ├─ DashboardPageComponent ─► fixture data (banner-flagged); navigates to /status/:id with statusData injected via history.state
  │    ├─ SubmitPageComponent (Reactive forms) ─► EvaluationService.submitEvaluation
  │    ├─ StatusPageComponent (polling 3s) ─► EvaluationService.{getSubmissionStatus, submitReview}
  │    └─ AssignmentPageComponent (template forms) ─► AssignmentService.create
  │
  └─ LoginPageComponent (Reactive forms) ─► AuthService.login ─► token stored, navigate('/dashboard')

AuthService (localStorage 'mapleAccessToken') + authInterceptor
  └─ HttpClient (every request gets Authorization: Bearer <stored-token>)
        ├─ POST /api/v1/code-eval/auth/login                   ─► auth.login ─► JWT
        ├─ POST /api/v1/code-eval/evaluate (multipart)         ─► main.evaluate_submission ─► cache + preprocessing + run_pipeline
        ├─ GET  /api/v1/code-eval/submissions/{id}             ─► submissions.get_submission ─► _serialize_submission
        ├─ POST /api/v1/code-eval/submissions/{id}/review      ─► submissions.review_submission ─► _serialize_submission (same shape)
        └─ POST /api/v1/code-eval/assignments                  ─► assignments.create ─► require_role("Instructor")

Backend (FastAPI on uvicorn)
  ├─ CORSMiddleware                  (cors_origins_list, prod-locked validator)
  ├─ SlowAPIMiddleware (slowapi)     (30/min default; 5/min on /evaluate; disabled in tests/env)
  ├─ Routers: auth + assignments + rubrics + submissions  (all under /api/v1/code-eval)
  └─ async pipeline (asyncio.create_task(run_pipeline(...))) ─► docker_client + AI passes + RAG + scoring + review_flags
```

### 1.3 Notable architectural strengths

- **Standard envelope adopted everywhere.** Every router response and the `EvaluationService` error path produce `{success, data, error, metadata}` ([utils/responses.py](server/app/utils/responses.py); [evaluation.service.ts:38-49](client/src/services/evaluation.service.ts#L38-L49); [api.types.ts:101-106](client/src/utils/api.types.ts#L101-L106)).
- **Sensitive-feedback redaction.** `GET /submissions/{id}` withholds `ai_feedback` unless the viewer is privileged or `review_status == "approved"` ([submissions.py:117-133](server/app/routers/submissions.py#L117-L133)). This is the right default; the AI feedback never leaks to a student before instructor approval.
- **Pipeline-stage abstraction.** The status page derives a presentation-grade pipeline tree purely from a single `status` string ([status-page.component.ts:150-180](client/src/pages/status-page/status-page.component.ts#L150-L180)). It is robust to backend status renames as long as the canonical names match `Pending | Cloned | Cached | Testing | Evaluating | Awaiting Review | Completed | Failed | EVALUATION_FAILED`.
- **Rate limiting + test bypass.** `install_rate_limiting` ([rate_limit.py:47-56](server/app/middleware/rate_limit.py#L47-L56)) keeps decorators valid in tests but disables enforcement, so production hardening doesn't add CI flakiness.
- **Polling correctness.** `TERMINAL_STATUSES` halts polling on `{Completed, Failed, Awaiting Review, Rejected, EVALUATION_FAILED}` ([status-page.component.ts:14](client/src/pages/status-page/status-page.component.ts#L14)) and `pollError` halts polling on transport failure ([status-page.component.ts:79-82](client/src/pages/status-page/status-page.component.ts#L79-L82)).
- **Reactive forms for the submit path.** `SubmitPageComponent` uses `FormGroup` with Validators, including a regex for GitHub URL and another for UUID assignment IDs ([submit-page.component.ts:16-26](client/src/pages/submit-page/submit-page.component.ts#L16-L26)). Errors are surfaced through `touched && invalid` getters.

---

## 2. Ambiguities, Predictive Errors, & Interface Mismatches

### 2.1 Medium/Low table

| Severity | Error Cause | Error Explanation | Origin Location(s) |
|:---|:---|:---|:---|
| **Medium** | `github_url` (POST /evaluate response) ↔ `github_repo_url` (GET /submissions/{id} response) divergence. | `SubmissionData.github_url` ([api.types.ts:3](client/src/utils/api.types.ts#L3)) carries the same value as `SubmissionStatusData.github_repo_url` ([api.types.ts:77](client/src/utils/api.types.ts#L77)). The DB column is `github_repo_url` ([models/submission.py:20](server/app/models/submission.py#L20)). The backend deliberately translates one to the other on the POST response ([main.py:466,547](server/app/main.py#L466)). The status page reads `data?.github_url` (from `history.state.data`) AND `statusData?.github_repo_url` (from polling) — and currently the template binds to whichever is non-null. This works today, but any future code that needs to display the URL from one shape must branch on which key is present. | [client/src/utils/api.types.ts:3,77](client/src/utils/api.types.ts#L3) |
| **Medium** | `rubric_digest` only on POST /evaluate response, not on GET /submissions/{id}. | `SubmissionData.rubric_digest: string` ([api.types.ts:5](client/src/utils/api.types.ts#L5)) but `SubmissionStatusData` has no such field ([api.types.ts:73-82](client/src/utils/api.types.ts#L73-L82)) and the GET response builder ([submissions.py:43-105](server/app/routers/submissions.py#L43-L105)) does not include it. A direct link to `/status/:id` (no `history.state.data` populated) leaves any UI panel that reads `data?.rubric_digest` blank. The status template currently shows it via `data?.rubric_digest` (only available for the just-submitted path), not `statusData?.rubric_digest` (always null). | [server/app/routers/submissions.py:43-105](server/app/routers/submissions.py#L43-L105), [client/src/utils/api.types.ts:73-82](client/src/utils/api.types.ts#L73-L82) |
| **Medium** | `Submission.assignment_id` declared NOT NULL in ORM but `/evaluate` allows it null. | `models/submission.py:14-16` declares `assignment_id` as `nullable=False`. `main.py:339,393-410` accepts `assignment_id: str | None = Form(default=None)` and passes `parsed_assignment_id=None` to `create_submission` ([main.py:441-447](server/app/main.py#L441-L447)) when omitted. `Submission(assignment_id=None)` would fail the NOT NULL constraint at commit. The frontend submit form requires it ([submit-page.component.ts:25-28](client/src/pages/submit-page/submit-page.component.ts#L25-L28)) and the SPA never triggers this path, but the API contract is incoherent for any non-SPA caller. | [server/app/models/submission.py:14-16](server/app/models/submission.py#L14-L16), [server/app/main.py:339,441-447](server/app/main.py#L339) |
| **Low** | Hardcoded UUIDs in dashboard and submit-page surfaces. | The dashboard's empty-state "Copy assignment ID" button writes the literal UUID `11111111-2222-3333-4444-555555555555` ([dashboard-page.component.ts:148](client/src/pages/dashboard-page/dashboard-page.component.ts#L148)) and the page header shows `Assignment 11111111` ([dashboard-page.component.html:15](client/src/pages/dashboard-page/dashboard-page.component.html#L15)). The submit-page placeholder also embeds the same fake UUID ([submit-page.component.html:105](client/src/pages/submit-page/submit-page.component.html#L105)). None of these affect runtime behavior, but they are demo-grade artifacts that should be removed before pilot. | [client/src/pages/dashboard-page/dashboard-page.component.ts:148](client/src/pages/dashboard-page/dashboard-page.component.ts#L148), [client/src/pages/submit-page/submit-page.component.html:105](client/src/pages/submit-page/submit-page.component.html#L105) |
| **Low** | Shell still renders hardcoded "Dr. Elena Marsh" in the template. | `ShellComponent` exposes `currentUserEmail` and `currentUserRole` getters derived from JWT claims ([shell.component.ts:16-22](client/src/components/shell/shell.component.ts#L16-L22)), but the sidebar template still hardcodes "Dr. Elena Marsh" / "EM" / "Instructor" ([shell.component.html:26-29](client/src/components/shell/shell.component.html#L26-L29)). Any deployed build shows the same user identity to every visitor. Trivial fix: bind the template to the existing getters. | [client/src/components/shell/shell.component.html:26-29](client/src/components/shell/shell.component.html#L26-L29) |
| **Low** | Avatar tints (`AVATAR_TINTS` 8-element OKLCH palette) are client-side only. | The dashboard fixture assigns `tint: 0..7` per student ([dashboard-page.component.ts:22-31,123-132](client/src/pages/dashboard-page/dashboard-page.component.ts#L22-L31)). The backend has no `tint` (or any avatar metadata) field. Once D1 (real `GET /submissions`) lands, the dashboard component will need a deterministic tint derivation (e.g. `hash(student_id) % 8`) — otherwise tints flicker as the list refreshes. | [client/src/pages/dashboard-page/dashboard-page.component.ts:22-31](client/src/pages/dashboard-page/dashboard-page.component.ts#L22-L31) |
| **Low** | `audit/written-reflection.md` deletion not yet committed. | Tracked file shown deleted in `git status`; the replacement is untracked at `docs/written-reflection.md`. The same is true of `audit/milestone-03-audit-2026-04-19.md` and `audit/milestone-04-audit-2026-04-30.md` (deleted; archived under `audits/archive/`). Trivial reconciliation. | working tree |
| **Informational** | `ResponseMetadata.module === "a1"` and `version === "1.0.0"` are hardcoded. | `APP_VERSION = "1.0.0"` ([main.py:44](server/app/main.py#L44)); the frontend types tag `module: 'a1'` per error envelope ([evaluation.service.ts:39-43](client/src/services/evaluation.service.ts#L39-L43)). Acceptable for the pilot, but a CI step that bumps version on tag would be helpful. | [server/app/main.py:44](server/app/main.py#L44), [client/src/services/evaluation.service.ts:39-43](client/src/services/evaluation.service.ts#L39-L43) |
| **Informational** | Status-page `studentLabel` only flows from Submit and Dashboard navigations via `history.state`. | Any direct link to `/status/:id` shows no student name in the breadcrumb. Acceptable today; revisit when the dashboard list endpoint lands. | [client/src/pages/status-page/status-page.component.ts:55-57](client/src/pages/status-page/status-page.component.ts#L55-L57) |

---

## 3. Ambiguity Resolution & Action Plan

### 3.1 MEDIUM batch — UI/API field reconciliation

| ID | Action | Definition of Done |
|---|---|---|
| 3.1.A | Resolve `assignment_id NOT NULL` vs. `evaluate(assignment_id=None)` mismatch. Choose one: either make the column nullable (preferred for the cache-only path), or require `assignment_id` on `/evaluate` and remove the `default=None`. Update `Submission` ORM and add an Alembic migration if making nullable. | Pydantic + SQLAlchemy + OpenAPI all agree. |
| 3.1.B | Add `rubric_digest` to `GET /submissions/{id}` response and `SubmissionStatusData` interface. | Direct-link `/status/:id` shows the correct digest. |
| 3.1.C | Decide a single canonical name (`github_url` vs. `github_repo_url`) and align both endpoints. Recommendation: keep DB column `github_repo_url`, return `github_url` in both responses. | One name across both endpoint shapes; types stop branching. |

### 3.2 LOW / Informational batch

- Extract `AVATAR_TINTS` into a shared util and derive tint from `hash(student_id) % AVATAR_TINTS.length` so dashboard refreshes don't flicker (post-D1).
- Remove hardcoded UUIDs from `dashboard-page.component.ts:148`, `dashboard-page.component.html:15`, and the submit-page placeholder at `submit-page.component.html:105`.
- Replace the static "Dr. Elena Marsh" user card in the Shell template with a binding to the existing `currentUserEmail` / `currentUserRole` getters on `ShellComponent`.
- Reconcile the `audit/` → `audits/archive/` move in a small commit.

---

## 4. Security & Vulnerability Assessment

### 4.1 Authentication & authorization

- ✅ **JWT signing** uses `HS256` with `settings.SECRET_KEY` ([utils/security.py](server/app/utils/security.py)). `.env.example` ships `SECRET_KEY=changeme`, but the deployment runbook ([docs/deployment.md](docs/deployment.md)) documents rotation. **Recommend** adding a startup-time check:
  ```python
  if settings.APP_ENV == "production" and settings.SECRET_KEY in {"changeme", ""}:
      raise ValueError("SECRET_KEY must be rotated in production.")
  ```
- ✅ **`require_role` is case-insensitive** ([middleware/auth.py:82](server/app/middleware/auth.py#L82)). Confirmed.
- ✅ **`auth.register` no longer accepts `role` from the request body** ([auth.py:31](server/app/routers/auth.py#L31)). Privilege escalation hole closed by the M4 remediation.
- ✅ **`POST /assignments` requires Instructor** ([assignments.py:44](server/app/routers/assignments.py#L44)). `POST /rubrics` requires Instructor (per the prior audit and the M4 commit message). `POST /submissions/{id}/review` requires Instructor + ownership ([submissions.py:155,181](server/app/routers/submissions.py#L155)).
- ✅ **`User.password_hash` column and ORM mapping in place** ([alembic/versions/20260430002_add_password_hash_to_users.py](alembic/versions/20260430002_add_password_hash_to_users.py), [server/app/models/user.py:15](server/app/models/user.py#L15)); auth tests cover register and login ([server/tests/test_auth_router.py](server/tests/test_auth_router.py)).
- ✅ **Frontend `authGuard` gates every protected route** ([client/src/guards/auth.guard.ts](client/src/guards/auth.guard.ts), [app.routes.ts:13-23](client/src/app/app.routes.ts#L13-L23)); `authInterceptor` attaches the stored JWT to every outbound request ([client/src/interceptors/auth.interceptor.ts](client/src/interceptors/auth.interceptor.ts)).
- ⚠️ **`devToken` mechanism leaks easily.** `environment.development.ts.example` documents the procedure to bake a local JWT into the bundle. If a developer accidentally checks in a real `environment.development.ts` (gitignored, but git history is unforgiving), the token is exposed. Mitigation: M4.A.3 gitignore secrets guard ([git pre-commit hook](.gitignore)) — verify the hook scans for `eyJ` JWT prefixes too.

### 4.2 Code injection & sandboxing

- ✅ **Docker container** runs `network_disabled=True`, `cap_drop=["ALL"]`, `read_only=True`, `security_opt=["no-new-privileges:true"]`, 256MB RAM cap, 30s timeout ([docker_client.py:62-114](server/app/services/docker_client.py)). Strong defense.
- ✅ **`redact()`** strips PATs, emails, uppercase env-style assignments before any LLM call ([llm.py:37-44](server/app/services/llm.py)). Confirmed pattern coverage.
- ✅ **`clone_repository`** lives in `git_ingest.py` (extracted in M4 remediation) and inserts the PAT into the URL via `quote()`-encoded credentials. **Verify** in code review that the PAT is never echoed to logs (audit pattern: any `subprocess.run` with the auth URL must redirect stderr through the redactor).
- ⚠️ **No size limit on the rubric upload.** `await rubric.read()` ([main.py:361](server/app/main.py#L361)) loads the entire upload into memory. A 1GB rubric would OOM the worker. Recommend adding `MAX_RUBRIC_BYTES = 256 * 1024` and a `Content-Length` pre-check.
- ⚠️ **No size limit on cloned repo.** `git_ingest.clone_repository` does not bound the resulting checkout. A 5GB student repo could fill the 4GB Droplet disk. Recommend `--depth 1` (likely already set; verify) and a `du -sh` clamp.
- ⚠️ **GitHub URL regex coupling.** Frontend regex ([submit-page.component.ts:20](client/src/pages/submit-page/submit-page.component.ts#L20)) allows `https://(www\.)?github\.com/<owner>/<repo>(/)?`. Backend uses `parse_github_repo_url` ([main.py:90-110](server/app/main.py#L90-L110)) which accepts `github.com` and `www.github.com` but does not require trailing slash. Mostly aligned; verify `.git` suffix handling is consistent (backend strips it; frontend regex doesn't allow it).

### 4.3 Input validation

- ✅ Rubric is validated as UTF-8 with explicit 400 ([main.py:362-369](server/app/main.py#L362-L369)).
- ✅ Rubric JSON parse failure falls back to text ([main.py:370-373](server/app/main.py#L370-L373)) — acceptable.
- ✅ `assignment_id` parsed as UUID with explicit 400 ([main.py:393-402](server/app/main.py#L393-L402)).
- ✅ **Submit-page `studentId`** now has `Validators.maxLength(120)` ([submit-page.component.ts:20](client/src/pages/submit-page/submit-page.component.ts#L20)).
- ⚠️ **`override_notes` (instructor reject notes)** has no client-side or server-side size limit. An instructor could paste a 1MB note into the JSON body. SQLAlchemy `Text` accepts it; pgsql will store it. Recommend a 4KB cap on both client and server.

### 4.4 Logic vulnerabilities

- ✅ **Cross-instructor review hijack** is blocked: `submission.assignment.instructor_id != current_user_id` returns 403 ([submissions.py:181](server/app/routers/submissions.py#L181)).
- ✅ **Student view of own submission** is allowed; admin sees all; instructor sees only assignments they own ([submissions.py:23-40](server/app/routers/submissions.py#L23-L40)).
- ✅ **Sensitive AI feedback redaction** is applied unless viewer is privileged or `review_status == "approved"` ([submissions.py:84-101](server/app/routers/submissions.py#L84-L101)).
- ✅ **Auth/register and auth/login** wired and tested ([server/tests/test_auth_router.py](server/tests/test_auth_router.py)); register hardcodes `role="Student"` to prevent privilege escalation ([auth.py:31](server/app/routers/auth.py#L31)).
- ⚠️ **`Submission.status` is a free-form string** ([models/submission.py:22](server/app/models/submission.py#L22)). No DB-level enum or CHECK. A typo or an unmodeled status would render in the UI as "In Progress" forever (because `displayStatus` defaults unknown statuses through). Recommend a Postgres ENUM after the M4 pilot stabilizes the canonical set.
- ⚠️ **No CSRF protection** on the JSON endpoints. The SPA uses Bearer tokens (which mitigates CSRF), but if a future auth scheme adds cookies, CSRF tokens become essential.

### 4.5 Secrets & dependencies

- ✅ `.env` is gitignored. `.env.example` ships only placeholders.
- ✅ `redact()` strips PATs from any string flowing into the LLM.
- ⚠️ `client/src/environments/environment.prod.ts` is checked in. Currently no secrets — keep it that way.
- Run `npm audit --omit=dev` against `client/package-lock.json` and `pip-audit` against `server/requirements.txt` before pilot.

---

## 5. Efficiency & Optimization Recommendations

### 5.1 Low-risk, high-reward

1. **Polling backoff.** The status page polls every 3 seconds without backoff ([status-page.component.ts:14](client/src/pages/status-page/status-page.component.ts#L14)). For a deadline-bunched pilot, 30 active status pages → 600 GET /submissions/{id} calls/minute. Recommend an exponential-then-capped schedule: 1.5s for the first 10s, 3s for 10–60s, 5s thereafter (still below the 30/min slowapi cap). **Risk: low.** Pure UX win; no backend impact other than load reduction. (Alternative: switch to Server-Sent Events; see 5.3.)
2. ~~Move `Authorization` header to an `HttpInterceptor`.~~ ✅ Done — `authInterceptor` ([client/src/interceptors/auth.interceptor.ts](client/src/interceptors/auth.interceptor.ts)) attaches the header centrally.
3. **Memoize `displayStatus` lookup.** The util module ([client/src/utils/status-display.util.ts](client/src/utils/status-display.util.ts)) builds module-level `IN_PROGRESS` and `ERROR` sets, but the function is still called on every dashboard CD cycle. Marginal cost; consider memoizing if profiles indicate. **Risk: zero.**
4. **Eager-load on `GET /submissions/{id}`.** Already correctly using `selectinload(assignment) + selectinload(evaluation_result)` ([submissions.py:60-61](server/app/routers/submissions.py#L60-L61)). ✅ No action.
5. **Promote `_MAX_CHUNKS_PER_REPO=200` to settings** ([pipeline.py per prior audit](server/app/services/pipeline.py)). Carry-over from the prior audit; still applies.

### 5.2 Recommendations that touch hot paths

6. **Precompute pipeline stages once per `statusData` write.** `pipelineStages` is currently a getter that rebuilds five objects on every change-detection cycle ([status-page.component.ts:159-189](client/src/pages/status-page/status-page.component.ts#L159-L189)). Convert to a cached field updated only when `statusData.status` changes. **Risk: low.** Requires `OnPush` discipline; verify Angular zone behavior.
7. **Fold dashboard `filtered` getter into a pure pipe or signal.** Currently re-runs on every keystroke and every CD cycle ([dashboard-page.component.ts:152-162](client/src/pages/dashboard-page/dashboard-page.component.ts#L152-L162)). Fine for 9 fixture rows; once D1 lands and the list grows to 100s, this becomes a dropped-frame on each keystroke. **Risk: low** — convert to `toSignal(searchQuery$)` + computed signal.

### 5.3 Recommendations with risk

8. **Replace polling with Server-Sent Events.** A single GET /submissions/{id}/events endpoint that streams status transitions would eliminate poll overhead and make pipeline transitions feel instant. **Risk: medium** — adds a new connection model, requires sticky-session-aware deployment, complicates the load-balancer config. **Defer until post-pilot** unless polling load becomes problematic.
9. **Cache decoded JWTs.** `decode_access_token` is called per request via `get_current_user`. For high traffic, `functools.lru_cache(maxsize=1024)` keyed by token string would halve the JWT verification cost. **Risk: medium** — must invalidate on logout (logout is not currently a server-side operation; if a logout endpoint is later added that revokes tokens, the cache must be invalidated). **Defer.**

---

## 6. Conclusion

After the post-audit fixes (password_hash schema + ORM + tests, Alembic merge, `_serialize_submission` extraction, `AuthService` + `authGuard` + `authInterceptor`, login wiring, assignment-page wiring, Reactive Forms + `studentId` relaxation, `Rejected` added to `TERMINAL_STATUSES`, `instructor_notes` on the GET shape, dashboard "Sample data" banner, `displayStatus` util extraction), the system is end-to-end runnable: Login → Dashboard → Submit → Status → Approve/Reject works without manual JWT pasting.

The remaining defects are limited to three MEDIUM contract-shape mismatches (`assignment_id` ORM nullability vs `/evaluate` accepting `None`; `rubric_digest` only on POST; `github_url`/`github_repo_url` divergence) and a handful of LOW/Informational items (residual hardcoded UUIDs in dashboard/submit-page, the `ShellComponent` template still hardcoding "Dr. Elena Marsh" despite the component exposing JWT-derived getters, AVATAR_TINTS client-only derivation, and the uncommitted `audit/` → `audits/archive/` rename).

**Suggested next commit sequence (≤ 1 engineer-hour):**

1. §3.1.A — decide and apply the `assignment_id` nullability resolution.
2. §3.1.B — surface `rubric_digest` on the GET shape.
3. §3.1.C — rename to a single canonical `github_url` field across both endpoint shapes.
4. §3.2 LOW batch — bind the Shell template to `currentUserEmail`/`currentUserRole`; remove the residual hardcoded UUIDs; reconcile the `audit/` directory rename.

Beyond that, the principal scalability concern is the 3-second polling cadence; address it with backoff (§5.1.1) before scaling beyond a single-section pilot.

This audit supersedes [audits/archive/comprehensive-forensic-audit-2026-04-30.md](audits/archive/comprehensive-forensic-audit-2026-04-30.md) (correct on its date against the pre-remediation HEAD) and [audits/archive/ui-spec-audit.md](audits/archive/ui-spec-audit.md) (which captured spec drift). Together with [docs/post-ui-integration-gaps.md](docs/post-ui-integration-gaps.md) — which remains the authoritative work-plan document for the wiring-side items — they form the complete picture as of `HEAD = 2ab9c7a`.
