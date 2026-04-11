# Milestone 2 — Sandboxed Execution & Deterministic Scoring (Week 11 — Lab 2 Prototype)

**Goal:** Working prototype where test suites run in Docker and produce a structured score. Instructor can see test results.

**Deliverable:** Instructor can submit a student GitHub URL, the system runs tests inside a Docker container, and the test results are displayed in the UI within 60 seconds. *(Source: `docs/design-doc.md` §8 "Milestone 2 — Sandboxed Execution & Deterministic Scoring")*

---

## Jayden — Docker Container Runtime (6 tasks)

**Summary:** By the end of these tasks, the Docker runtime layer will be fully operational: the Droplet has Docker accessible, the SDK can spin up hardened ephemeral containers from language-specific images, TTL enforcement kills runaway containers, and log output is normalized before it reaches any business logic. These tasks are independently verifiable with a standalone integration test against the Docker daemon — no pipeline business logic is required.

**Tasks:**

- [ ] Verify Docker is installed and the `maple-a1.service` process user has access to `/var/run/docker.sock` on the DigitalOcean Droplet; document the socket permission setup in `docs/deployment.md`. — *`docs/design-doc.md` §6 "The FastAPI backend will have direct access to the Docker Daemon via the native UNIX socket `/var/run/docker.sock`"*; also §8 "Implement Docker SDK integration: spin up ephemeral sibling containers via `/var/run/docker.sock`"*

- [ ] Integrate Docker SDK: spin up ephemeral sibling containers via the host UNIX socket `/var/run/docker.sock` (no Docker-in-Docker). — *`docs/design-doc.md` §8 "Implement Docker SDK integration: spin up ephemeral sibling containers via `/var/run/docker.sock`"*

- [ ] Define language-specific base images for the sandbox: Python/Pytest, Java/JUnit, JavaScript/Jest, TypeScript/Jest. — *`docs/design-doc.md` §8 "Define language-specific base images: Python/Pytest, Java/JUnit, JavaScript/Jest, TypeScript/Jest"*
  > *Depends on: Docker socket task above (images are pulled/built against the live daemon).*

- [ ] Implement container security hardening: run with `--no-new-privileges`, drop all Linux capabilities, mount root filesystem read-only, and apply CPU and memory limits via Docker SDK. — *`docs/design-doc.md` §8 "Implement container security hardening: `--no-new-privileges`, dropped Linux capabilities, read-only FS, CPU/memory limits, 30s TTL"*; also `docs/design-doc.md` §7 "Risk 2: Docker Sandbox Misconfiguration" (mitigation)*
  > *Depends on: Docker SDK integration task above (hardening flags are applied at container creation).*

- [ ] Implement a 30-second TTL: forcibly kill containers that exceed the time limit; map exit code `124` (timeout) and `137` (OOM kill) to a `resource_constraint_metadata` flag injected into the evaluation reasoning object rather than failing silently. — *`docs/design-doc.md` §8 "30s TTL" and §3 §IV "Resource Constraints: exit codes 137 (OOM) or 124 (Timeout) … inject a Resource Constraint Metadata flag"*
  > *Depends on: Docker SDK integration task above. The `resource_constraint_metadata` flag is consumed by Dom's test result capture task.*

- [ ] Implement log normalization using a circular buffer: retain the first 2 KB and last 5 KB of the execution trace; discard the middle to prevent context bloat. — *`docs/design-doc.md` §8 "Implement log normalization: circular buffer keeping first 2KB + last 5KB of execution trace"*; also `docs/design-doc.md` §3 §IV "Log Normalization: Circular Buffer truncates logs, retaining only the first 2KB and last 5KB"*
  > *Depends on: Docker SDK integration task above. Normalized log output is the raw input consumed by Dom's test result capture task.*

---

## Dom — Pipeline Business Logic (7 tasks)

**Summary:** By the end of these tasks, the backend will inject test suites into Jayden's containers, parse the output into structured scores, and persist a complete `EvaluationResult`. The async `POST /evaluate` dispatch and `GET /submissions/{id}` backend endpoint are also implemented here, as they are the direct orchestrators of the scoring pipeline. Unit tests for these tasks can be written against mock container output before Jayden's runtime layer is integrated; full integration tests require Jayden's section to be complete.

**Tasks:**

- [ ] Implement test suite injection: at container startup, mount the cleaned student repository (from `data/raw/`) and the instructor-provided test suite (cloned from `test_suite_repo_url`) into the container as volume mounts. — *`docs/design-doc.md` §8 "Implement test suite injection: mount cleaned student repo + instructor-provided test suite into container"*; `docs/api-spec.md` `POST /assignments` (`test_suite_repo_url` field)*
  > *Depends on: Jayden's Docker SDK integration and base images tasks (containers must be startable before mounts can be applied). Unit-testable in isolation with a mock Docker client.*

- [ ] Capture test results from container stdout/stderr: parse the output into a structured JSON object; handle cases where the build fails, no tests run, or the framework is unrecognized. — *`docs/design-doc.md` §8 "Implement test result capture: parse stdout/stderr into structured JSON; handle exit codes 137 (OOM) and 124 (timeout)"*
  > *Depends on: Jayden's TTL and log normalization tasks (exit codes and truncated logs are the raw inputs). Unit-testable against fixture log strings without a live container.*

- [ ] Implement language version detection: read `pyproject.toml` (Python), `pom.xml` (Java), `package.json` (JavaScript/TypeScript), or `CMakeLists.txt` (C++) from the student repository to detect the runtime version; if `language_override` is set on the assignment, use that value instead; store the resolved version in `metadata_json`. — *`docs/design-doc.md` §8 "Implement language version detection: read `pyproject.toml`, `pom.xml`, `package.json` to extract version; store in `metadata_json`; display to instructor"*; also `docs/design-doc.md` §3 §II "Version Detection"*
  > *No cross-section dependencies. Fully unit-testable against fixture repository files.*

- [ ] Calculate `deterministic_score`: map the test pass/fail counts against rubric point weights to produce a numeric score on a 0–100 scale. — *`docs/design-doc.md` §8 "Calculate `deterministic_score` from test pass/fail ratio mapped to rubric point weights"*
  > *Depends on: test result capture task above (requires the structured JSON output). Fully unit-testable with mock test result fixtures.*

- [ ] Persist `EvaluationResult` with `deterministic_score` and `metadata_json` populated (including language version, exit code, resource constraint flags, and model fields left null for M2). — *`docs/design-doc.md` §8 "Persist `EvaluationResult` with `deterministic_score` and `metadata_json`"*; also `docs/design-doc.md` §2 "Data Model — EvaluationResult"*
  > *Depends on: `deterministic_score` calculation and language version detection tasks above. The persisted record is what Sylvie's `GET /submissions/{id}` and frontend tasks read.*

- [ ] Extend `POST /evaluate` to dispatch the sandbox pipeline as an async background task so the endpoint returns `submission_id` immediately without blocking on test execution. — *`docs/design-doc.md` §8 "Implement `POST /api/v1/code-eval/evaluate` with async task dispatch"*; `docs/api-spec.md` `POST /evaluate` ("The `submission_id` in the response is a UUID backed by the database (not ephemeral)")*
  > *Depends on: test suite injection, language version detection, and `EvaluationResult` persistence tasks above (the background task orchestrates all of them).*

- [ ] Implement `GET /submissions/{submission_id}`: return submission fields with no `evaluation` key when the result is not yet available, and include `evaluation.deterministic_score` + `evaluation.ai_feedback` (null for M2) once `EvaluationResult` is persisted. — *`docs/design-doc.md` §8 "Implement `GET /api/v1/code-eval/submissions/{id}` for frontend polling"*; `docs/api-spec.md` `GET /submissions/{submission_id}` (both response shapes)*
  > *Depends on: `EvaluationResult` persistence task above (the endpoint reads the persisted record). Sylvie's status polling page and test result display tasks depend on this endpoint being implemented.*

---

## Sylvie — API Contracts & Frontend (6 tasks)

**Summary:** By the end of these tasks, the `POST /assignments` and `GET /assignments/{id}` endpoints will conform fully to spec, `GET /submissions/{id}` error handling will be verified, and the Angular app will have a complete submission form, live status polling, and a test result display. The API contract tasks are verifiable with pytest against a running server (no Docker pipeline required); the Angular tasks require Dom's `GET /submissions/{id}` endpoint to be up for full end-to-end testing but can be developed against a mock HTTP backend in isolation.

**Tasks:**

### API Contract Alignment

- [ ] Confirm `POST /assignments` accepts and persists the `test_suite_repo_url` field; return it in the 200 response body. — *`docs/api-spec.md` `POST /assignments` (`test_suite_repo_url`: "URL to a test suite repository")*

- [ ] Confirm `GET /assignments/{assignment_id}` returns `test_suite_repo_url` in the response `data` object. — *`docs/api-spec.md` `GET /assignments/{assignment_id}` (success 200 response schema)*
  > *Depends on: `POST /assignments` task above (assignment record with `test_suite_repo_url` must exist to be retrieved).*

- [ ] Verify `GET /submissions/{submission_id}` returns 400 `VALIDATION_ERROR` for a non-UUID `submission_id`, 401 for a missing or expired JWT, and 404 `NOT_FOUND` when no record exists. — *`docs/api-spec.md` `GET /submissions/{submission_id}` (Errors table)*
  > *Depends on: Dom's `GET /submissions/{id}` implementation task (the endpoint must exist before error paths can be verified).*

### Frontend (Angular)

- [ ] Complete the Angular student submission form: fields for GitHub URL and assignment ID, submit via `POST /evaluate`, navigate to the status page with the returned `submission_id`. *(M1 carryover — task explicitly re-listed for M2)* — *`docs/design-doc.md` §8 "Angular scaffold: student submission form (GitHub URL + assignment ID), status polling page"*

- [ ] Implement submission status polling page: on load, start polling `GET /submissions/{id}` at a reasonable interval; display the current `status` value; stop polling when `status` is terminal (`Completed` or `Failed`). — *`docs/design-doc.md` §8 "Angular: submission status polling; test result display with pass/fail breakdown"*; also `docs/design-doc.md` §1 User Story 8 "poll the system for status updates"*
  > *Depends on: Angular submission form task above (navigates to this page with `submission_id`). Depends on Dom's `GET /submissions/{id}` endpoint for full integration; develop against a mock HTTP response in isolation.*

- [ ] Display test result breakdown in the UI: once `evaluation` is present, render the `deterministic_score` and a pass/fail summary derived from the structured JSON returned by `GET /submissions/{id}`. — *`docs/design-doc.md` §8 "test result display with pass/fail breakdown"*; `docs/api-spec.md` `GET /submissions/{submission_id}` (with-evaluation response: `evaluation.deterministic_score`)*
  > *Depends on: status polling page task above (the display renders within the same page). Requires Dom's `EvaluationResult` persistence to be complete for real data; develop against a mock `evaluation` JSON fixture in isolation.*

---

## Integration Point

The Milestone 2 deliverable connects all three workstreams in sequence. Jayden's container runtime is the execution layer; Dom's pipeline business logic orchestrates it and exposes the result via API; Sylvie's frontend and API contracts surface it to the user. Each workstream has been scoped so it can be tested independently before the full pipeline is wired:

1. **Jayden** — verify containers launch, apply security settings, enforce TTL, and produce normalized logs (standalone Docker integration test, no business logic needed).
2. **Dom** — unit test scoring and persistence against mock container output; full integration test against Jayden's containers once available.
3. **Sylvie** — verify API contracts and Angular components against mock data; full end-to-end test once Dom's endpoints are live.

**End-to-end verification:** instructor submits a GitHub URL via the Angular form → `POST /evaluate` returns `submission_id` → Angular polls `GET /submissions/{submission_id}` → Docker container runs test suite → `EvaluationResult` persisted → UI renders `deterministic_score` and pass/fail breakdown — all within 60 seconds. *(Source: `docs/design-doc.md` §8 deliverable; also §5 "Evaluation Plan — Sandboxed execution" and NFR-1.1 60s criterion)*

---

## Traceability Summary

Verdicts below were reconciled with [`audits/milestone-02-forensic-audit-2026-04-11.md`](../../audits/milestone-02-forensic-audit-2026-04-11.md) (revision 2026-04-11). `*` = not reverified in this pass; use the audit matrix for Jayden/Sylvie/E2E detail.

| # | Task (short label) | Assignee | Source file | Marker | Verdict |
|---|---|---|---|---|---|
| 1 | Docker socket on Droplet | Jayden | `docs/design-doc.md` | §6 `/var/run/docker.sock`; §8 Docker SDK integration | pass * |
| 2 | Docker SDK integration | Jayden | `docs/design-doc.md` | §8 "Implement Docker SDK integration" | pass * |
| 3 | Language-specific base images | Jayden | `docs/design-doc.md` | §8 "Define language-specific base images" | pass * |
| 4 | Container security hardening | Jayden | `docs/design-doc.md` | §8 "container security hardening"; §7 Risk 2 mitigation | pass * |
| 5 | 30s TTL + exit codes 137/124 | Jayden | `docs/design-doc.md` | §8 "30s TTL"; §3 §IV "Resource Constraints" | pass * |
| 6 | Log normalization circular buffer | Jayden | `docs/design-doc.md` | §8 "log normalization: circular buffer"; §3 §IV "Log Normalization" | pass * |
| 7 | Test suite injection | Dom | `docs/design-doc.md` + `docs/api-spec.md` | §8 "test suite injection"; `POST /assignments` `test_suite_repo_url` | **partial** — clone + `run_container` paths; SDK mounts pending Jayden |
| 8 | Test result capture → structured JSON | Dom | `docs/design-doc.md` | §8 "test result capture: parse stdout/stderr into structured JSON" | **pass** — `parse_test_results` + `run_pipeline` |
| 9 | Language version detection | Dom | `docs/design-doc.md` | §8 "language version detection"; §3 §II "Version Detection" | **pass** — `detect_language_version` → `metadata_json.language` |
| 10 | `deterministic_score` calculation | Dom | `docs/design-doc.md` | §8 "Calculate `deterministic_score`" | **pass** — `calculate_deterministic_score` in `run_pipeline` |
| 11 | Persist `EvaluationResult` | Dom | `docs/design-doc.md` | §8 "Persist `EvaluationResult`"; §2 "Data Model — EvaluationResult" | **pass** — score + `metadata_json` (language, exit_code, constraints, test_summary) |
| 12 | `POST /evaluate` async dispatch | Dom | `docs/design-doc.md` + `docs/api-spec.md` | §8 "async task dispatch"; `POST /evaluate` response contract | **pass** — `create_task`; response `status` `"Pending"` when assignment set |
| 13 | `GET /submissions/{id}` backend endpoint | Dom | `docs/design-doc.md` + `docs/api-spec.md` | §8 "Implement `GET …/submissions/{id}`"; `GET /submissions/{submission_id}` | **pass** — `evaluation` + `evaluation.metadata` subset for UI |
| 14 | `POST /assignments` `test_suite_repo_url` | Sylvie | `docs/api-spec.md` | `POST /assignments` field table | pass * |
| 15 | `GET /assignments/{id}` returns `test_suite_repo_url` | Sylvie | `docs/api-spec.md` | `GET /assignments/{assignment_id}` success response | pass * |
| 16 | `GET /submissions/{id}` error contracts | Sylvie | `docs/api-spec.md` | `GET /submissions/{submission_id}` Errors table | pass * |
| 17 | Angular submission form (M1 carryover) | Sylvie | `docs/design-doc.md` | §8 "Angular scaffold: student submission form" | pass * |
| 18 | Status polling page | Sylvie | `docs/design-doc.md` | §8 "Angular: submission status polling"; §1 User Story 8 | **fail** — TODO placeholder; no polling (`audit` §2 Sylvie) |
| 19 | Test result display in UI | Sylvie | `docs/design-doc.md` + `docs/api-spec.md` | §8 "test result display with pass/fail breakdown"; `GET /submissions/{id}` with-evaluation response | **fail** — no score/summary in Angular (`audit` §2 Sylvie) |
| E2E | End-to-end 60s verification | All | `docs/design-doc.md` | §8 deliverable; §5 "Sandboxed execution" NFR-1.1 | **fail** — Docker stub + frontend gaps (`audit` §2 E2E) |
