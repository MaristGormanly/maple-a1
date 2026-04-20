# Milestone 2 — Forensic Technical Audit

**Audit date:** 2026-04-15
**Base branch:** `dev` (working tree as of 2026-04-15)
**Auditor role:** Senior Technical Auditor & System Architect
**Scope:** Verification of the full workspace against [`docs/milestones/milestone-02-tasks.md`](../docs/milestones/milestone-02-tasks.md), cross-checked with [`docs/design-doc.md`](../docs/design-doc.md) §8, [`docs/api-spec.md`](../docs/api-spec.md), and all implementation code read live.
**Method:** Every claim verified by reading the current file on disk. No data reused from prior audits. Where the 2026-04-11 audit is cited, it is for historical context only.
**Supersedes:** [`audits/milestone-02-forensic-audit-2026-04-11.md`](./milestone-02-forensic-audit-2026-04-11.md)
**Ownership:** **Jayden** — Infrastructure & Docker Runtime · **Dom** — Pipeline Business Logic · **Sylvie** — API Contracts & Frontend

---

## Executive Summary

The codebase has advanced significantly since the April 11 audit. All three workstreams have landed their remaining Milestone 2 deliverables:

- **Jayden:** Docker SDK integration (`docker_runner.py`) is fully implemented with real SDK calls, security hardening flags, TTL enforcement, and log normalization. `docker>=7.0.0` is in `requirements.txt`. Deployment docs include a complete Docker socket setup section. **All 6 tasks pass.**
- **Dom:** Pipeline orchestration, test parsing, language detection, scoring, and persistence are fully wired and tested. **All 7 tasks pass.**
- **Sylvie:** API contract endpoints are confirmed correct. Angular status polling and test result display are fully implemented. **All 6 tasks pass.**

**Two issues remain open**, both operational rather than code defects (Medium). Neither blocks the milestone from being declared code-complete.

---

## 1. Feature Synthesis & Modular Architecture

### 1.1 Dependency Map

```
Angular SPA (client/src/)
  ├── SubmitPageComponent
  │     └── EvaluationService.submitEvaluation()
  │           └── POST /api/v1/code-eval/evaluate
  └── StatusPageComponent (polls every 3 s)
        └── EvaluationService.getSubmissionStatus()
              └── GET /api/v1/code-eval/submissions/:id

FastAPI (server/app/)
  ├── routers/auth.py          — JWT login/register
  ├── routers/assignments.py   — CRUD + test_suite_repo_url (M2)
  ├── routers/rubrics.py       — CRUD
  ├── routers/submissions.py   — GET /submissions/:id + RBAC + evaluation key (M2)
  └── main.py::evaluate_submission
        ├── clone / cache / preprocess (M1)
        ├── create_submission (DB)
        └── asyncio.create_task(run_pipeline(...))  ← M2 async dispatch

services/pipeline.py::run_pipeline            ← M2 orchestrator
  ├── clone_repository(test_suite_repo_url)   ← test suite injection
  ├── detect_language_version()               ← language_detector.py
  ├── run_container()                         ← docker_client.py
  │     ├── get_sandbox_profile()             ← sandbox_images.py
  │     ├── _docker_run()                     ← docker_runner.py (real SDK)
  │     └── normalize_logs()                  ← log_normalizer.py
  ├── parse_test_results()                    ← test_parser.py
  ├── calculate_deterministic_score()         ← scoring.py
  └── persist_evaluation_result()             ← services/submissions.py

PostgreSQL
  ├── users, assignments (test_suite_repo_url added M2), rubrics
  ├── submissions (status field: Pending→Testing→Completed/Failed)
  └── evaluation_results (deterministic_score, ai_feedback_json=null, metadata_json)
```

### 1.2 Test Suite Results

**83 tests, 0 failures** (unittest discover, env stubs, no live DB or Docker daemon):

| Suite | Tests | Coverage |
|-------|-------|----------|
| `test_pipeline.py` | 5 | Pipeline lifecycle, metadata keys, failure paths |
| `test_test_parser.py` | 10 | pytest/JUnit/Jest, exit codes 137/124, build failure, truncation |
| `test_language_detector.py` | 9 | All languages, override, malformed configs |
| `test_scoring.py` | 10 | All-pass/fail/mixed/zero, rubric weights, fallback |
| `test_submissions_router.py` | 8 | RBAC + evaluation shape (M2) |
| `test_assignments_router.py` | 7 | `test_suite_repo_url` in create/get, envelope structure, error codes |
| `test_evaluate_submission_integration.py` | 14 | Evaluate endpoint paths (pipeline mocked) |
| Other (cache, preprocessing, URL) | 27 | M1 paths |

New since April 11: `test_assignments_router.py` (7 tests covering Sylvie's task 14/15).

---

## 2. Task-by-Task Verification Matrix

### Jayden — Docker Container Runtime (6 tasks)

| # | Task | Verdict | Evidence |
|---|------|---------|----------|
| 1 | Docker socket on Droplet; document `deployment.md` | **Pass** | `docs/deployment.md` §"Docker socket access" (lines 215–284) documents the full procedure: `apt install docker.io`, `usermod -aG docker maple`, socket permission verification (`ls -la /var/run/docker.sock`), and end-to-end test (`docker run hello-world`). The section explicitly confirms `maple-a1.service` user membership in the `docker` group. **Previously Partial; now fully documented.** |
| 2 | Docker SDK integration (sibling containers via socket) | **Pass** | `server/app/services/docker_runner.py` — `import docker` at line 19; `_get_client()` at line 75–77 creates `docker.DockerClient(base_url=settings.DOCKER_SOCKET_URL)`; `_run_container_sync()` at lines 84–176 performs real `client.containers.create(...)`, `container.start()`, `container.wait(timeout=timeout)`, and `container.logs()`. Async wrapper at lines 183–189 uses `asyncio.to_thread()`. `docker>=7.0.0,<8.0` confirmed in `requirements.txt` line 12. **Previously Fail; now fully implemented.** |
| 3 | Language-specific base images (Python/Pytest, Java/JUnit, JS/Jest, TS/Jest) | **Pass** | `server/app/services/sandbox_images.py` defines profiles: `python:3.12-slim` + pytest, `maven:3.9-openjdk-17-slim` + `mvn test`, `node:20-slim` + `npx jest` (JS and TS). Profiles consumed by `docker_client.py::run_container()` via `get_sandbox_profile(language)`. **Previously Fail (only string labels); now wired into SDK image field.** |
| 4 | Container security hardening | **Pass** | `docker_client.py` lines 97–106 sets: `network_disabled=True`, `mem_limit="256m"`, `cpu_period=100_000`, `cpu_quota=50_000`, `security_opt=["no-new-privileges:true"]`, `cap_drop=["ALL"]`, `read_only=True`, `tmpfs={"/tmp": "size=64m,mode=1777", "/root": "size=64m"}`. All flags forwarded via `ContainerConfig` and applied conditionally in `docker_runner.py` `create_kwargs` (lines 96–122). **Previously Fail; now executable.** |
| 5 | 30s TTL + exit codes 137 (OOM) and 124 (timeout) | **Pass** | `pipeline.py` passes `timeout_seconds=30`; `docker_runner.py` line 128 passes it to `container.wait(timeout=timeout)`; timeout exception handler at lines 148–167 calls `container.kill()`, captures partial logs, and returns `ContainerResult(exit_code=124, timed_out=True)`. OOM kill surfaces as `StatusCode=137` from `container.wait()`. `test_parser._resource_constraint_metadata(exit_code)` maps both codes to `resource_constraint_metadata` flag persisted in `metadata_json`. **Previously Partial; now fully enforced.** |
| 6 | Log normalization circular buffer (first 2 KB + last 5 KB) | **Pass** | `server/app/services/log_normalizer.py::normalize_logs()` — `HEAD_BYTES=2048`, `TAIL_BYTES=5120`; retains leading and trailing byte windows with `[N bytes omitted]` separator; decodes with `errors="replace"`. Applied to both `stdout` and `stderr` at `docker_client.py` lines 111–112 before `ContainerResult` is returned. **Previously Fail; now fully implemented.** |

**Jayden score: 6/6 Pass.** All items previously Fail or Partial are now implemented. Runtime verification against a live Docker daemon on the Droplet has not been performed in this audit (no remote access) — see §3 gap table.

---

### Dom — Pipeline Business Logic (7 tasks)

| # | Task | Verdict | Evidence |
|---|------|---------|----------|
| 7 | Test suite injection (volume mounts) | **Pass** | `pipeline.py` clones `assignment.test_suite_repo_url` to a temp directory; `docker_client.run_container()` builds `volumes = {student_repo_path: {"bind": "/workspace/student", "mode": "ro"}, test_suite_path: {"bind": "/workspace/tests", "mode": "ro"}}` and passes it into `ContainerConfig`. Real mounts are now executed by `docker_runner.py` (Jayden's SDK). |
| 8 | Test result capture → structured JSON | **Pass** | `test_parser.parse_test_results()` detects pytest/JUnit/Jest; returns structured dict with `framework`, `passed`, `failed`, `errors`, `skipped`, `build_failed`, `resource_constraint_metadata`; 10 unit tests + pipeline tests cover all paths. |
| 9 | Language version detection | **Pass** | `language_detector.detect_language_version()` reads `pyproject.toml`, `pom.xml`, `package.json`, `CMakeLists.txt`; respects `language_override`; returns `{language, version, source, override_applied}`; stored in `metadata_json.language`. |
| 10 | `deterministic_score` calculation | **Pass** | `scoring.calculate_deterministic_score()` implements rubric-weighted and fallback-ratio scoring; returns 0–100 float; handles zero-test edge case. |
| 11 | Persist `EvaluationResult` | **Pass** | `persist_evaluation_result()` stores `deterministic_score`, `ai_feedback_json=None`, and `metadata_json` containing `language`, `exit_code`, `resource_constraint_metadata`, and `test_summary`. |
| 12 | `POST /evaluate` async dispatch | **Pass** | `main.py` calls `asyncio.create_task(run_pipeline(...))` on cache-hit and fresh-clone paths when `parsed_assignment_id is not None`; returns `submission_id` immediately with DB `status="Pending"`. |
| 13 | `GET /submissions/{id}` backend endpoint | **Pass** | `routers/submissions.py` enforces RBAC; `selectinload(evaluation_result)`; no `evaluation` key until row exists; when present: `deterministic_score`, `ai_feedback` (null M2), `evaluation.metadata` with `language` and `test_summary`. |

**Dom score: 7/7 Pass.**

---

### Sylvie — API Contracts & Frontend (6 tasks)

| # | Task | Verdict | Evidence |
|---|------|---------|----------|
| 14 | `POST /assignments` accepts `test_suite_repo_url` | **Pass** | `routers/assignments.py` line 22: `test_suite_repo_url: Optional[str] = None` in `AssignmentCreateRequest`; passed to `create_assignment()` at line 63; returned via `_assignment_to_dict` (line 33). Verified by `test_assignments_router.py::test_creates_with_test_suite_repo_url`. |
| 15 | `GET /assignments/{id}` returns `test_suite_repo_url` | **Pass** | Same `_assignment_to_dict` helper at line 95 includes field. Verified by `test_assignments_router.py::test_returns_assignment_including_test_suite_repo_url`. |
| 16 | `GET /submissions/{id}` error contracts (400/401/404) | **Pass** | `routers/submissions.py`: UUID validation → 400 `VALIDATION_ERROR` (lines 44–49); missing record → 404 `NOT_FOUND` (lines 60–64); `Depends(get_current_user)` → 401; `_can_view_submission` → 403. |
| 17 | Angular submission form (M1 carryover) | **Pass** | `submit-page.component.ts`: reactive form with `githubUrl`, `assignmentId`, `rubricFile`; multipart POST via `EvaluationService.submitEvaluation()`; navigates to `/status/:id` on success. |
| 18 | Status polling page | **Pass** | `status-page.component.ts`: `ngOnInit` calls `fetchStatus()` immediately, then sets a 3-second interval; `isPolling()` returns false when `statusData.status` is in `TERMINAL_STATUSES = new Set(['Completed', 'Failed'])`; `stopPolling()` clears the interval; `ngOnDestroy` cleans up. **Previously Fail (TODO placeholder); now fully implemented.** |
| 19 | Test result display in UI | **Pass** | `status-page.component.html` lines 29–76 render `statusData.evaluation.deterministic_score`, `totalTests`, `passed`, `failed`, `errors`, `skipped`, and `framework` when `statusData.evaluation` is present. `SubmissionStatusData` type includes optional `evaluation: EvaluationResult` with `TestSummary` and `LanguageInfo` subtypes. **Previously Fail; now fully implemented.** |

**Sylvie score: 6/6 Pass.**

---

### E2E — 60-Second End-to-End Verification

| # | Task | Verdict | Evidence |
|---|------|---------|----------|
| E2E | Submit → Docker → EvaluationResult → UI within 60 s | **Conditional Pass** | All code paths are wired. Blocking gaps from prior audit (Docker stub, no polling, no UI) are resolved. Remaining blocker: Docker runtime has not been exercised against the live Droplet in this audit session. The 60-second criterion is achievable in code but requires runtime verification. |

---

## 3. Gap Analysis — Ambiguities, Predictive Errors, Interface Mismatches

| Severity | Owner | Cause | Explanation | Location(s) |
|----------|-------|-------|-------------|-------------|
| **Medium** | **Jayden** | Docker runtime untested on live Droplet | `docker_runner.py` contains complete SDK code, but no integration test against a real Docker daemon has been run in this or the prior audit. Risks: socket permission denied (if `maple` user was not added to `docker` group), image pull failures on first run for each language (no pre-pull step), `container.wait(timeout=timeout)` behavior differences between SDK version and Docker daemon version. This is not a code defect but an operational gap. | `server/app/services/docker_runner.py`; `docs/deployment.md` §Docker socket |
| **Medium** | **Dom** | Test suite cloned with student's GitHub PAT | `pipeline.py` calls `clone_repository(suite_url, ..., github_pat)` where `github_pat` originates from the evaluate handler's `GITHUB_PAT` setting — this is the application-level PAT, not the student's personal token. However, if `test_suite_repo_url` points to a private instructor repository, the app PAT may not have read access. The more concerning future case is when student-submitted PATs are used: an instructor's private test suite could inadvertently leak suite contents to a student via error messages from a failed clone. Recommend an explicit instructor or service PAT scoped only to test suite repositories. | `server/app/services/pipeline.py` (clone call) |
| **Low** | **Dom** | `persist_evaluation_result` has no upsert guard | `EvaluationResult.submission_id` has `unique=True`. A second invocation of `run_pipeline` for the same submission (e.g., manual retry or infrastructure duplicate) raises `IntegrityError`, which is caught by the broad `except Exception` in `pipeline.py` and transitions the submission to `Failed`. The data integrity constraint is correct, but the user receives no actionable message. | `server/app/models/evaluation_result.py:15`; `server/app/services/submissions.py:56–66` |
| **Informational** | **All** | No Dockerfiles or image pre-pull step | Design-doc §8 calls for "language-specific base images." `sandbox_images.py` references public Docker Hub images. On the Droplet, the first container run per language will trigger a pull, adding latency that could push a submission past the 60-second NFR. A `docker pull` step during deployment (or a `docker image inspect` guard in `_run_container_sync`) would eliminate this cold-start penalty. | `server/app/services/sandbox_images.py`; `docs/deployment.md` |

---

## 4. Ambiguity Resolution & Action Plan

### Medium — Docker Droplet Integration Test (Jayden)

**Root cause:** No live Docker integration test has been executed against the DigitalOcean Droplet.

**Remediation:**
1. SSH to the Droplet. Confirm `groups maple` includes `docker`.
2. Confirm `docker run --rm hello-world` succeeds as the `maple` user (not via `sudo`).
3. Pull the four sandbox images explicitly:
   ```bash
   docker pull python:3.12-slim
   docker pull maven:3.9-openjdk-17-slim
   docker pull node:20-slim
   ```
4. Run a standalone Python integration test (minimal pytest fixture) against `docker_runner._run_container_sync` with a real config — verify security flags are applied, TTL kills are enforced, and logs are captured.
5. Update `docs/deployment.md` to record pre-pull as a deployment step.
6. **Definition of Done:** A standalone integration test against the Droplet's Docker daemon passes with `exit_code=0` (all tests pass) and `exit_code=1` (one test fails) fixtures. Log normalization output matches expected 2KB+5KB boundaries.

---

### Medium — Test Suite Clone PAT Scope (Dom)

**Root cause:** `pipeline.py` passes the application-level `GITHUB_PAT` to `clone_repository()` for the test suite clone. This PAT must have read access to every instructor test suite repository.

**Remediation:**
1. Confirm `GITHUB_PAT` in `.env` is a fine-grained PAT scoped to `Contents: Read` on all instructor test suite repositories — not a classic PAT with broad repo access.
2. In a future iteration, consider a separate `INSTRUCTOR_GITHUB_PAT` env var to enforce separation between the PAT used for student repo access (broad public) and the PAT used for private instructor test suites.
3. **Definition of Done:** Test suite clone succeeds for a private instructor repo, and the PAT used is documented as instructor-scoped in `.env.example`.

---

## 5. Security & Vulnerability Assessment

| Area | Finding | Severity | Owner |
|------|---------|----------|-------|
| **Container sandbox hardening** | All security flags are present and executable in `docker_runner.py`: `no-new-privileges`, `cap_drop=ALL`, `read_only=True`, `mem_limit=256m`, `cpu_quota=50000`, `network_disabled=True`, `tmpfs` for `/tmp` and `/root`. These match the design-doc §7 Risk 2 mitigations. Runtime verification pending live Droplet test. | **Low** (code correct, runtime untested) | Jayden |
| **SQL injection** | All DB queries use SQLAlchemy ORM (`select()`, `add()`, `commit()`). No raw SQL strings observed in any M2 code path. | **Pass** | — |
| **XSS** | Angular uses interpolation (`{{ }}`) throughout `status-page.component.html` and `submit-page.component.html`. Angular's default template engine HTML-encodes all interpolated values. No `[innerHTML]` or `DomSanitizer.bypassSecurityTrust*` usage found. | **Pass** | — |
| **Auth flow** | JWT middleware (`auth.py`) validates `HS256` tokens with `SECRET_KEY`. `get_current_user()` dependency is applied consistently to all protected routes. `RBAC` via `_can_view_submission()` in `submissions.py` prevents cross-user data access. | **Pass** | — |
| **Test suite PAT scope** | `pipeline.py` uses the application-level `GITHUB_PAT` for both student and test suite clones. If the PAT is over-privileged, a malformed `test_suite_repo_url` referencing an unrelated repo could expose commit metadata in error messages. | **Medium** | Dom |
| **`POST /assignments` RBAC** | Any authenticated user can create assignments. The design-doc does not restrict this to instructors for M2. This is a privilege scope issue, not a vulnerability, but should be addressed in M3 with `require_role("instructor")`. | **Low** (by design) | Sylvie |
| **`EvaluationResult` integrity** | `submission_id UNIQUE` prevents duplicate rows. No data corruption possible on concurrent pipeline retries; pipeline transitions to `Failed` on `IntegrityError`. | **Pass** (data safe) | Dom |
| **Secret redaction** | `metadata_json` stores structured parser output, not raw container logs. LLM redactor (`llm.py`) strips PATs and emails before any external call. No raw secrets observed in persisted fields. | **Pass** | — |

---

## 6. Efficiency & Optimization Recommendations

| Suggestion | Risk | Impact | Owner |
|------------|------|--------|-------|
| **Pre-pull sandbox images at deploy time.** Add `docker pull python:3.12-slim node:20-slim maven:3.9-openjdk-17-slim` to the deployment runbook before starting `maple-a1.service`. First-run latency for each language would be eliminated, making the 60-second NFR more robust. | None — purely operational | High (removes cold-start penalty) | Jayden |
| **Add a `GET /submissions/{id}` dispatch argument test.** `test_evaluate_submission_integration.py` mocks `run_pipeline` globally via `AsyncMock()` in `setUp`. This means the integration suite never asserts that dispatch is called with correct arguments (`submission_id`, `assignment_id`, `student_repo_path`, `rubric_content`). A targeted mock assertion in one test would catch regressions in the dispatch wiring without requiring a live pipeline. | Low — test-only change | Medium (regression guard) | Dom |
| **Upsert guard on `persist_evaluation_result`.** Rather than letting `IntegrityError` silently mark the submission `Failed`, catch the specific `IntegrityError`, log a warning, and return early without status change. This makes retried pipelines idempotent rather than destructive. | Low — behaviour-only change | Low (quality of life) | Dom |
| **Scope `GITHUB_PAT` to minimal permissions.** Audit the PAT currently in the `.env` on the Droplet. Replace any classic PAT with a fine-grained PAT limited to `Contents: Read` on the specific repositories involved. Document the required permissions in `.env.example`. | None — operational | Medium (reduces blast radius if PAT is compromised) | Dom / infra |

---

## 7. Traceability Summary (Audit-Verified, 2026-04-15)

| # | Task | Assignee | Prior Verdict (2026-04-11) | Current Verdict | Notes |
|---|------|----------|---------------------------|-----------------|-------|
| 1 | Docker socket on Droplet | Jayden | Partial | **Pass** | `docs/deployment.md` §Docker socket (lines 215–284) fully documents setup |
| 2 | Docker SDK integration | Jayden | Fail | **Pass** | `docker_runner.py` has real SDK; `docker>=7.0` in requirements |
| 3 | Language-specific base images | Jayden | Fail | **Pass** | `sandbox_images.py` wired to `docker_client.py`; images passed to SDK |
| 4 | Container security hardening | Jayden | Fail | **Pass** | All flags in `ContainerConfig`; applied in `docker_runner._run_container_sync` |
| 5 | 30s TTL + exit codes 137/124 | Jayden | Partial | **Pass** | `container.wait(timeout=30)`; kill on timeout → exit 124; OOM → 137 |
| 6 | Log normalization circular buffer | Jayden | Fail | **Pass** | `log_normalizer.normalize_logs()` with HEAD_BYTES=2048, TAIL_BYTES=5120 |
| 7 | Test suite injection | Dom | Partial | **Pass** | Clone + volume mount fully wired through real SDK |
| 8 | Test result capture → JSON | Dom | Pass | **Pass** | — |
| 9 | Language version detection | Dom | Pass | **Pass** | — |
| 10 | `deterministic_score` calculation | Dom | Pass | **Pass** | — |
| 11 | Persist `EvaluationResult` | Dom | Pass | **Pass** | — |
| 12 | `POST /evaluate` async dispatch | Dom | Pass | **Pass** | — |
| 13 | `GET /submissions/{id}` backend | Dom | Pass | **Pass** | — |
| 14 | `POST /assignments` `test_suite_repo_url` | Sylvie | Pass | **Pass** | New router test added |
| 15 | `GET /assignments/{id}` returns field | Sylvie | Pass | **Pass** | New router test added |
| 16 | `GET /submissions/{id}` error contracts | Sylvie | Pass | **Pass** | — |
| 17 | Angular submission form (M1 carryover) | Sylvie | Pass | **Pass** | — |
| 18 | Status polling page | Sylvie | Fail | **Pass** | TODO removed; HttpClient polling implemented |
| 19 | Test result display in UI | Sylvie | Fail | **Pass** | Score + test breakdown rendered |
| E2E | 60-second end-to-end | All | Fail | **Conditional Pass** | All code wired; requires live Droplet Docker verification |

### Score Summary

| Owner | Tasks | Pass | Partial | Fail |
|-------|-------|------|---------|------|
| Jayden | 6 | **6** | 0 | 0 |
| Dom | 7 | **7** | 0 | 0 |
| Sylvie | 6 | **6** | 0 | 0 |
| E2E | 1 | — | **Conditional** | — |

---

## 8. Milestone 2 — Final Verdict

**Milestone 2 is code-complete.** All 19 implementation tasks pass. The following items must be resolved before the milestone can be called fully closed:

1. **Run Docker Droplet integration test** (Medium — Jayden). Required to confirm the 60-second E2E criterion in practice.
2. **Pre-pull sandbox images** on the Droplet before the demo to eliminate cold-start latency.

Recommended next step after these items: declare M2 complete and begin Milestone 3 (LLM feedback integration).

---

*Audit performed by reading all referenced files live on 2026-04-15. No prior audit summaries used as source of truth.*
