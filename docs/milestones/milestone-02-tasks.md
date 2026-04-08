# Milestone 2 — Sandboxed Execution & Deterministic Scoring (Week 11 — Lab 2 Prototype)

**Goal:** Working prototype where test suites run in Docker and produce a structured score. Instructor can see test results.

**Deliverable:** Instructor can submit a student GitHub URL, the system runs tests inside a Docker container, and the test results are displayed in the UI within 60 seconds. *(Source: `docs/design-doc.md` §8 "Milestone 2 — Sandboxed Execution & Deterministic Scoring")*

---

## Dom — Docker Sandbox & Deterministic Scoring

**Summary:** By the end of these tasks, the backend will spin up ephemeral Docker containers to run instructor-provided test suites against student code, capture structured results, and persist a `deterministic_score` in `EvaluationResult`. This is the core deliverable of Milestone 2.

**Tasks:**

- [ ] Integrate Docker SDK: spin up ephemeral sibling containers via the host UNIX socket `/var/run/docker.sock` (no Docker-in-Docker). — *`docs/design-doc.md` §8 "Implement Docker SDK integration: spin up ephemeral sibling containers via `/var/run/docker.sock`"*

- [ ] Define language-specific base images for the sandbox: Python/Pytest, Java/JUnit, JavaScript/Jest, TypeScript/Jest. — *`docs/design-doc.md` §8 "Define language-specific base images: Python/Pytest, Java/JUnit, JavaScript/Jest, TypeScript/Jest"*

- [ ] Implement container security hardening: run with `--no-new-privileges`, drop all Linux capabilities, mount root filesystem read-only, and apply CPU and memory limits via Docker SDK. — *`docs/design-doc.md` §8 "Implement container security hardening: `--no-new-privileges`, dropped Linux capabilities, read-only FS, CPU/memory limits, 30s TTL"*; also `docs/design-doc.md` §7 "Risk 2: Docker Sandbox Misconfiguration" (mitigation)*

- [ ] Implement a 30-second TTL: forcibly kill containers that exceed the time limit; map exit code `124` (timeout) and `137` (OOM kill) to a `resource_constraint_metadata` flag injected into the evaluation reasoning object rather than failing silently. — *`docs/design-doc.md` §8 "30s TTL" and §3 §IV "Resource Constraints: exit codes 137 (OOM) or 124 (Timeout) … inject a Resource Constraint Metadata flag"*

- [ ] Implement test suite injection: at container startup, mount the cleaned student repository (from `data/raw/`) and the instructor-provided test suite (cloned from `test_suite_repo_url`) into the container as volume mounts. — *`docs/design-doc.md` §8 "Implement test suite injection: mount cleaned student repo + instructor-provided test suite into container"*; `docs/api-spec.md` `POST /assignments` (`test_suite_repo_url` field)*

- [ ] Capture test results from container stdout/stderr: parse the output into a structured JSON object; handle cases where the build fails, no tests run, or the framework is unrecognized. — *`docs/design-doc.md` §8 "Implement test result capture: parse stdout/stderr into structured JSON; handle exit codes 137 (OOM) and 124 (timeout)"*

- [ ] Implement log normalization using a circular buffer: retain the first 2 KB and last 5 KB of the execution trace; discard the middle to prevent context bloat. — *`docs/design-doc.md` §8 "Implement log normalization: circular buffer keeping first 2KB + last 5KB of execution trace"*; also `docs/design-doc.md` §3 §IV "Log Normalization: Circular Buffer truncates logs, retaining only the first 2KB and last 5KB"*

- [ ] Implement language version detection: read `pyproject.toml` (Python), `pom.xml` (Java), `package.json` (JavaScript/TypeScript), or `CMakeLists.txt` (C++) from the student repository to detect the runtime version; if `language_override` is set on the assignment, use that value instead; store the resolved version in `metadata_json`. — *`docs/design-doc.md` §8 "Implement language version detection: read `pyproject.toml`, `pom.xml`, `package.json` to extract version; store in `metadata_json`; display to instructor"*; also `docs/design-doc.md` §3 §II "Version Detection"*

- [ ] Calculate `deterministic_score`: map the test pass/fail counts against rubric point weights to produce a numeric score on a 0–100 scale. — *`docs/design-doc.md` §8 "Calculate `deterministic_score` from test pass/fail ratio mapped to rubric point weights"*

- [ ] Persist `EvaluationResult` with `deterministic_score` and `metadata_json` populated (including language version, exit code, resource constraint flags, and model fields left null for M2). — *`docs/design-doc.md` §8 "Persist `EvaluationResult` with `deterministic_score` and `metadata_json`"*; also `docs/design-doc.md` §2 "Data Model — EvaluationResult"*

---

## Sylvie — Backend Orchestration, API Contract & Frontend

**Summary:** By the end of these tasks, `POST /evaluate` will dispatch work asynchronously, `GET /submissions/{id}` will be fully wired for frontend polling, the Angular submission form will be complete (M1 carryover), and students/instructors will see a live pass/fail breakdown in the UI.

**Tasks:**

### Backend Orchestration

- [ ] Extend `POST /evaluate` to dispatch the sandbox pipeline as an async background task so the endpoint returns `submission_id` immediately without blocking on test execution. — *`docs/design-doc.md` §8 "Implement `POST /api/v1/code-eval/evaluate` with async task dispatch"*; `docs/api-spec.md` `POST /evaluate` ("The `submission_id` in the response is a UUID backed by the database (not ephemeral)")*

- [ ] Implement `GET /submissions/{submission_id}`: return submission fields with no `evaluation` key when the result is not yet available, and include `evaluation.deterministic_score` + `evaluation.ai_feedback` (null for M2) once `EvaluationResult` is persisted. — *`docs/design-doc.md` §8 "Implement `GET /api/v1/code-eval/submissions/{id}` for frontend polling"*; `docs/api-spec.md` `GET /submissions/{submission_id}` (both response shapes)*

### API Contract Alignment

- [ ] Confirm `POST /assignments` accepts and persists the `test_suite_repo_url` field; return it in the 200 response body. — *`docs/api-spec.md` `POST /assignments` (`test_suite_repo_url`: "URL to a test suite repository")*

- [ ] Confirm `GET /assignments/{assignment_id}` returns `test_suite_repo_url` in the response `data` object. — *`docs/api-spec.md` `GET /assignments/{assignment_id}` (success 200 response schema)*

- [ ] Verify `GET /submissions/{submission_id}` returns 400 `VALIDATION_ERROR` for a non-UUID `submission_id`, 401 for a missing or expired JWT, and 404 `NOT_FOUND` when no record exists. — *`docs/api-spec.md` `GET /submissions/{submission_id}` (Errors table)*

### Frontend (Angular)

- [ ] Complete the Angular student submission form: fields for GitHub URL and assignment ID, submit via `POST /evaluate`, navigate to the status page with the returned `submission_id`. *(M1 carryover — task explicitly re-listed for M2)* — *`docs/design-doc.md` §8 "Angular scaffold: student submission form (GitHub URL + assignment ID), status polling page"*

- [ ] Implement submission status polling page: on load, start polling `GET /submissions/{id}` at a reasonable interval; display the current `status` value; stop polling when `status` is terminal (`Completed` or `Failed`). — *`docs/design-doc.md` §8 "Angular: submission status polling; test result display with pass/fail breakdown"*; also `docs/design-doc.md` §1 User Story 8 "poll the system for status updates"*

- [ ] Display test result breakdown in the UI: once `evaluation` is present, render the `deterministic_score` and a pass/fail summary derived from the structured JSON returned by `GET /submissions/{id}`. — *`docs/design-doc.md` §8 "test result display with pass/fail breakdown"*; `docs/api-spec.md` `GET /submissions/{submission_id}` (with-evaluation response: `evaluation.deterministic_score`)*

---

## Jayden — Infrastructure

**Summary:** No new infrastructure tasks are required for Milestone 2 beyond confirming Docker is available on the Droplet and the service restarts cleanly after the new async changes.

**Tasks:**

- [ ] Verify Docker is installed and the `maple-a1.service` process user has access to `/var/run/docker.sock` on the DigitalOcean Droplet; document the socket permission setup in `docs/deployment.md`. — *`docs/design-doc.md` §6 "The FastAPI backend will have direct access to the Docker Daemon via the native UNIX socket `/var/run/docker.sock`"*; also §8 "Implement Docker SDK integration: spin up ephemeral sibling containers via `/var/run/docker.sock`"*

---

## Integration Point

The Milestone 2 deliverable spans all three workstreams. Dom's sandbox produces the `EvaluationResult`; Sylvie's async `POST /evaluate` dispatches it and exposes it via `GET /submissions/{id}`; the Angular status page renders it; Jayden's infrastructure ensures Docker is reachable on the Droplet. An integration session near the end of the milestone to run the full end-to-end flow is recommended.

**End-to-end verification:** instructor submits a GitHub URL via the Angular form → `POST /evaluate` returns `submission_id` → Angular polls `GET /submissions/{submission_id}` → Docker container runs test suite → `EvaluationResult` persisted → UI renders `deterministic_score` and pass/fail breakdown — all within 60 seconds. *(Source: `docs/design-doc.md` §8 deliverable; also §5 "Evaluation Plan — Sandboxed execution" and NFR-1.1 60s criterion)*

---

## Traceability Summary

| # | Task (short label) | Source file | Marker | Verdict |
|---|---|---|---|---|
| 1 | Docker SDK integration | `docs/design-doc.md` | §8 "Implement Docker SDK integration" | pass |
| 2 | Language-specific base images | `docs/design-doc.md` | §8 "Define language-specific base images" | pass |
| 3 | Container security hardening | `docs/design-doc.md` | §8 "container security hardening"; §7 Risk 2 mitigation | pass |
| 4 | 30s TTL + exit codes 137/124 | `docs/design-doc.md` | §8 "30s TTL"; §3 §IV "Resource Constraints" | pass |
| 5 | Test suite injection | `docs/design-doc.md` + `docs/api-spec.md` | §8 "test suite injection"; `POST /assignments` `test_suite_repo_url` | pass |
| 6 | Test result capture → structured JSON | `docs/design-doc.md` | §8 "test result capture: parse stdout/stderr into structured JSON" | pass |
| 7 | Log normalization circular buffer | `docs/design-doc.md` | §8 "log normalization: circular buffer"; §3 §IV "Log Normalization" | pass |
| 8 | Language version detection | `docs/design-doc.md` | §8 "language version detection"; §3 §II "Version Detection" | pass |
| 9 | `deterministic_score` calculation | `docs/design-doc.md` | §8 "Calculate `deterministic_score`" | pass |
| 10 | Persist `EvaluationResult` | `docs/design-doc.md` | §8 "Persist `EvaluationResult`"; §2 "Data Model — EvaluationResult" | pass |
| 11 | `POST /evaluate` async dispatch | `docs/design-doc.md` + `docs/api-spec.md` | §8 "async task dispatch"; `POST /evaluate` response contract | pass |
| 12 | `GET /submissions/{id}` polling endpoint | `docs/design-doc.md` + `docs/api-spec.md` | §8 "Implement `GET …/submissions/{id}`"; `GET /submissions/{submission_id}` | pass |
| 13 | `POST /assignments` `test_suite_repo_url` | `docs/api-spec.md` | `POST /assignments` field table | pass |
| 14 | `GET /assignments/{id}` returns `test_suite_repo_url` | `docs/api-spec.md` | `GET /assignments/{assignment_id}` success response | pass |
| 15 | `GET /submissions/{id}` error contracts | `docs/api-spec.md` | `GET /submissions/{submission_id}` Errors table | pass |
| 16 | Angular submission form (M1 carryover) | `docs/design-doc.md` | §8 "Angular scaffold: student submission form" | pass |
| 17 | Status polling page | `docs/design-doc.md` | §8 "Angular: submission status polling"; §1 User Story 8 | pass |
| 18 | Test result display in UI | `docs/design-doc.md` + `docs/api-spec.md` | §8 "test result display with pass/fail breakdown"; `GET /submissions/{id}` with-evaluation response | pass |
| 19 | Docker socket on Droplet | `docs/design-doc.md` | §6 `/var/run/docker.sock`; §8 Docker SDK integration | pass |
| E2E | End-to-end 60s verification | `docs/design-doc.md` | §8 deliverable; §5 "Sandboxed execution" NFR-1.1 | pass |
