# MAPLE A1 — Post-UI Integration Gaps

**Date:** 2026-04-30  
**Context:** The Angular UI prototype has been fully implemented. The backend (Milestones 1–3) and deployment infrastructure (Milestone 4) are largely complete. This document maps every remaining gap between what the UI expects and what the backend currently provides, so remaining work can be planned and assigned.

---

## A — Backend must build (UI is ready and calling these; backend work is outstanding)

### A1. `POST /submissions/{id}/review` endpoint

The instructor review panel on the status page is fully built. When the instructor clicks **Approve** or **Reject**, the frontend calls:

```
POST /api/v1/code-eval/submissions/{submission_id}/review
Authorization: Bearer <jwt>
Content-Type: application/json

{ "action": "approve" | "reject", "instructor_notes": "..." }
```

Expected response: the updated `SubmissionStatusData` envelope (same shape as `GET /submissions/{id}`).

This endpoint does not exist in `api-spec.md` and has not been implemented in FastAPI. Until it exists, the review panel's Approve and Reject buttons will fail silently.

**Work needed:**
- Implement the endpoint in FastAPI with `require_role('Instructor')`
- Add it to `api-spec.md` (see §C below)
- Update `EvaluationResult` to track `review_status` (see A2)

---

### A2. `review_status` field on `EvaluationResult`

The status page gates the entire review panel on:

```typescript
statusData?.evaluation?.review_status === 'pending'
```

This field is not in the `EvaluationResult` data model (`design-doc.md §2`) and is not returned by `GET /submissions/{id}`. Until the backend adds it, the review panel will never appear even when a submission reaches `Awaiting Review` status.

**Work needed:**
- Add `review_status` (enum: `pending` | `approved` | `rejected`) to the `EvaluationResult` schema and Alembic migration
- Return it in the `GET /submissions/{id}` response
- Document it in `design-doc.md §2` and `api-spec.md §7`

---

## B — Frontend needs wiring (backend endpoint exists and is specced; UI is currently stubbed)

### B1. Login page → `POST /auth/login`

The login form collects email and password but navigates directly to `/dashboard` without making any API call. `POST /auth/login` is fully specced and implemented. The `devToken` stub in `environment.ts` masks this gap during development.

**Work needed:**
- Wire `onSubmit()` in `login-page.component.ts` to call `POST /auth/login`
- Store the returned JWT (localStorage or a dedicated `AuthService`)
- Replace the hardcoded `devToken` in `evaluation.service.ts` with the stored token
- Redirect to `/dashboard` on success; show an error banner on `401`

---

### B2. Assignment creation page → `POST /assignments`

The assignment form shows a hardcoded UUID success banner on submit without calling the backend. `POST /assignments` is fully specced.

**Work needed:**
- Add `rubric_id` field to the form (optional UUID — accepted by `POST /assignments` but currently absent)
- Remove the `dueDate` field (not in the API spec or data model)
- Wire `create()` to call `POST /assignments` via a new method in `EvaluationService` (or a dedicated `AssignmentService`)
- Display the real `assignment_id` returned in the response

---

## C — Spec documentation only (no code changes required)

### C1. Add `POST /submissions/{id}/review` to `api-spec.md`

**Endpoint to document:**

| Property | Value |
|---|---|
| Auth required | Yes — Bearer JWT, Instructor role |
| Content-Type | `application/json` |

Request body:

| Field | Type | Required | Notes |
|---|---|---|---|
| `action` | string | yes | `"approve"` or `"reject"` |
| `instructor_notes` | string | no | Shown to student alongside rejection |

Success (200): same `SubmissionStatusData` envelope as `GET /submissions/{id}`, with updated `status` and `evaluation.review_status`.

Errors: `400 VALIDATION_ERROR` (invalid action), `401` (missing/expired JWT), `403 FORBIDDEN` (non-instructor role), `404 NOT_FOUND` (submission not found), `409 CONFLICT` (submission not in `Awaiting Review` state).

---

### C2. Update `Submission.status` enum in `design-doc.md §2`

The formal enum lists: `Pending`, `Testing`, `Evaluating`, `Completed`, `Failed`.

The following values are in active use and need to be added:

| Value | Source |
|---|---|
| `Cloned` | Returned by `POST /evaluate` on fresh clone |
| `Cached` | Returned by `POST /evaluate` on cache hit |
| `Awaiting Review` | Set when AI evaluation completes and instructor review is required |
| `EVALUATION_FAILED` | Set when all LLM retries are exhausted |

---

### C3. Document `review_status` in spec (companion to A2)

Once A2 is implemented, add `review_status` to the `EvaluationResult` description in `design-doc.md §2` and to the `GET /submissions/{id}` response example in `api-spec.md §7`.

---

## D — Deferred (post-MVP / future milestone)

### D1. Dashboard submission list

The dashboard shows fixture data. No `GET /submissions` list endpoint exists in the spec or backend. This is the **Historical grading records** stretch user story.

When this is prioritized, it will require:
- New `GET /submissions` endpoint (filtered by instructor JWT, optionally by status or assignment)
- Updating the dashboard component to call it and replace fixture data
- Adding the endpoint to `api-spec.md`

### D2. `rubric_digest` on the status page

`rubric_digest` is returned by `POST /evaluate` but not by `GET /submissions/{id}`. The status page only shows it when navigating directly from the submit page (via `history.state`). A direct link to `/status/:id` will always show a blank rubric digest.

Fix when convenient: add `rubric_digest` to the `GET /submissions/{id}` response.

---

## Summary

| ID | Work | Type | Blocks |
|----|------|------|--------|
| A1 | Implement `POST /submissions/{id}/review` | Backend | Instructor review flow |
| A2 | Add `review_status` to `EvaluationResult` + GET response | Backend + DB migration | Review panel rendering |
| B1 | Wire login to `POST /auth/login`, replace devToken | Frontend | Real authentication |
| B2 | Wire assignment form to `POST /assignments` | Frontend | Assignment creation |
| C1 | Add review endpoint to `api-spec.md` | Docs | A1 implementation |
| C2 | Update `Submission.status` enum in design doc | Docs | — |
| C3 | Document `review_status` in spec | Docs | A2 implementation |
| D1 | Dashboard list endpoint | Backend + Frontend | Deferred |
| D2 | `rubric_digest` on GET response | Backend | Deferred |
