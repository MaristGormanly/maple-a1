# Milestone 2 — Forensic Technical Audit

**Audit date:** 2026-04-11  
**Base commit:** `affe88938985bc536b11113f0986f64c6b330a2c` (2026-04-08 16:25:37 -0400) + uncommitted working-tree changes on `dev`  
**Auditor role:** Senior technical auditor and QA engineer  
**Scope:** Verification of the workspace against [`docs/milestones/milestone-02-tasks.md`](../docs/milestones/milestone-02-tasks.md), cross-checked with [`docs/design-doc.md`](../docs/design-doc.md) §8, [`docs/api-spec.md`](../docs/api-spec.md), and implementation code as it exists today.  
**Method:** Every claim verified by reading live files; no data reused from prior M1 audits.  
**Test environment:** `python3 -m unittest discover` with env stubs (`DATABASE_URL`, `SECRET_KEY`, `GITHUB_PAT` set to test values); no live PostgreSQL or Docker daemon available.

**Revision (Dom + cross-refs, 2026-04-11):** Re-verified against the current `dev` tree after pipeline integration work. Dom’s section, Jayden rows that reference `pipeline.py`, gap analysis items H1/M1/M2/M3, security note on `metadata_json`, and §7 Dom traceability were updated. [`docs/milestones/milestone-02-tasks.md`](../docs/milestones/milestone-02-tasks.md) Traceability Summary rows **7–13 (Dom)** were aligned with this audit.

**Ownership:** **Jayden** — Infrastructure & Docker Runtime; **Dom** — Pipeline Business Logic; **Sylvie** — API Contracts & Frontend.

---

## 1. Feature synthesis & architecture map (M2-relevant)

### 1.1 Architecture at audit time

```
Angular SPA (client/src/)
  ├── SubmitPageComponent → POST /evaluate (via EvaluationService)
  └── StatusPageComponent → [TODO: poll GET /submissions/:id]

FastAPI (server/app/)
  ├── main.py::evaluate_submission
  │     ├── clone / cache / preprocess (M1)
  │     ├── create_submission (DB)
  │     └── asyncio.create_task(run_pipeline(...))  ← M2 addition
  ├── routers/submissions.py::get_submission
  │     └── selectinload(evaluation_result) → conditional "evaluation" key
  ├── routers/assignments.py
  │     └── POST/GET with test_suite_repo_url
  └── services/
        ├── pipeline.py::run_pipeline          ← M2 orchestrator (calls detector, parser, scorer)
        ├── docker_client.py::run_container    ← STUB (returns exit_code=1; ignores image/TTL args)
        ├── test_parser.py::parse_test_results ← used by run_pipeline
        ├── language_detector.py               ← used by run_pipeline
        ├── scoring.py                         ← used by run_pipeline
        └── submissions.py
              ├── create_submission
              ├── persist_evaluation_result    ← M2
              └── update_submission_status     ← M2

PostgreSQL (ORM models)
  ├── Submission (status: Pending→Testing→Completed/Failed)
  └── EvaluationResult (deterministic_score, ai_feedback_json=null, metadata_json)
```

### 1.2 Test suite results

**83 tests, 0 failures** (unittest discover, no live DB or Docker):

| Suite | Tests | M2 coverage |
|-------|-------|-------------|
| `test_pipeline.py` | 5 | Pipeline lifecycle, `persist_evaluation_result` + `metadata_json` keys, parsable stdout mocks, failure paths, no-assignment skip, missing suite URL |
| `test_test_parser.py` | 10 | Pytest/JUnit/Jest parsing, 137/124, build failure, empty, truncation |
| `test_language_detector.py` | 9 | Python/JS/TS/Java/C++, override, empty, malformed |
| `test_scoring.py` | 10 | All-pass/fail/mixed/zero/errors, skipped, rubric-weighted, fallback |
| `test_submissions_router.py` | 8 | RBAC (4 M1) + evaluation key absent/present, Testing/Completed status (4 M2) |
| `test_evaluate_submission_integration.py` | 14 | Evaluate endpoint paths — `run_pipeline` mocked globally in setUp |
| Other (cache, preprocessing, URL) | 27 | M1 paths |

---

## 2. Task-by-task matrix

### Jayden — Docker Container Runtime (6 tasks)

| # | Task | Verdict | Evidence |
|---|------|---------|----------|
| 1 | Docker socket on Droplet; document in `deployment.md` | **Partial** | `docs/deployment.md` line 51 mentions `/var/run/docker.sock` in a summary table but states "Not described in detail in this file; confirm on the Droplet." No socket permission setup procedure, no `maple-a1.service` user-group verification documented. Milestone checkbox `[ ]` unchecked. |
| 2 | Docker SDK integration (sibling containers via socket) | **Fail** | `server/app/services/docker_client.py` lines 11-33: `run_container()` is a **stub** — deletes all parameters and returns `ContainerResult(stdout="", stderr="...not yet integrated", exit_code=1)`. No `docker` or `aiodocker` package in `requirements.txt`. No Docker SDK code anywhere in repo. |
| 3 | Language-specific base images (Python/Pytest, Java/JUnit, JS/Jest, TS/Jest) | **Fail** | **Jayden scope:** No `Dockerfile` / image-build scripts; daemon never pulls or runs real images. **Dom layer:** `pipeline.py` maps detected language to image tags (`python:3.12-slim`, `openjdk:17-slim`, `node:20-slim`, `gcc:13`, default `python:3.12-slim`) and passes `image` into `run_container`; the stub discards it. |
| 4 | Container security hardening (`--no-new-privileges`, capabilities, read-only FS, CPU/mem) | **Fail** | No security flags in any executable code. `docker_client.py` docstring (line 21) mentions read-only mounts "conceptually" only. `docs/design-doc.md` §7 Risk 2 lists the flags as planned mitigation. |
| 5 | 30s TTL; map exit codes 137/124 to `resource_constraint_metadata` | **Partial** | **TTL:** `pipeline.py` passes `timeout_seconds=30` (`_CONTAINER_TIMEOUT_SECONDS`); `docker_client.run_container` still ignores the parameter (`del timeout_seconds`) — no kill until Jayden implements the SDK. **Exit codes:** `parse_test_results` maps 137/124 to `resource_constraint_metadata`; `run_pipeline` calls `parse_test_results` and persists `resource_constraint_metadata` inside `metadata_json`. |
| 6 | Log normalization: circular buffer (first 2KB + last 5KB) | **Fail** | No circular buffer in any code. `test_parser.py` uses `_MAX_RAW_LEN = 50_000` for a truncation flag — different from the 2KB+5KB design. `pipeline.py` no longer copies raw `container.stderr` into `metadata_json` (only structured fields from the parser). |

### Dom — Pipeline Business Logic (7 tasks)

| # | Task | Verdict | Evidence |
|---|------|---------|----------|
| 7 | Test suite injection: mount student repo + test suite into container | **Partial** | **Milestone alignment:** Depends on Jayden’s Docker SDK (`milestone-02-tasks.md` Dom task 1). `docker_client.py` docstring documents mount targets. `run_pipeline` clones the test suite from `assignment.test_suite_repo_url`, then passes `student_repo_path` and resolved test-suite directory to `run_container()`. Stub does not mount volumes. **Dom’s obligation (paths + clone) is met; real mounts remain Jayden.** |
| 8 | Test result capture → structured JSON | **Pass** | `test_parser.parse_test_results` implements the milestone (pytest, JUnit, Jest, build failure, empty/unrecognized, 137/124). **`run_pipeline` calls it** on `ContainerResult` and persists parser output counts via `metadata_json.test_summary` and `resource_constraint_metadata`. 10 parser unit tests + pipeline tests cover the path (with mocked `run_container`). |
| 9 | Language version detection | **Pass** | `language_detector.detect_language_version` matches milestone (`pyproject.toml`, `package.json`, `pom.xml`, `CMakeLists.txt`, `language_override`). **`run_pipeline` calls it** and stores the full detection dict under `metadata_json.language`. |
| 10 | `deterministic_score` calculation | **Pass** | `scoring.calculate_deterministic_score` matches milestone (rubric weights, fallback ratio, skipped excluded). **`run_pipeline` passes the parser dict and `rubric_content` from `POST /evaluate`.** |
| 11 | Persist `EvaluationResult` | **Pass** | `persist_evaluation_result` persists `deterministic_score`, `ai_feedback_json=None`, and `metadata_json` with **`language`**, **`exit_code`**, **`resource_constraint_metadata`**, **`test_summary`** (`framework`, pass/fail/error/skip counts) — satisfies design-doc / milestone “language version, exit code, resource constraint flags” plus test counts for instructor display. |
| 12 | `POST /evaluate` async dispatch | **Pass** | `main.py`: `asyncio.create_task(run_pipeline(...))` on cache-hit and fresh-clone paths when `parsed_assignment_id is not None`. DB row `status` is `"Pending"`; **HTTP `SubmissionData.status` is also `"Pending"`** in those cases (aligned with lifecycle). Response returns immediately with `submission_id`. `run_pipeline` mocked in evaluate integration tests. |
| 13 | `GET /submissions/{id}` with/without evaluation | **Pass** | `routers/submissions.py`: UUID 400, 404, 403 RBAC, `selectinload(evaluation_result)`. No `evaluation` key until row exists. When present: `deterministic_score`, `ai_feedback` (null M2), and **`evaluation.metadata`** with **`language`** and **`test_summary`** trimmed from `metadata_json` (supports Sylvie’s pass/fail summary). Documented in `docs/api-spec.md` §7. Router tests include M2 lifecycle and evaluation shape. |

### Sylvie — API Contracts & Frontend (6 tasks)

| # | Task | Verdict | Evidence |
|---|------|---------|----------|
| 14 | `POST /assignments` accepts `test_suite_repo_url` | **Pass** | `server/app/routers/assignments.py` lines 20-25: `AssignmentCreateRequest` has `test_suite_repo_url: Optional[str] = None`. Passed to `create_assignment()` at line 63. Response via `_assignment_to_dict` includes it (line 33). |
| 15 | `GET /assignments/{id}` returns `test_suite_repo_url` | **Pass** | Same `_assignment_to_dict` helper used at line 95, includes `test_suite_repo_url` (line 33). |
| 16 | `GET /submissions/{id}` error contracts (400/401/404) | **Pass** | `routers/submissions.py`: UUID validation returns 400 `VALIDATION_ERROR` (lines 44-49); missing record returns 404 `NOT_FOUND` (lines 60-64); JWT enforced via `Depends(get_current_user)` (line 40). Matches `docs/api-spec.md` error table. |
| 17 | Angular submission form (M1 carryover) | **Pass** | `client/src/pages/submit-page/submit-page.component.ts` lines 14-19: reactive form with `githubUrl`, `assignmentId`, `rubricFile`. `EvaluationService.submitEvaluation()` posts multipart to `/api/v1/code-eval/evaluate`. Navigation to status page on success. |
| 18 | Status polling page | **Fail** | `client/src/pages/status-page/status-page.component.ts` lines 24-26: explicit `// TODO (Milestone 2)` comment. No `HttpClient` usage, no polling interval, no GET request. Only shows data from `history.state` (router navigation state). Template (line 37) still says "live status lookup is not yet available." |
| 19 | Test result display in UI | **Fail** | No `deterministic_score` rendering anywhere in `client/src/`. `api.types.ts` `SubmissionData` type has no evaluation/score fields. Status page template shows only clone/cache status badge (line 7), not test results. |

### E2E — 60-second End-to-end Verification

| # | Task | Verdict | Evidence |
|---|------|---------|----------|
| E2E | Submit → Docker → EvaluationResult → UI renders score within 60s | **Fail** | Three blocking gaps: (1) Docker runtime is a stub (empty stdout, exit 1) — no real test execution; (2) Angular status page has no polling; (3) No test result UI. Dom’s pipeline **does** parse, score, and persist when given real or mocked container output, but the full 60s user journey is still blocked. |

---

## 3. Gap analysis — ambiguities, predictive errors, interface mismatches

| Severity | Owner(s) | Cause | Explanation | Location(s) |
|----------|----------|-------|-------------|-------------|
| ~~**High**~~ **Resolved** | **Dom** | ~~Pipeline does not wire parser / detector / scorer~~ | **Fixed (2026-04-11):** `run_pipeline` imports and calls `detect_language_version`, `parse_test_results`, and `calculate_deterministic_score`; `_language_info` / `_minimal_test_results` / `_deterministic_score` removed. | `server/app/services/pipeline.py` |
| **High** | **Jayden** | Docker runtime is a non-functional stub | `docker_client.run_container()` always returns `exit_code=1` with empty stdout. With the **current** stub, `parse_test_results` yields zero counted tests → `calculate_deterministic_score` returns **0.0** (per product note: no tests counted). Pipeline unit tests use **parsable** mocked `stdout` to assert non-zero scores. Until Jayden delivers the SDK, production runs still get stub output. | `server/app/services/docker_client.py` |
| **High** | **Sylvie** | Angular status page is a TODO placeholder | Lines 24-26 of `status-page.component.ts` contain an explicit TODO. No HTTP polling, no terminal-status detection. The template (line 37) tells the user "live status lookup is not yet available." This blocks the M2 deliverable: instructors cannot see test results in the UI. | `client/src/pages/status-page/status-page.component.ts` lines 24-26; `status-page.component.html` line 37 |
| **High** | **Sylvie** | No test result display in frontend | `SubmissionData` type in `api.types.ts` has no `evaluation`, `deterministic_score`, or test breakdown fields. No component renders scores. M2 deliverable requires "test results displayed in the UI." | `client/src/utils/api.types.ts`; entire `client/src/pages/status-page/` |
| ~~**Medium**~~ **Resolved** | **Dom** | ~~Pipeline timeout 3600s~~ | **Fixed:** `pipeline.py` uses `_CONTAINER_TIMEOUT_SECONDS = 30`. Stub still ignores the value until Jayden implements enforcement. | `server/app/services/pipeline.py` |
| ~~**Medium**~~ **Resolved** | **Dom** | ~~`POST /evaluate` response `status` vs DB~~ | **Fixed:** When `parsed_assignment_id is not None`, HTTP `SubmissionData.status` is `"Pending"` (cache-hit and clone paths), matching DB. `docs/api-spec.md` §3 documents `"Pending"`. | `server/app/main.py`; `docs/api-spec.md` |
| ~~**Medium**~~ **Resolved** | **Dom** | ~~`source` string inconsistency (`override` vs `language_override`)~~ | **Obviated:** `_language_info` removed; persisted `metadata_json.language` comes only from `detect_language_version` (`source="language_override"` when override set). | `server/app/services/pipeline.py`; `language_detector.py` |
| **Medium** | **Jayden** | No `docker` package in `requirements.txt` | Even partial SDK work would require `docker>=7.0` or `aiodocker`. Absence confirms zero SDK integration has landed. | `server/requirements.txt` (11 entries, none Docker-related) |
| ~~**Low**~~ **Resolved** | **Dom** | ~~GET does not expose evaluation metadata~~ | **Fixed:** `evaluation.metadata` returns `language` and `test_summary` from `metadata_json`. Full `metadata_json` (e.g. `exit_code`, `resource_constraint_metadata`) remains DB-only unless product expands the API. | `server/app/routers/submissions.py`; `docs/api-spec.md` §7 |
| **Low** | **Jayden** | No Dockerfiles or image build scripts | Design doc §8 calls for "Define language-specific base images." No `Dockerfile`, `docker-compose.yml`, or image-build script exists anywhere in the repo. | Glob for `Dockerfile*`: 0 results |
| **Low** | **Dom** | `persist_evaluation_result` has no upsert guard | `EvaluationResult.submission_id` has a `unique=True` constraint. If `run_pipeline` is invoked twice for the same submission (e.g., retry), the second call will raise `IntegrityError` and the pipeline catches it as `Failed`, but the user gets no clear error message. | `server/app/models/evaluation_result.py` line 15; `server/app/services/submissions.py` lines 56-66 |
| **Informational** | **All** | `milestone-02-tasks.md` Traceability Summary marks all tasks "pass" | The Traceability Summary table (lines 104-125) shows verdict "pass" for all 19 tasks + E2E, but all task checkboxes in the body (lines 15-86) are `[ ]` unchecked. The table was written as an aspirational template, not a verified audit. This document should not be trusted as a status report. | `docs/milestones/milestone-02-tasks.md` lines 104-125 vs lines 15-86 |
| **Informational** | **Sylvie** | Angular has zero test coverage for M2 | Only `app.spec.ts` exists with 2 trivial tests. No tests for submit page, status page, evaluation service, or any M2 feature. | `client/src/app/app.spec.ts` |
| **Informational** | **Dom** | `evaluate_submission_integration` tests mock `run_pipeline` globally | `test_evaluate_submission_integration.py` lines 46-50 patch `app.main.run_pipeline` with `AsyncMock()` in `setUp`. This is correct for isolating evaluate-path tests, but means the integration suite does not verify that the pipeline is dispatched or that the dispatch arguments are correct. | `server/tests/test_evaluate_submission_integration.py` lines 46-50 |

---

## 4. Remediation — prioritized actions for High and Medium items

**Completed (Dom, post–initial audit):** H1 (wire three modules), M1 (30s passed from pipeline to `run_container`), M2 (`POST /evaluate` returns `"Pending"` when assignment + dispatch), M3 (`source` consistency via `language_detector` only), and exposure of `evaluation.metadata` on GET. See [`prompts/dev/dom/DomMilestone2PipelineIntegrationPlan.md`](../prompts/dev/dom/DomMilestone2PipelineIntegrationPlan.md).

### High priority

| # | Item | Remediation | Definition of done |
|---|------|-------------|-------------------|
| ~~H1~~ **Done** | ~~Pipeline does not wire `test_parser`, `language_detector`, `scoring`~~ | ~~As below~~ | Implemented in `pipeline.py`; private helpers removed; `test_pipeline.py` asserts metadata and scores with parsable mocked stdout. |
| H2 | Docker runtime stub | Jayden: integrate `docker` SDK or `aiodocker`. Implement `run_container()` body with real `client.containers.run(...)`, volume mounts to `/workspace/student` and `/workspace/tests` (read-only), security flags, TTL kill, and log capture. Add `docker>=7.0` to `requirements.txt`. | `run_container()` starts a real container and returns actual stdout/stderr/exit_code. Integration test against Docker daemon passes. |
| H3 | Angular status polling | Sylvie: implement `HttpClient.get(GET /submissions/${id})` on a 3-5s interval in `StatusPageComponent.ngOnInit()`. Stop polling when `status` is `Completed` or `Failed`. Display `status` badge with M2 values (`Pending`, `Testing`, `Completed`, `Failed`). | Direct navigation to `/status/:uuid` fetches and displays live submission state; polling stops on terminal status. |
| H4 | Test result display in Angular | Sylvie: extend `SubmissionData` type with optional `evaluation` object. When present, render `deterministic_score` and pass/fail summary in the status page template. | Instructor sees numeric score and test breakdown after pipeline completes. |

### Medium priority

| # | Item | Remediation |
|---|------|-------------|
| ~~M1~~ **Done** | ~~Pipeline timeout~~ | `timeout_seconds=30` from pipeline (stub ignores until SDK). |
| ~~M2~~ **Done** | ~~Response status~~ | HTTP `status` is `"Pending"` when assignment + dispatch. |
| ~~M3~~ **Done** | ~~`source` inconsistency~~ | Resolved by H1. |
| M4 | Add `docker` to `requirements.txt` | Blocked on H2. |

---

## 5. Security assessment (M2-scoped)

| Area | Finding | Severity |
|------|---------|----------|
| **Container sandbox** | No containers run — all security hardening (capabilities, read-only FS, resource limits) is documented but not implemented. Until Jayden's SDK lands, there is **no sandbox risk** because there is **no sandbox**. | N/A (blocked) |
| **Test suite clone uses student-provided PAT** | `pipeline.py` line 84 calls `clone_repository(suite_url, ..., github_pat)` with the **student's** GitHub PAT (passed from evaluate handler). If `test_suite_repo_url` is a private instructor repo, the student PAT may lack access. Consider using an instructor PAT or service account. | **Medium** |
| **RBAC on `GET /submissions/{id}`** | `_can_view_submission` enforces student-owner, admin, or assignment-instructor access. `selectinload` for assignment enables instructor check without N+1. No escalation path found. | **Pass** |
| **Auth on `POST /assignments`** | `Depends(get_current_user)` present (line 44). No role restriction — any authenticated user can create assignments. Design doc does not restrict this to instructors for M2, but it is a privilege escalation surface. | **Low** |
| **SQL injection** | All DB queries use SQLAlchemy ORM (`select()`, `add()`, `commit()`). No raw SQL strings observed in M2 code paths. | **Pass** |
| **Secrets exposure** | `metadata_json` no longer embeds raw `container.stderr` slices; it stores structured parser output and summaries. If product later persists full raw logs, apply `redact()` or similar before storage. | **Low** |
| **`EvaluationResult` uniqueness** | `submission_id` is `unique=True` on the model. Concurrent or retried pipeline runs for the same submission will raise `IntegrityError`, caught by the broad `except Exception` and logged. No data corruption, but no user-facing message. | **Low** |

---

## 6. Efficiency & risk notes (low-risk wins only)

| Suggestion | Risk | Impact |
|------------|------|--------|
| ~~**Wire the three standalone modules (H1)**~~ | Done — see §4. | — |
| **Add a `GET /submissions/{id}` integration test** that verifies `asyncio.create_task` dispatch and pipeline argument passing, using a mock pipeline. Currently the evaluate integration suite skips this entirely. | Low — test-only change. | Catches regressions in the dispatch wiring (status, arguments). |
| ~~**Delete inline pipeline helpers**~~ | Done with H1. | — |
| **`SubmissionData` type in Angular** should be updated to match the `GET /submissions/{id}` response shape from `api-spec.md`, not the `POST /evaluate` response shape. The two responses have different fields (`created_at`, `evaluation` vs `rubric_digest`, `local_repo_path`). | Low — type-only change. | Prevents runtime type errors when status page eventually fetches from GET endpoint. |

---

## 7. Traceability summary (audit-verified)

| # | Task (short label) | Assignee | Verdict | Notes |
|---|---|---|---|---|
| 1 | Docker socket on Droplet | Jayden | **Partial** | Mentioned in deployment.md but no setup procedure |
| 2 | Docker SDK integration | Jayden | **Fail** | Stub only; no SDK package |
| 3 | Language-specific base images | Jayden | **Fail** | Only `python:3.12-slim` string; no Dockerfiles |
| 4 | Container security hardening | Jayden | **Fail** | Docstring only; no executable flags |
| 5 | 30s TTL + 137/124 mapping | Jayden | **Partial** | Exit code mapping in `test_parser`; no TTL enforcement |
| 6 | Log normalization circular buffer | Jayden | **Fail** | No 2KB+5KB buffer; different truncation logic |
| 7 | Test suite injection (mounts) | Dom | **Partial** | Clone + paths into `run_container`; real mounts blocked on Jayden stub |
| 8 | Test result capture → JSON | Dom | **Pass** | `parse_test_results` invoked from `run_pipeline`; counts in `metadata_json` |
| 9 | Language version detection | Dom | **Pass** | `detect_language_version` + `metadata_json.language` |
| 10 | `deterministic_score` calculation | Dom | **Pass** | `calculate_deterministic_score` in pipeline with evaluate rubric |
| 11 | Persist `EvaluationResult` | Dom | **Pass** | `persist_evaluation_result` + structured `metadata_json` per milestone |
| 12 | `POST /evaluate` async dispatch | Dom | **Pass** | `create_task`; HTTP + DB `status` `"Pending"` when assignment present |
| 13 | `GET /submissions/{id}` | Dom | **Pass** | RBAC; `evaluation` + `evaluation.metadata` (`language`, `test_summary`) |
| 14 | `POST /assignments` `test_suite_repo_url` | Sylvie | **Pass** | Field accepted and persisted |
| 15 | `GET /assignments/{id}` returns field | Sylvie | **Pass** | Via `_assignment_to_dict` |
| 16 | `GET /submissions/{id}` error contracts | Sylvie | **Pass** | 400/401/404 per spec |
| 17 | Angular submission form | Sylvie | **Pass** | Reactive form + multipart POST |
| 18 | Status polling page | Sylvie | **Fail** | TODO placeholder; no HTTP call |
| 19 | Test result display in UI | Sylvie | **Fail** | No score/breakdown rendering |
| E2E | 60s end-to-end | All | **Fail** | Docker stub + no frontend polling + no result UI |

### Score summary

- **Jayden:** 0 Pass, 2 Partial, 4 Fail (0 of 6 fully done)
- **Dom:** 6 Pass, 1 Partial, 0 Fail (6 of 7 fully done; Task 7 blocked on Jayden SDK for real mounts)
- **Sylvie:** 4 Pass, 0 Partial, 2 Fail (4 of 6 fully done)
- **E2E:** Fail (blocked by all three workstreams)

### Documentation drift

The `milestone-02-tasks.md` **Traceability Summary** historically marked all rows **pass**, which did not match this audit. **Revised 2026-04-11:** Dom rows **7–13** now match §7 above (**partial** for task 7, **pass** for 8–13). Jayden, Sylvie, and E2E rows in the milestone file remain **incorrect if still marked pass** — reconcile separately. Task **body** checkboxes `[ ]` are a manual completion tracker; unchecked boxes are consistent with incomplete Jayden/Sylvie/E2E work.

---

*End of Milestone 2 forensic audit. Evidence from live files at audit time; prior audits not used as source of truth.*
