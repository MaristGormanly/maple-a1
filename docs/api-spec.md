# MAPLE A1 — API Specification

> **Base path:** `/api/v1/code-eval`
> **Content-Type (default):** `application/json` unless noted otherwise
> **Auth mechanism:** Bearer JWT in `Authorization` header (issued by `POST /auth/login`)

---

## Response Envelope

Every response follows the MAPLE standard envelope:

```json
{
  "success": true | false,
  "data": { ... } | null,
  "error": null | { "code": "ERROR_CODE", "message": "Human-readable detail" },
  "metadata": {
    "timestamp": "ISO-8601 UTC",
    "module": "a1",
    "version": "1.0.0"
  }
}
```

- On success: `success` is `true`, `data` contains the payload, `error` is `null`.
- On failure: `success` is `false`, `data` is `null`, `error` contains `code` and `message`.

---

## Endpoints

### 1. `POST /auth/register`

Creates a new user account.

| Property | Value |
|---|---|
| Auth required | No |
| Content-Type | `application/json` |

**Request body:**

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `email` | string | yes | — | Must be unique across all users |
| `password` | string | yes | — | Stored as bcrypt hash |
| `role` | string | no | `"Student"` | e.g. `"Student"`, `"Instructor"` |

**Success (200):**

```json
{
  "success": true,
  "data": {
    "user_id": "b7e2c4a0-...",
    "email": "student@example.com",
    "role": "Student"
  },
  "error": null,
  "metadata": { "timestamp": "...", "module": "a1", "version": "1.0.0" }
}
```

**Errors:**

| Status | Code | Condition |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Missing or malformed fields (Pydantic) |
| 409 | `CONFLICT` | Email already registered |

---

### 2. `POST /auth/login`

Authenticates a user and returns a JWT.

| Property | Value |
|---|---|
| Auth required | No |
| Content-Type | `application/json` |

**Request body:**

| Field | Type | Required |
|---|---|---|
| `email` | string | yes |
| `password` | string | yes |

**Success (200):**

```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer"
  },
  "error": null,
  "metadata": { "timestamp": "...", "module": "a1", "version": "1.0.0" }
}
```

**Errors:**

| Status | Code | Condition |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Missing or malformed fields (Pydantic) |
| 401 | `AUTH_ERROR` | Email not found, no password set, or wrong password |

---

### 3. `POST /evaluate`

Submits a GitHub repository for evaluation against a teacher-provided rubric.
The `submission_id` in the response is a **UUID backed by the database** (not ephemeral).

| Property | Value |
|---|---|
| Auth required | **Yes** — Bearer JWT |
| Content-Type | **`multipart/form-data`** |

**Form fields:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `github_url` | string | yes | Must be a valid `github.com` URL |
| `assignment_id` | string | no | UUID of a previously created assignment; validated for format and existence |
| `rubric` | file | yes | UTF-8 text or JSON file (uploaded as `application/json`) |

**Success (200):**

```json
{
  "success": true,
  "data": {
    "submission_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "github_url": "https://github.com/student/example-assignment",
    "assignment_id": "11111111-2222-3333-4444-555555555555",
    "rubric_digest": "sha256:abcdef...",
    "status": "cloned",
    "local_repo_path": "server/repos/student/example-assignment/abc123-...",
    "commit_hash": "abc123def456..."
  },
  "error": null,
  "metadata": { "timestamp": "...", "module": "a1", "version": "1.0.0" }
}
```

`status` is either `"cloned"` (fresh clone) or `"cached"` (cache hit).
`assignment_id` is `null` when omitted from the request.

**Errors:**

| Status | Code | Condition |
|---|---|---|
| 400 | `VALIDATION_ERROR` | `github_url` is not a valid URL or not a `github.com` URL |
| 400 | `VALIDATION_ERROR` | `rubric` is empty, not UTF-8, or fails fingerprinting |
| 400 | `VALIDATION_ERROR` | `assignment_id` is present but not a valid UUID |
| 401 | `AUTH_ERROR` | JWT missing, expired, or `sub` claim is not a valid UUID |
| 401 | `AUTHENTICATION_ERROR` | `GITHUB_PAT` is invalid or expired |
| 404 | `NOT_FOUND` | `assignment_id` UUID is valid but no matching assignment exists |
| 500 | `CONFIGURATION_ERROR` | `GITHUB_PAT` env var is not set |
| 500 | `CACHE_ERROR` | Cache index is corrupt or unwritable |
| 500 | `PREPROCESSING_ERROR` | Repository cleanup/preprocessing failed |
| 502 | `CLONE_ERROR` | `git clone` failed |

---

### 4. `POST /rubrics`

Creates a rubric definition for use in evaluations.

| Property | Value |
|---|---|
| Auth required | No |
| Content-Type | `application/json` |

**Request body:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `rubric_id` | string | no | Client-supplied UUID; server generates one if omitted |
| `title` | string | yes | |
| `total_points` | integer | yes | Must equal the sum of all criteria `max_points` |
| `criteria` | array | yes | At least one `RubricCriterion` object |

Each **`RubricCriterion`**:

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | yes | |
| `max_points` | integer | yes | |
| `levels` | array | yes | At least one `RubricLevel` object |

Each **`RubricLevel`**:

| Field | Type | Required |
|---|---|---|
| `label` | string | yes |
| `points` | integer | yes |
| `description` | string | yes |

**Success (200):**

```json
{
  "success": true,
  "data": {
    "rubric_id": "d4f8a1c2-...",
    "title": "Assignment 1 Review",
    "criteria_count": 3
  },
  "error": null,
  "metadata": { "timestamp": "...", "module": "a1", "version": "1.0.0" }
}
```

**Errors:**

| Status | Code | Condition |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Missing/malformed fields, `rubric_id` is not a valid UUID, or `criteria max_points` sum ≠ `total_points` |
| 409 | `CONFLICT` | A rubric with the given `rubric_id` already exists |

---

### 5. `POST /assignments`

Creates an assignment definition.

| Property | Value |
|---|---|
| Auth required | **Yes** — Bearer JWT |
| Content-Type | `application/json` |

**Request body:**

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `title` | string | yes | — | |
| `test_suite_repo_url` | string | no | `null` | URL to a test suite repository |
| `rubric_id` | string | no | `null` | UUID referencing a previously created rubric |
| `enable_lint_review` | boolean | no | `false` | |
| `language_override` | string | no | `null` | |

The `instructor_id` is extracted from the JWT `sub` claim automatically.

**Success (200):**

```json
{
  "success": true,
  "data": {
    "assignment_id": "a1b2c3d4-...",
    "title": "Homework 3",
    "instructor_id": "b7e2c4a0-...",
    "test_suite_repo_url": null,
    "rubric_id": "d4f8a1c2-...",
    "enable_lint_review": false,
    "language_override": null
  },
  "error": null,
  "metadata": { "timestamp": "...", "module": "a1", "version": "1.0.0" }
}
```

**Errors:**

| Status | Code | Condition |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Missing/malformed fields or `rubric_id` is not a valid UUID |
| 401 | — | JWT missing or expired (FastAPI default 401) |

---

### 6. `GET /assignments/{assignment_id}`

Retrieves a single assignment by ID.

| Property | Value |
|---|---|
| Auth required | **Yes** — Bearer JWT |

**Path parameters:**

| Param | Type | Notes |
|---|---|---|
| `assignment_id` | string | Must be a valid UUID |

**Success (200):**

```json
{
  "success": true,
  "data": {
    "assignment_id": "a1b2c3d4-...",
    "title": "Homework 3",
    "instructor_id": "b7e2c4a0-...",
    "test_suite_repo_url": null,
    "rubric_id": "d4f8a1c2-...",
    "enable_lint_review": false,
    "language_override": null
  },
  "error": null,
  "metadata": { "timestamp": "...", "module": "a1", "version": "1.0.0" }
}
```

**Errors:**

| Status | Code | Condition |
|---|---|---|
| 400 | `VALIDATION_ERROR` | `assignment_id` is not a valid UUID |
| 401 | — | JWT missing or expired |
| 404 | `NOT_FOUND` | No assignment with the given ID |

---

### 7. `GET /submissions/{submission_id}`

Retrieves a submission and its evaluation result (if available).
The `submission_id` is a **UUID** (database primary key), as returned by `POST /evaluate`.

| Property | Value |
|---|---|
| Auth required | **Yes** — Bearer JWT |

**Path parameters:**

| Param | Type | Notes |
|---|---|---|
| `submission_id` | string | Must be a valid UUID |

**Success (200) — without evaluation:**

```json
{
  "success": true,
  "data": {
    "submission_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "assignment_id": "11111111-2222-3333-4444-555555555555",
    "student_id": "b7e2c4a0-...",
    "github_repo_url": "https://github.com/student/example-assignment",
    "commit_hash": "abc123def456...",
    "status": "cloned",
    "created_at": "2026-03-28T12:00:00+00:00"
  },
  "error": null,
  "metadata": { "timestamp": "...", "module": "a1", "version": "1.0.0" }
}
```

**Success (200) — with evaluation:**

When an `EvaluationResult` is associated, the response includes an `evaluation` key:

```json
{
  "success": true,
  "data": {
    "submission_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "assignment_id": "11111111-2222-3333-4444-555555555555",
    "student_id": "b7e2c4a0-...",
    "github_repo_url": "https://github.com/student/example-assignment",
    "commit_hash": "abc123def456...",
    "status": "evaluated",
    "created_at": "2026-03-28T12:00:00+00:00",
    "evaluation": {
      "deterministic_score": 85,
      "ai_feedback": { "summary": "Good work overall..." }
    }
  },
  "error": null,
  "metadata": { "timestamp": "...", "module": "a1", "version": "1.0.0" }
}
```

**Errors:**

| Status | Code | Condition |
|---|---|---|
| 400 | `VALIDATION_ERROR` | `submission_id` is not a valid UUID |
| 401 | — | JWT missing or expired |
| 404 | `NOT_FOUND` | No submission with the given ID |

---

### 8. `GET /health`

Returns service liveness status. No authentication required.

| Property | Value |
|---|---|
| Auth required | No |

**Success (200):**

```json
{
  "success": true,
  "data": {
    "status": "ok",
    "environment": "development"
  },
  "error": null,
  "metadata": { "timestamp": "...", "module": "a1", "version": "1.0.0" }
}
```

`environment` reflects the `APP_ENV` setting (e.g. `"development"`, `"production"`).
