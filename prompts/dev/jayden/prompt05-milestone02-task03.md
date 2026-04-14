# Milestone 02 — Task 03: Define Language-Specific Base Images

## Task Definition

> Define language-specific base images for the sandbox: Python/Pytest, Java/JUnit, JavaScript/Jest, TypeScript/Jest.
> — `docs/design-doc.md` §8

## Implementation Summary

### What Was Done

**1. Created `server/app/services/sandbox_images.py`** (new file)

Central registry of per-language sandbox profiles. Each `SandboxProfile` (frozen dataclass) defines:

| Language     | Docker Image                  | Install Command                              | Test Command           |
|-------------|-------------------------------|----------------------------------------------|------------------------|
| Python      | `python:3.12-slim`            | `pip install --no-cache-dir -r requirements.txt` (conditional) | `pytest --tb=short -v` |
| Java        | `maven:3.9-openjdk-17-slim`   | None (Maven handles deps)                    | `mvn test -B`          |
| JavaScript  | `node:20-slim`                | `npm ci --ignore-scripts` (conditional)      | `npx jest --verbose`   |
| TypeScript  | `node:20-slim`                | `npm ci --ignore-scripts` (conditional)      | `npx jest --verbose`   |

- `get_sandbox_profile(language)` provides case-insensitive lookup with Python as the default fallback.
- `DEFAULT_PROFILE` is set to the Python profile.

**Design decision:** Used `maven:3.9-openjdk-17-slim` instead of `openjdk:17-slim` because the latter lacks Maven, which is required to run `mvn test`.

**2. Rewrote `server/app/services/docker_client.py`** (replaced stub)

The stub previously returned a hardcoded failure. Now it:
- Accepts `language: str` as the first parameter (instead of `image: str`).
- Resolves a `SandboxProfile` via `get_sandbox_profile(language)`.
- Builds a composite shell command (`sh -c "..."`) with conditional dependency installation guarded by file-existence checks (e.g., `test -f requirements.txt && pip install ... || true`).
- Mounts student repo at `/workspace/student` (read-only) and test suite at `/workspace/tests` (read-only).
- Delegates to `docker_runner.run_container(ContainerConfig)`.
- Converts the 4-field `docker_runner.ContainerResult` to the 3-field `docker_client.ContainerResult`.

**3. Updated `server/app/services/pipeline.py`** (minimal change)

- Removed `_LANGUAGE_IMAGE_MAP`, `_DEFAULT_IMAGE`, and `_eval_image()` (moved to `sandbox_images.py`).
- Changed `run_container()` call to pass the detected `language` string instead of an image string.

**4. Created test files:**

- `server/tests/test_sandbox_images.py` — 17 tests covering profile lookup, fallback, case insensitivity, immutability.
- `server/tests/test_docker_client.py` — 10 tests covering shell command construction, volume mounts, image selection per language, result conversion.

### Test Results

```
tests/test_sandbox_images.py  — 17 passed (+ 8 subtests)
tests/test_docker_client.py   — 10 passed (+ 4 subtests)
tests/test_docker_runner.py   —  7 passed (pre-existing, no regressions)
──────────────────────────────────────────────────────────
Total: 34 passed, 0 failed
```

**Note:** `tests/test_pipeline.py` requires `psycopg2` which is not installed in the local dev environment. This is a pre-existing issue unrelated to this task. The pipeline tests mock `run_container` without asserting on its arguments, so no changes were required.

### Errors Encountered

1. **`pydantic_core.ValidationError` on test collection** — Tests that import from modules touching `config.py` require `DATABASE_URL`, `SECRET_KEY`, and `GITHUB_PAT` environment variables. Resolved by providing dummy values via env vars when running tests locally. Pre-existing issue.

2. **`ModuleNotFoundError: psycopg2`** — Pipeline tests fail to collect because `pipeline.py` imports from `models.database` which uses `psycopg2`. Pre-existing issue; not introduced by this task.

### Files Changed

| File | Action |
|------|--------|
| `server/app/services/sandbox_images.py` | Created |
| `server/app/services/docker_client.py` | Rewritten (stub → real bridge) |
| `server/app/services/pipeline.py` | Updated (removed old image map) |
| `server/tests/test_sandbox_images.py` | Created |
| `server/tests/test_docker_client.py` | Created |

### Spec Traceability

- **Design doc §8:** "Define language-specific base images: Python/Pytest, Java/JUnit, JavaScript/Jest, TypeScript/Jest" — **DONE**
- **Milestone task doc (Task 3):** "Depends on: Docker socket task above (images are pulled/built against the live daemon)" — Docker SDK integration (Task 2) was already complete in `docker_runner.py`; this task wires it through `docker_client.py`.
