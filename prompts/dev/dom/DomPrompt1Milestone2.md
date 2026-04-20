---

## Section A — Test Suite Injection and Async Dispatch (Tasks 7, 12)

**Objective**

Implement the background pipeline orchestrator and Docker client abstraction so that `POST /evaluate` dispatches test execution as an async task and returns `submission_id` immediately. The pipeline clones the instructor test suite, mounts it alongside the student repo into a Docker container, and manages the `Submission.status` lifecycle (`Pending` -> `Testing` -> `Completed` / `Failed`).

**Inputs to use**

1. **`prompts/dev/dom/dom_milestone_2_plan.md`** — Section A. Follow the file paths, function signatures, and design decisions exactly.
2. **`docs/milestones/milestone-02-tasks.md`** — Tasks 7 (test suite injection) and 12 (async dispatch) under "Dom — Pipeline Business Logic".
3. **`docs/design-doc.md`** — Section 8 "Milestone 2" for the Docker mount and async dispatch requirements. Section 6 for `/var/run/docker.sock` access pattern.
4. **`docs/api-spec.md`** — `POST /evaluate` response contract (submission_id is UUID, returned immediately) and `POST /assignments` (`test_suite_repo_url` field).

**Files to create**

1. **`server/app/services/docker_client.py`** — Mockable abstraction over Jayden's Docker SDK. Defines `ContainerResult` dataclass (stdout, stderr, exit_code) and `run_container(image, student_repo_path, test_suite_path, timeout_seconds)` async function. Mount student repo at `/workspace/student` read-only, test suite at `/workspace/tests` read-only. Delegate security hardening and TTL to Jayden's runtime layer.

2. **`server/app/services/pipeline.py`** — `run_pipeline(submission_id, assignment_id, student_repo_path, rubric_content, github_pat)` async function. Opens its own DB session via `async_session_maker()`. Steps: update status to `Testing`, load assignment for `test_suite_repo_url` and `language_override`, clone test suite, detect language, run container, parse results, calculate score, persist `EvaluationResult`, update status to `Completed`. Wraps entire body in try/except — on failure set status to `Failed` and log the error.

3. **`server/tests/test_pipeline.py`** — Unit tests with mocked `docker_client`, `async_session_maker`, and `clone_repository`. Test successful completion (status transitions, EvaluationResult created), failure path (status = Failed), test suite clone called with correct URL, and no Docker call when assignment_id is None.

**Files to modify (additive only)**

- **`server/app/main.py`** — Add `from .services.pipeline import run_pipeline` to imports. After each `create_submission()` call (cache-hit path ~line 535 and clone path ~line 600), add `asyncio.create_task(run_pipeline(...))` dispatch. Only dispatch when `parsed_assignment_id is not None`. Do NOT change any existing logic in the handler.

**Files NOT to modify**

- `server/app/config.py`
- `server/app/utils/responses.py`
- `server/app/middleware/auth.py`
- `server/app/routers/auth.py`
- `server/app/utils/security.py`
- `requirements.txt`
- Any Jayden Docker runtime files
- Any Sylvie Angular/frontend files
- Do NOT change existing logic inside `evaluate_submission`, `clone_repository`, `validate_github_repo_access`, or `resolve_repository_head_commit_hash`

**Acceptance criteria**

- [ ] `POST /evaluate` returns `submission_id` immediately without blocking on Docker execution
- [ ] Background task updates `Submission.status` through `Pending -> Testing -> Completed`
- [ ] On any pipeline exception, `Submission.status` is set to `Failed`
- [ ] Test suite is cloned from `Assignment.test_suite_repo_url` when present
- [ ] Student repo and test suite are mounted as volume paths into the container
- [ ] Pipeline is not dispatched when `assignment_id` is None (M1 clone-only behavior preserved)
- [ ] All tests in `test_pipeline.py` pass
- [ ] No linter errors introduced

**Constraints**

- Use `asyncio.create_task()` for dispatch (not `BackgroundTasks`)
- Pipeline function must open its own DB session — the request session closes after response
- Use relative imports (`from ..models import ...`)
- All database primary keys are UUIDs
- Do NOT overwrite or remove any existing code

**Dependencies**

- Jayden's Docker SDK integration must be complete for full integration testing
- Unit-testable in isolation with a mock `docker_client.run_container` that returns fixture `ContainerResult`

---

## Section B — Test Result Capture and Language Detection (Tasks 8, 9)

**Objective**

Implement two standalone service modules: (1) a test result parser that converts raw container stdout/stderr into structured JSON with framework detection and resource constraint metadata, and (2) a language version detector that reads common config files from the student repo. Both modules are pure functions with no database or network dependencies — fully unit-testable.

**Inputs to use**

1. **`prompts/dev/dom/dom_milestone_2_plan.md`** — Section B. Follow the output schemas and detection strategies exactly.
2. **`docs/milestones/milestone-02-tasks.md`** — Tasks 8 (test result capture) and 9 (language version detection).
3. **`docs/design-doc.md`** — Section 3 §IV "Resource Constraints" for exit codes 137/124 handling. Section 3 §II "Version Detection" for config file parsing.

**Files to create**

1. **`server/app/services/test_parser.py`** — `parse_test_results(stdout: str, stderr: str, exit_code: int) -> dict` function. Returns structured JSON with fields: `framework` (pytest/junit/jest/unknown), `passed`, `failed`, `errors`, `skipped`, `tests` (list of individual test results), `resource_constraint_metadata` (set when exit_code is 137 or 124), `raw_output_truncated`. Detection strategy: check exit code first for resource constraints, then detect framework from output patterns (pytest summary line, JUnit XML tags, Jest markers), then parse individual test results. Handle build failures (compilation errors before tests), empty output, and unrecognized formats gracefully.

2. **`server/app/services/language_detector.py`** — `detect_language_version(repo_path: str, language_override: str | None = None) -> dict` function. Returns dict with `language`, `version`, `source`, `override_applied`. If `language_override` is set, return immediately with `override_applied=True`. Otherwise check for `pyproject.toml` (parse `requires-python` or Poetry python dependency), `package.json` (parse `engines.node`, detect TypeScript via `devDependencies`), `pom.xml` (parse `java.version` property), `CMakeLists.txt` (parse `CMAKE_CXX_STANDARD`). Return `unknown` if nothing found.

3. **`server/tests/test_test_parser.py`** — Unit tests with inline fixture strings for: pytest output (all pass, mixed, build failure), JUnit XML, Jest output, exit code 137 (OOM), exit code 124 (timeout), empty output, unrecognized framework. At least 9 test cases.

4. **`server/tests/test_language_detector.py`** — Unit tests using `TemporaryDirectory` with fixture config files for: Python (pyproject.toml), JavaScript (package.json), TypeScript (package.json with typescript dep), Java (pom.xml), C++ (CMakeLists.txt), override precedence, empty directory. At least 7 test cases.

**Files NOT to modify**

- All files listed in the Existing Code Inventory
- No modifications to any existing file — these are standalone new modules

**Acceptance criteria**

- [ ] Pytest, JUnit, and Jest output formats are correctly parsed into the structured schema
- [ ] Exit code 137 sets `oom_killed=True` in `resource_constraint_metadata`
- [ ] Exit code 124 sets `timed_out=True` in `resource_constraint_metadata`
- [ ] Build failures produce `errors=1` with the error message captured
- [ ] Empty/unrecognized output returns `framework="unknown"` with zero counts
- [ ] All four config file types are detected correctly
- [ ] `language_override` takes precedence over file-based detection
- [ ] Missing config files return `language="unknown"`
- [ ] All tests in `test_test_parser.py` and `test_language_detector.py` pass
- [ ] No linter errors introduced

**Constraints**

- These are pure service modules — no database access, no network calls, no FastAPI dependencies
- Use relative imports (`from ..services import ...` if needed from other modules)
- Parse files defensively — never crash on malformed config files, return `unknown` instead
- Do NOT add any dependencies to `requirements.txt` — use only stdlib (`tomllib` for TOML on Python 3.11+, `xml.etree.ElementTree` for XML, `json` for JSON)

**Dependencies**

- None. Both modules are fully self-contained and unit-testable without any other sections.

---

## Section C — Deterministic Scoring and Persistence (Tasks 10, 11)

**Objective**

Implement the scoring algorithm that maps test pass/fail counts to a 0-100 scale score, and the persistence function that creates an `EvaluationResult` row in the database with the score, metadata, and null AI feedback (M2 scope).

**Inputs to use**

1. **`prompts/dev/dom/dom_milestone_2_plan.md`** — Section C. Follow the scoring logic, metadata_json schema, and function signatures exactly.
2. **`docs/milestones/milestone-02-tasks.md`** — Tasks 10 (deterministic_score) and 11 (persist EvaluationResult).
3. **`docs/design-doc.md`** — Section 8 "Calculate `deterministic_score` from test pass/fail ratio mapped to rubric point weights". Section 2 "Data Model — EvaluationResult" for entity fields.
4. **`server/app/models/evaluation_result.py`** — The existing ORM model with `deterministic_score` (Float, nullable), `ai_feedback_json` (JSON, nullable), `metadata_json` (JSON, nullable).

**Files to create**

1. **`server/app/services/scoring.py`** — `calculate_deterministic_score(test_results: dict, rubric_content: dict | list | str | None = None) -> float` function. Scoring logic: if rubric has weighted criteria and test names can be mapped to criteria, distribute points proportionally. Default fallback: `(passed / total) * 100`. Edge cases: 0 total tests = 0.0, all errors = 0.0. Skipped tests are excluded from the total.

2. **`server/tests/test_scoring.py`** — Unit tests: all pass = 100, all fail = 0, mixed = proportional, zero tests = 0, all errors = 0, skipped excluded from total, rubric-weighted scoring path. At least 7 test cases.

**Files to modify (additive only)**

- **`server/app/services/submissions.py`** — Add `persist_evaluation_result(db, *, submission_id, deterministic_score, metadata_json) -> EvaluationResult` function. Imports `EvaluationResult` from `..models.evaluation_result`. Creates the row with `ai_feedback_json=None`, commits, refreshes, returns. Do NOT modify existing functions.

**Files NOT to modify**

- `server/app/models/evaluation_result.py` (ORM already has the right columns)
- `server/app/models/submission.py`
- All Jayden and Sylvie files
- `config.py`, `security.py`, `responses.py`, `requirements.txt`

**Acceptance criteria**

- [ ] `calculate_deterministic_score` returns 100.0 for all-pass, 0.0 for all-fail, proportional for mixed
- [ ] Zero total tests returns 0.0 (no division by zero)
- [ ] Skipped tests are excluded from the denominator
- [ ] `persist_evaluation_result()` creates an `EvaluationResult` row with correct `submission_id`, `deterministic_score`, `metadata_json`, and `ai_feedback_json=None`
- [ ] All tests in `test_scoring.py` pass
- [ ] No linter errors introduced

**Constraints**

- `scoring.py` is a pure function — no database, no network
- `persist_evaluation_result` goes in the existing `submissions.py` service file, not a new file
- Use relative imports
- All primary keys are UUIDs

**Dependencies**

- Depends on Section B's `parse_test_results` output schema (the `test_results` dict input). For unit testing, construct the dict directly — no need to import the parser.

---

## Section D — GET /submissions/{id} Verification (Task 13)

**Objective**

Verify that the existing `GET /submissions/{submission_id}` endpoint correctly handles the M2 pipeline lifecycle: it should return submission data without an `evaluation` key when the pipeline is still running, and include `evaluation.deterministic_score` and `evaluation.ai_feedback` (null for M2) once an `EvaluationResult` is persisted. Add tests to confirm both response shapes and the new status values.

**Inputs to use**

1. **`prompts/dev/dom/dom_milestone_2_plan.md`** — Section D. Review the "Current State Analysis" to understand what already exists.
2. **`docs/api-spec.md`** — Section 7 "GET /submissions/{submission_id}" for both with-evaluation and without-evaluation response schemas.
3. **`server/app/routers/submissions.py`** — The existing endpoint implementation with RBAC and eager loading.

**Files to modify (if needed)**

- **`server/app/routers/submissions.py`** — Review lines 83-87. If `metadata_json` should be included in the evaluation response (check `docs/api-spec.md`), add `"metadata": submission.evaluation_result.metadata_json` to the evaluation dict. Otherwise, no code changes needed — the existing implementation already matches the spec.

**Files to extend**

- **`server/tests/test_submissions_router.py`** — Add new test cases to the existing `GetSubmissionAuthorizationTests` class (or a new sibling class). Use the existing `_submission()` fixture helper and `_db_with_submission()` pattern.

New test cases to add:

- `test_submission_without_evaluation_has_no_evaluation_key` — Create a submission mock with `evaluation_result=None`. Call `get_submission()` as the student owner. Verify `payload["success"]` is True and `"evaluation"` is NOT a key in `payload["data"]`.
- `test_submission_with_evaluation_includes_score_and_null_feedback` — Create a submission mock with `evaluation_result=SimpleNamespace(deterministic_score=85.0, ai_feedback_json=None, metadata_json={...})`. Call `get_submission()` as the student owner. Verify `payload["data"]["evaluation"]["deterministic_score"]` is 85.0 and `payload["data"]["evaluation"]["ai_feedback"]` is None.
- `test_submission_status_reflects_testing` — Create a submission with `status="Testing"`. Verify `payload["data"]["status"]` is `"Testing"`.
- `test_submission_status_reflects_completed` — Create a submission with `status="Completed"`. Verify `payload["data"]["status"]` is `"Completed"`.

**Files NOT to modify**

- `server/app/models/submission.py`
- `server/app/models/evaluation_result.py`
- All Jayden and Sylvie files
- `config.py`, `security.py`, `responses.py`, `requirements.txt`

**Acceptance criteria**

- [ ] `GET /submissions/{id}` returns no `evaluation` key when `EvaluationResult` is absent
- [ ] `GET /submissions/{id}` returns `evaluation.deterministic_score` (float) and `evaluation.ai_feedback` (null) when `EvaluationResult` is present
- [ ] `status` field correctly reflects `"Testing"`, `"Completed"`, `"Failed"` lifecycle values
- [ ] Existing RBAC tests (student, instructor, admin, forbidden) continue to pass unchanged
- [ ] All new tests pass
- [ ] No linter errors introduced

**Constraints**

- Do NOT rewrite the existing `get_submission` handler or `_can_view_submission` RBAC logic
- Use the existing test patterns from `test_submissions_router.py` (SimpleNamespace mocks, `_payload()` helper, `IsolatedAsyncioTestCase`)
- Use relative imports

**Dependencies**

- Depends on Section C's `persist_evaluation_result` for full integration (the endpoint reads the persisted record). For unit testing, mock the evaluation_result directly on the submission fixture — no need for a real database.
