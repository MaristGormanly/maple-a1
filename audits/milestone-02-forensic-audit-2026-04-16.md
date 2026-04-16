# Milestone 2 — Forensic Technical Audit

**Audit date:** 2026-04-16
**Base branch:** `dev` (working tree as of 2026-04-16)
**Auditor role:** Senior Technical Auditor & System Architect
**Scope:** Verification of the full workspace against [`docs/milestones/milestone-02-tasks.md`](../docs/milestones/milestone-02-tasks.md), cross-checked with [`docs/design-doc.md`](../docs/design-doc.md) §8, [`docs/api-spec.md`](../docs/api-spec.md), and all implementation code read live.
**Method:** Every claim verified by reading the current file on disk and running the test suite. No data reused from prior audits. Where earlier audits are cited, it is for historical context only.
**Supersedes:** [`audits/milestone-02-forensic-audit-2026-04-15.md`](./milestone-02-forensic-audit-2026-04-15.md), [`audits/milestone-02-forensic-audit-2026-04-11.md`](./milestone-02-forensic-audit-2026-04-11.md)
**Ownership:** **Jayden** — Infrastructure & Docker Runtime · **Dom** — Pipeline Business Logic · **Sylvie** — API Contracts & Frontend

---

## Executive Summary

All three workstreams have landed their Milestone 2 deliverables. Since the April 15 audit, Dom's follow-up closure plan has been implemented: dispatch argument regression tests, idempotent persistence, and PAT-scope documentation are now in place.

- **Jayden (6/6 Pass):** Docker SDK integration (`docker_runner.py`) is fully implemented with real SDK calls, security hardening flags, TTL enforcement, and log normalization. `docker>=7.0.0` is in `requirements.txt`. Deployment docs include a complete Docker socket setup section.
- **Dom (7/7 Pass + 3 follow-ups closed):** Pipeline orchestration, test parsing, language detection, scoring, and persistence are fully wired and tested. Post-audit follow-ups resolved: dispatch argument regression tests, idempotent `EvaluationResult` persistence (via `DuplicateEvaluationError`), and PAT-scope documentation.
- **Sylvie (6/6 Pass):** API contract endpoints are confirmed correct. Angular status polling and test result display are fully implemented.

**One issue remains open** — operational, not a code defect (Medium). It does not block the milestone from being declared code-complete.

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
        └── DuplicateEvaluationError guard    ← idempotent on IntegrityError

PostgreSQL
  ├── users, assignments (test_suite_repo_url added M2), rubrics
  ├── submissions (status field: Pending→Testing→Completed/Failed)
  └── evaluation_results (deterministic_score, ai_feedback_json=null, metadata_json)
```

### 1.2 Test Suite Results

**147 tests, 0 failures** (unittest discover, env stubs, no live DB or Docker daemon):

| Suite | Tests | Coverage |
|-------|-------|----------|
| `test_pipeline.py` (PipelineTests) | 6 | Pipeline lifecycle, metadata keys, failure paths, duplicate-run idempotency |
| `test_pipeline.py` (PersistEvaluationResultTests) | 2 | `DuplicateEvaluationError` on `IntegrityError`, clean persist path |
| `test_test_parser.py` | 10 | pytest/JUnit/Jest, exit codes 137/124, build failure, truncation |
| `test_language_detector.py` | 9 | All languages, override, malformed configs |
| `test_scoring.py` | 10 | All-pass/fail/mixed/zero, rubric weights, fallback |
| `test_submissions_router.py` | 8 | RBAC + evaluation shape (M2) |
| `test_assignments_router.py` | 8 | `test_suite_repo_url` in create/get, envelope structure, error codes |
| `test_evaluate_submission_integration.py` | 16 | Evaluate endpoint paths, dispatch argument assertions (fresh-clone + cache-hit) |
| `test_docker_client.py` | 10 | Shell command build, run_container config, result conversion, language fallback |
| `test_docker_runner.py` | 8 | SDK delegation, timeout, OOM, volumes, error paths, kill failure |
| `test_log_normalizer.py` | 16 | Head/tail preservation, truncation, multibyte, integration |
| `test_sandbox_images.py` | 17 | Profile lookup, language mapping, frozen profiles, defaults |
| Other (cache, preprocessing, URL parsing) | 27 | M1 paths |

---

## 2. Task-by-Task Verification Matrix

### Jayden — Docker Container Runtime (6 tasks)

| # | Task | Verdict | Evidence |
|---|------|---------|----------|
| 1 | Docker socket on Droplet; document `deployment.md` | **Pass** | `docs/deployment.md` §"Docker socket access" (lines 215–288) documents the full procedure: `apt install docker.io`, `usermod -aG docker maple`, socket permission verification (`ls -la /var/run/docker.sock`), end-to-end test (`docker run hello-world`), and a verification checklist table. The section explicitly confirms `maple-a1.service` user membership in the `docker` group and includes a security note about root-equivalence of `docker` group membership. |
| 2 | Docker SDK integration (sibling containers via socket) | **Pass** | `server/app/services/docker_runner.py` — `import docker` at line 19; `_get_client()` at line 75–77 creates `docker.DockerClient(base_url=settings.DOCKER_SOCKET_URL)`; `_run_container_sync()` at lines 84–176 performs real `client.containers.create(...)`, `container.start()`, `container.wait(timeout=timeout)`, and `container.logs()`. Async wrapper at lines 183–189 uses `asyncio.to_thread()`. `docker>=7.0.0,<8.0` confirmed in `requirements.txt` line 12. Container is ALWAYS removed in the `finally` block (line 171–175). 8 unit tests in `test_docker_runner.py` covering success, timeout, OOM, kill failure, volumes/env, async delegation. |
| 3 | Language-specific base images (Python/Pytest, Java/JUnit, JS/Jest, TS/Jest) | **Pass** | `server/app/services/sandbox_images.py` defines `SANDBOX_PROFILES` dict with `SandboxProfile` frozen dataclass entries: `python:3.12-slim` + `pytest --tb=short -v`, `maven:3.9-openjdk-17-slim` + `mvn test -B`, `node:20-slim` + `npx jest --verbose` (shared by JS and TS). `get_sandbox_profile(language)` at line 62–64 returns profile or falls back to `DEFAULT_PROFILE` (Python). Profiles consumed by `docker_client.py::run_container()` at line 74 via `get_sandbox_profile(language)`. 17 tests in `test_sandbox_images.py` cover all languages, fallback, case-insensitivity, frozen check. |
| 4 | Container security hardening | **Pass** | `docker_client.py` lines 90–107 sets: `network_disabled=True`, `mem_limit="256m"`, `cpu_period=100_000`, `cpu_quota=50_000`, `security_opt=["no-new-privileges:true"]`, `cap_drop=["ALL"]`, `read_only=True`, `tmpfs={"/tmp": "size=64m,mode=1777", "/root": "size=64m"}`. All flags forwarded via `ContainerConfig` dataclass and applied conditionally in `docker_runner.py` `create_kwargs` (lines 96–122). |
| 5 | 30s TTL + exit codes 137 (OOM) and 124 (timeout) | **Pass** | `pipeline.py` line 23 sets `_CONTAINER_TIMEOUT_SECONDS = 30`; passed to `run_container()` at line 64. `docker_runner.py` line 128 passes it to `container.wait(timeout=timeout)`. Timeout exception handler at lines 148–167 calls `container.kill()`, captures partial logs, and returns `ContainerResult(exit_code=124, timed_out=True)`. OOM kill surfaces as `StatusCode=137` from `container.wait()`. `test_parser._resource_constraint_metadata(exit_code)` maps both codes: `137 → {oom_killed: True}`, `124 → {timed_out: True}`. Both are persisted in `metadata_json.resource_constraint_metadata`. Tests: `test_docker_runner.py::test_container_removed_on_wait_timeout`, `test_docker_runner.py::test_oom_kill_returns_exit_code_137`, `test_test_parser.py::test_exit_code_137_oom`, `test_test_parser.py::test_exit_code_124_timeout`. |
| 6 | Log normalization circular buffer (first 2 KB + last 5 KB) | **Pass** | `server/app/services/log_normalizer.py::normalize_logs()` — `HEAD_BYTES=2048`, `TAIL_BYTES=5120`; retains leading and trailing byte windows with `[N bytes omitted]` separator; decodes with `errors="replace"` to guard against mid-character splits. Applied to both `stdout` and `stderr` at `docker_client.py` lines 111–112 before `ContainerResult` is returned to pipeline. 16 tests in `test_log_normalizer.py` covering: empty/single char/short/exactly-at-limit/one-byte-over/large truncation, head/tail preservation, separator, omitted byte count, multibyte safety, integration with `run_container`. |

**Jayden score: 6/6 Pass.**

---

### Dom — Pipeline Business Logic (7 tasks)

| # | Task | Verdict | Evidence |
|---|------|---------|----------|
| 7 | Test suite injection (volume mounts) | **Pass** | `pipeline.py` lines 43–47 reads `assignment.test_suite_repo_url` from the assignment row; line 53 creates a temp directory; line 56 clones the test suite repo into it via `clone_repository()`. `docker_client.run_container()` at lines 76–79 builds `volumes = {student_repo_path: {"bind": "/workspace/student", "mode": "ro"}, test_suite_path: {"bind": "/workspace/tests", "mode": "ro"}}` and passes them into `ContainerConfig`. Real mounts are executed by `docker_runner.py`'s SDK integration. `_build_shell_command()` generates a composite command starting with `cd /workspace/tests` so the test runner executes from the correct working directory. Tests: `test_pipeline.py::test_run_pipeline_success_status_and_persist` verifies clone is called with the test suite URL. |
| 8 | Test result capture → structured JSON | **Pass** | `test_parser.parse_test_results(stdout, stderr, exit_code)` at `test_parser.py` lines 13–69 detects framework in order: pytest → JUnit XML → Jest. Returns structured dict with `framework`, `passed`, `failed`, `errors`, `skipped`, `tests` (individual results), `resource_constraint_metadata`, `raw_output_truncated`. Handles: build failures (via `_BUILD_PATTERNS` heuristic, line 127–130), empty/unrecognized output, exit codes 137/124. Called by `pipeline.py` at line 67. 10 unit tests in `test_test_parser.py` cover all-pass pytest, mixed pytest, JUnit XML, Jest, OOM, timeout, build failure, empty, unrecognized, truncation. |
| 9 | Language version detection | **Pass** | `language_detector.detect_language_version(repo_path, language_override)` at `language_detector.py` lines 16–46 returns `{language, version, source, override_applied}`. Detectors: `_detect_python` (pyproject.toml — `requires-python` and Poetry `tool.poetry.dependencies.python`), `_detect_node` (package.json — devDependencies for TypeScript detection, engines.node for version), `_detect_java` (pom.xml — `properties/java.version`), `_detect_cpp` (CMakeLists.txt — `CMAKE_CXX_STANDARD`). Respects `language_override` (early return at line 21–27). All parsers use `try/except` for malformed files. Called by `pipeline.py` at line 58; result stored in `metadata_json["language"]`. 9 unit tests in `test_language_detector.py` using `TemporaryDirectory` fixtures. |
| 10 | `deterministic_score` calculation | **Pass** | `scoring.calculate_deterministic_score(test_results, rubric_content)` at `scoring.py` lines 9–37 returns 0–100 float. Skipped tests excluded from denominator (line 29 `effective_total = passed + failed + errors`). Zero effective tests → `0.0`. Rubric-weighted scoring via `_weighted_score()` when `criteria` list has at least one `weight` key; maps tests to criteria by case-insensitive substring match on `name`. Falls back to `(passed / effective_total) * 100`. Called by `pipeline.py` at line 68. 10 unit tests in `test_scoring.py`: all-pass, all-fail, mixed, zero tests, all errors, skipped excluded, skipped with failures, rubric-weighted, rubric without weights, string rubric fallback. |
| 11 | Persist `EvaluationResult` | **Pass** | `submissions.persist_evaluation_result()` at `submissions.py` lines 57–90 creates an `EvaluationResult` row with `deterministic_score`, `ai_feedback_json=None`, and `metadata_json`. **Idempotent-safe:** catches `IntegrityError` on commit (line 80), rolls back the session (line 81), and raises `DuplicateEvaluationError` (line 86–88) instead of letting the exception propagate. Caller (`pipeline.py` line 91–96) catches `DuplicateEvaluationError` and logs an info message without transitioning the submission to `Failed`. Model: `EvaluationResult.submission_id` has `unique=True` (line 15 of `evaluation_result.py`). `metadata_json` contains `language`, `exit_code`, `resource_constraint_metadata`, and `test_summary` (pipeline.py lines 70–81). Tests: `test_pipeline.py::PersistEvaluationResultTests` (2 tests) pins the `DuplicateEvaluationError` contract; `test_pipeline.py::test_run_pipeline_stays_completed_on_duplicate_evaluation` verifies no false `Failed` transition. |
| 12 | `POST /evaluate` async dispatch | **Pass** | `main.py` line 38 imports `run_pipeline`. Lines 548–556 (cache-hit path) and 624–632 (fresh-clone path) call `asyncio.create_task(run_pipeline(submission.id, parsed_assignment_id, student_abs, rubric_content, github_pat))` when `parsed_assignment_id is not None`. Submission status is set to `"Pending"` in the DB and HTTP response when an assignment is present (lines 542, 557, 621, 634). Endpoint returns `submission_id` immediately. Tests: `test_evaluate_submission_integration.py::test_evaluate_dispatch_arguments_on_fresh_clone` and `test_evaluate_dispatch_arguments_on_cache_hit` assert all five dispatch arguments (`submission_id`, `assignment_id`, `student_repo_path`, `rubric_content`, `github_pat`). The global `run_pipeline` mock in `setUp` prevents actual pipeline execution during integration tests. |
| 13 | `GET /submissions/{id}` backend endpoint | **Pass** | `routers/submissions.py` lines 36–96: enforces RBAC via `_can_view_submission()` (owner, admin, or instructor of linked assignment); uses `selectinload(Submission.evaluation_result)` for eager loading (line 54). No `evaluation` key in response until `EvaluationResult` row exists (line 83 conditional). When present: `deterministic_score`, `ai_feedback` (null M2), and `evaluation.metadata` with `language` and `test_summary` extracted from `metadata_json` (lines 88–93). Error contracts: UUID validation → 400 `VALIDATION_ERROR` (lines 43–49); missing record → 404 `NOT_FOUND` (lines 60–64); `Depends(get_current_user)` → 401; `_can_view_submission` → 403 `FORBIDDEN` (lines 66–71). 8 tests in `test_submissions_router.py`. |

**Dom score: 7/7 Pass.**

**Dom follow-ups (closed 2026-04-13):**

| Follow-up | Status | Evidence |
|-----------|--------|----------|
| Dispatch argument regression test | **Closed** | `test_evaluate_submission_integration.py`: `test_evaluate_dispatch_arguments_on_fresh_clone` and `test_evaluate_dispatch_arguments_on_cache_hit` assert `submission_id`, `assignment_id`, `student_repo_path`, `rubric_content`, `github_pat` are correctly wired to `run_pipeline`. |
| Idempotent `EvaluationResult` persistence | **Closed** | `submissions.py`: `persist_evaluation_result` catches `IntegrityError` → raises `DuplicateEvaluationError`. `pipeline.py`: catches `DuplicateEvaluationError` before broad `except Exception`, logs info, does not mark `Failed`. `test_pipeline.py`: `test_run_pipeline_stays_completed_on_duplicate_evaluation` and `PersistEvaluationResultTests` (2 tests) pin the contract. |
| PAT-scope documentation | **Closed** | `.env.example` lines 19–28 document minimum scope (`repo`), safe-failure behavior, and recommended ownership. `docs/deployment.md` environment-variable table expanded with scope and failure-safety detail. Clone-failure paths verified safe in code: `pipeline.py` exception handler (lines 97–105) uses `logger.exception` which does not log function arguments; `main.py::clone_repository` (line 231) applies `redact()` and replaces `github_pat` with `[REDACTED]` before building the error message. |

---

### Sylvie — API Contracts & Frontend (6 tasks)

| # | Task | Verdict | Evidence |
|---|------|---------|----------|
| 14 | `POST /assignments` accepts `test_suite_repo_url` | **Pass** | `routers/assignments.py` line 22: `test_suite_repo_url: Optional[str] = None` in `AssignmentCreateRequest`. Passed to `create_assignment()` at line 63. Returned via `_assignment_to_dict` (line 33: `"test_suite_repo_url": a.test_suite_repo_url`). 8 tests in `test_assignments_router.py`: `test_creates_with_test_suite_repo_url`, `test_creates_with_null_test_suite_repo_url`, envelope structure, error codes. |
| 15 | `GET /assignments/{id}` returns `test_suite_repo_url` | **Pass** | Same `_assignment_to_dict` helper at line 95 includes the field. `test_assignments_router.py::test_returns_assignment_including_test_suite_repo_url` verifies. |
| 16 | `GET /submissions/{id}` error contracts (400/401/404) | **Pass** | `routers/submissions.py`: UUID validation → 400 `VALIDATION_ERROR` (lines 43–49); missing record → 404 `NOT_FOUND` (lines 60–64); `Depends(get_current_user)` → 401; `_can_view_submission` → 403. |
| 17 | Angular submission form (M1 carryover) | **Pass** | `submit-page.component.ts` lines 13–66: reactive form with `githubUrl` (required, GitHub URL pattern validator) and `assignmentId` (required); `selectedFile` for rubric upload; multipart POST via `EvaluationService.submitEvaluation()`; navigates to `/status/:id` on success with `state: { data: response.data }`. |
| 18 | Status polling page | **Pass** | `status-page.component.ts` lines 18–98: `ngOnInit` extracts `submissionId` from route params, reads `history.state` for initial data, calls `fetchStatus()` immediately, then sets a 3-second interval (`POLL_INTERVAL_MS = 3000`). `isPolling()` returns false when `statusData.status` is in `TERMINAL_STATUSES = new Set(['Completed', 'Failed'])`. `stopPolling()` clears the interval. `ngOnDestroy` calls `stopPolling()` for cleanup. `fetchStatus()` subscribes to `EvaluationService.getSubmissionStatus()` and stops polling on error or terminal status. |
| 19 | Test result display in UI | **Pass** | `status-page.component.html` lines 29–76: when `statusData.evaluation` is present, renders `deterministic_score` (line 33), `totalTests` (computed getter, line 89–93 of TS), `passed` (line 43), `failed` (line 49, conditional), `errors` (line 54, conditional), `skipped` (line 60, conditional), and `framework` (line 65). `testSummary` getter at TS line 85–87 accesses `statusData.evaluation.metadata.test_summary`. TypeScript types: `SubmissionStatusData` includes optional `evaluation: EvaluationResult` with `TestSummary` and `LanguageInfo` subtypes in `api.types.ts`. AI feedback placeholder at HTML line 69 renders `ai_feedback.summary` when present (null for M2). |

**Sylvie score: 6/6 Pass.**

---

### E2E — 60-Second End-to-End Verification

| # | Task | Verdict | Evidence |
|---|------|---------|----------|
| E2E | Submit → Docker → EvaluationResult → UI within 60 s | **Conditional Pass** | All code paths are wired: Angular form → `POST /evaluate` → `asyncio.create_task(run_pipeline)` → test suite clone → Docker container (real SDK) → parse → score → persist → status update. Angular polls `GET /submissions/{id}` every 3 seconds and renders results when evaluation key appears. Blocking gaps from prior audits (Docker stub, no polling, no UI) are all resolved. Remaining blocker: Docker runtime has not been exercised against the live Droplet in this audit session. The 60-second criterion is achievable in code but requires runtime verification. |

---

## 3. Gap Analysis — Ambiguities, Predictive Errors, Interface Mismatches

| Severity | Owner | Cause | Explanation | Location(s) |
|----------|-------|-------|-------------|-------------|
| **Medium** | **Jayden** | Docker runtime untested on live Droplet | `docker_runner.py` contains complete SDK code, but no integration test against a real Docker daemon has been run in this or prior audits. Risks: socket permission denied (if `maple` user was not added to `docker` group), image pull failures on first run for each language (no pre-pull step), `container.wait(timeout=timeout)` behavior differences between SDK version and Docker daemon version. This is not a code defect but an operational gap. | `server/app/services/docker_runner.py`; `docs/deployment.md` §Docker socket |
| **Medium** | **Dom** | Test suite cloned with application-level GitHub PAT | `pipeline.py` calls `clone_repository(suite_url, ..., github_pat)` where `github_pat` originates from the evaluate handler's `GITHUB_PAT` setting. `.env.example` now documents minimum scope (`repo`) and recommended ownership (service/instructor account). Clone failures remain safe — `pipeline.py` logs the exception, sets submission to `Failed`, and never leaks the PAT in error output (`main.py::clone_repository` applies `redact()` + literal `[REDACTED]` replacement). Still recommend a separate `INSTRUCTOR_GITHUB_PAT` env var in a future iteration. | `server/app/services/pipeline.py`; `.env.example`; `docs/deployment.md` |
| ~~**Low**~~ | ~~**Dom**~~ | ~~`persist_evaluation_result` has no upsert guard~~ | **Resolved (2026-04-13).** `persist_evaluation_result` now catches `IntegrityError`, rolls back, and raises `DuplicateEvaluationError`. `pipeline.py` catches this specific exception and logs an info message without transitioning to `Failed`. Tests in `test_pipeline.py` pin this contract. | `server/app/services/submissions.py`; `server/app/services/pipeline.py` |
| **Informational** | **All** | No Dockerfiles or image pre-pull step | Design-doc §8 calls for "language-specific base images." `sandbox_images.py` references public Docker Hub images. On the Droplet, the first container run per language will trigger a pull, adding latency that could push a submission past the 60-second NFR. A `docker pull` step during deployment would eliminate this cold-start penalty. | `server/app/services/sandbox_images.py`; `docs/deployment.md` |

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

### Medium — Test Suite Clone PAT Scope (Dom) — *Partially Resolved*

**Root cause:** `pipeline.py` passes the application-level `GITHUB_PAT` to `clone_repository()` for the test suite clone.

**Remediation (completed 2026-04-13):**
1. `.env.example` now documents minimum required PAT scope (`repo` — full read for private repos) and recommended ownership (service account or instructor account).
2. `docs/deployment.md` environment-variable table updated with PAT scope requirements and safe-failure behavior.
3. Clone-failure paths verified safe: `pipeline.py` logs exceptions via `logger.exception` (which does not include function arguments like `github_pat`), sets submission to `Failed`, and never exposes credentials in API responses. `main.py::clone_repository` explicitly applies `redact()` and replaces `github_pat` with `[REDACTED]` in error messages (line 231).

**Remaining (deferred to M3):**
- Consider a separate `INSTRUCTOR_GITHUB_PAT` env var to enforce separation between student-repo and test-suite PATs.
- Verify actual PAT on the Droplet is correctly scoped.

---

## 5. Security & Vulnerability Assessment

| Area | Finding | Severity | Owner |
|------|---------|----------|-------|
| **Container sandbox hardening** | All security flags present and executable in `docker_runner.py`: `no-new-privileges`, `cap_drop=ALL`, `read_only=True`, `mem_limit=256m`, `cpu_quota=50000`, `network_disabled=True`, `tmpfs` for `/tmp` and `/root`. These match design-doc §7 Risk 2 mitigations. Runtime verification pending live Droplet test. | **Low** (code correct, runtime untested) | Jayden |
| **SQL injection** | All DB queries use SQLAlchemy ORM (`select()`, `add()`, `commit()`). No raw SQL strings observed in any M2 code path. | **Pass** | — |
| **XSS** | Angular uses interpolation (`{{ }}`) throughout `status-page.component.html` and `submit-page.component.html`. Angular's default template engine HTML-encodes all interpolated values. No `[innerHTML]` or `DomSanitizer.bypassSecurityTrust*` usage found. | **Pass** | — |
| **Auth flow** | JWT middleware (`auth.py`) validates `HS256` tokens with `SECRET_KEY`. `get_current_user()` dependency is applied consistently to all protected routes. RBAC via `_can_view_submission()` in `submissions.py` prevents cross-user data access. `require_role()` factory available for future role restrictions. | **Pass** | — |
| **Test suite PAT scope** | `pipeline.py` uses the application-level `GITHUB_PAT` for both student and test suite clones. `.env.example` now documents minimum scope and recommended ownership. Clone errors are sanitized via `redact()` + `[REDACTED]` replacement in `main.py::clone_repository`. Pipeline exception handler does not log function arguments. | **Pass** (mitigated; operational recommendation remains) | Dom |
| **`POST /assignments` RBAC** | Any authenticated user can create assignments. The design-doc does not restrict this to instructors for M2. This is a privilege scope issue, not a vulnerability, but should be addressed in M3 with `require_role("instructor")`. | **Low** (by design) | Sylvie |
| **`EvaluationResult` integrity** | `submission_id UNIQUE` prevents duplicate rows. `persist_evaluation_result` catches `IntegrityError` and raises `DuplicateEvaluationError`; `pipeline.py` handles this without marking `Failed`. Duplicate pipeline runs are idempotent. | **Pass** (data safe, idempotent) | Dom |
| **Secret redaction** | `metadata_json` stores structured parser output, not raw container logs. LLM redactor (`llm.py`) strips PATs and emails before any external call. Clone error messages are scrubbed via `redact()` and literal PAT replacement. No raw secrets observed in persisted fields. | **Pass** | — |
| **Container cleanup** | `docker_runner.py` line 170–175: `container.remove(force=True)` in `finally` block ensures ephemeral behavior. Client connection is closed in `finally` (line 176). `pipeline.py` line 107: `shutil.rmtree(test_suite_dir, ignore_errors=True)` in `finally` cleans up cloned test suite directory. | **Pass** | Jayden / Dom |

---

## 6. Efficiency & Optimization Recommendations

| Suggestion | Risk | Impact | Owner | Status |
|------------|------|--------|-------|--------|
| **Pre-pull sandbox images at deploy time.** Add `docker pull python:3.12-slim node:20-slim maven:3.9-openjdk-17-slim` to the deployment runbook before starting `maple-a1.service`. | None — purely operational | High (removes cold-start penalty) | Jayden | Open |
| ~~**Add a dispatch argument test.**~~ Two new tests added: `test_evaluate_dispatch_arguments_on_fresh_clone` and `test_evaluate_dispatch_arguments_on_cache_hit`. | — | — | Dom | **Resolved** |
| ~~**Upsert guard on `persist_evaluation_result`.**~~ `DuplicateEvaluationError` guard implemented. Tests pin the contract. | — | — | Dom | **Resolved** |
| ~~**Scope `GITHUB_PAT` to minimal permissions.**~~ `.env.example` and `docs/deployment.md` updated with scope requirements. | None — operational | Medium | Dom / infra | **Partially resolved** (verify Droplet PAT) |
| **Consider separate `INSTRUCTOR_GITHUB_PAT`** for test suite cloning in M3. | Low — env config change | Medium (reduces blast radius) | Dom / infra | Deferred |

---

## 7. Traceability Summary (Audit-Verified, 2026-04-16)

| # | Task | Assignee | Prior Verdict (2026-04-15) | Current Verdict | Notes |
|---|------|----------|---------------------------|-----------------|-------|
| 1 | Docker socket on Droplet | Jayden | Pass | **Pass** | `docs/deployment.md` §Docker socket (lines 215–288) fully documents setup |
| 2 | Docker SDK integration | Jayden | Pass | **Pass** | `docker_runner.py` has real SDK; `docker>=7.0` in requirements; 8 tests |
| 3 | Language-specific base images | Jayden | Pass | **Pass** | `sandbox_images.py` wired to `docker_client.py`; images passed to SDK; 17 tests |
| 4 | Container security hardening | Jayden | Pass | **Pass** | All flags in `ContainerConfig`; applied in `docker_runner._run_container_sync` |
| 5 | 30s TTL + exit codes 137/124 | Jayden | Pass | **Pass** | `container.wait(timeout=30)`; kill on timeout → exit 124; OOM → 137 |
| 6 | Log normalization circular buffer | Jayden | Pass | **Pass** | `log_normalizer.normalize_logs()` with HEAD_BYTES=2048, TAIL_BYTES=5120; 16 tests |
| 7 | Test suite injection | Dom | Pass | **Pass** | Clone + volume mount fully wired through real SDK |
| 8 | Test result capture → JSON | Dom | Pass | **Pass** | 3 frameworks, resource constraints, build failure, truncation; 10 tests |
| 9 | Language version detection | Dom | Pass | **Pass** | 4 languages + override + malformed handling; 9 tests |
| 10 | `deterministic_score` calculation | Dom | Pass | **Pass** | Rubric-weighted + fallback ratio; edge cases handled; 10 tests |
| 11 | Persist `EvaluationResult` | Dom | Pass | **Pass** | Idempotent-safe via `DuplicateEvaluationError`; 2 dedicated tests |
| 12 | `POST /evaluate` async dispatch | Dom | Pass | **Pass** | Dispatch arguments regression-tested (fresh-clone + cache-hit); 2 new tests |
| 13 | `GET /submissions/{id}` backend | Dom | Pass | **Pass** | RBAC + evaluation + metadata; 8 tests |
| 14 | `POST /assignments` `test_suite_repo_url` | Sylvie | Pass | **Pass** | Router test covers create with and without URL; 8 tests |
| 15 | `GET /assignments/{id}` returns field | Sylvie | Pass | **Pass** | `_assignment_to_dict` includes field; router test verifies |
| 16 | `GET /submissions/{id}` error contracts | Sylvie | Pass | **Pass** | 400/401/403/404 paths verified |
| 17 | Angular submission form (M1 carryover) | Sylvie | Pass | **Pass** | Reactive form, multipart POST, navigation to status page |
| 18 | Status polling page | Sylvie | Pass | **Pass** | 3s interval, terminal status detection, cleanup in ngOnDestroy |
| 19 | Test result display in UI | Sylvie | Pass | **Pass** | Score + test breakdown + framework rendered; ai_feedback placeholder ready |
| E2E | 60-second end-to-end | All | Conditional Pass | **Conditional Pass** | All code wired; requires live Droplet Docker verification |

### Score Summary

| Owner | Tasks | Pass | Partial | Fail |
|-------|-------|------|---------|------|
| Jayden | 6 | **6** | 0 | 0 |
| Dom | 7 | **7** | 0 | 0 |
| Sylvie | 6 | **6** | 0 | 0 |
| E2E | 1 | — | **Conditional** | — |

---

## 8. Milestone 2 — Final Verdict

**Milestone 2 is code-complete.** All 19 implementation tasks pass. Dom's post-audit follow-ups (dispatch regression tests, idempotent persistence, PAT-scope documentation) are resolved. The following item must be resolved before the milestone can be called fully closed:

1. **Run Docker Droplet integration test** (Medium — Jayden). Required to confirm the 60-second E2E criterion in practice. Pre-pull sandbox images on the Droplet before the demo to eliminate cold-start latency.

Recommended next step after this item: declare M2 complete and begin Milestone 3 (LLM feedback integration).

---

*Audit performed by reading all referenced files live on 2026-04-16. No prior audit summaries used as source of truth. Test suite executed: 147 tests, 0 failures.*
