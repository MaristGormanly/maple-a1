# MAPLE A1 — UI vs. Spec Audit

**Date:** 2026-04-30  
**Scope:** Angular client (`client/src/`) cross-referenced against `user-stories.md`, `design-doc.md`, `api-spec.md`, `deployment.md`, `instructor-maple-a1-evaluation-instructions.md`, and `docs/resources/maple-a1.md`

---

## Summary Table

| # | Area | Severity | Action needed |
|---|------|----------|---------------|
| 1 | `student_id` submit field | **High** | Remove or make optional; backend doesn't accept it |
| 2 | `/review` endpoint undocumented | **High** | Add to `api-spec.md` |
| 3 | `rubric_digest` only available from POST state | **Medium** | Accept gap or add field to GET response |
| 4 | `review_status` field undocumented | **Medium** | Add to `api-spec.md` and data model |
| 5 | Dashboard uses entirely fixture data | **Medium** | Add UI note or doc that this is static for MVP |
| 6 | Assignment form not wired to backend | **Medium** | Wire to `POST /assignments`; add `rubric_id`; drop `dueDate` |
| 7 | Login not wired to auth endpoint | **Low** | Acceptable with devToken stub; document explicitly |
| 8 | Submission status enum incomplete in design doc | **Low** | Update design-doc data model |
| 9 | `assignment_id` required vs. optional conflict | **Low** | Fix `api-spec.md` to say required |
| 10 | `github_url` vs. `github_repo_url` field name mismatch | **Low** | Normalize field name in spec |
| 11 | Dual `recommendations` shape with ambiguous relationship | **Low** | Clarify in spec whether they're duplicated or distinct |
| 12 | Wrong LLM model names in design doc | **Low** | Fix in `design-doc.md` before Milestone 3 |

---

## Critical — Would Break Against a Real Backend

### 1. `student_id` form field is not an accepted API request field

**File:** `client/src/pages/submit-page/submit-page.component.ts:17`  
**Service:** `client/src/services/evaluation.service.ts:27`

The submit page has a required `studentId` form control. `evaluation.service.ts` appends it to FormData as `student_id`. But `POST /evaluate` (`api-spec.md` §3) only accepts three fields: `github_url`, `assignment_id`, and `rubric`. The `student_id` field does not exist on the request side — it only appears in the *response* because the backend derives it from the JWT `sub` claim.

During MVP, students don't have A1 accounts (design-doc §2 MVP scope note), so there is no student UUID for an instructor to enter. The field is conceptually wrong and will either be silently ignored or rejected by the backend.

**Fix:** Remove the `studentId` form control, or make it optional and remove the `Validators.required` constraint pending a post-MVP student accounts story.

---

### 2. `POST /submissions/{id}/review` endpoint is not in the API spec

**File:** `client/src/services/evaluation.service.ts:81`

`evaluation.service.ts` calls `POST /submissions/{submissionId}/review`. This endpoint is entirely absent from `api-spec.md`. It is a real product requirement (user story #6 — instructor review before release) and the backend will need it, but it is currently undocumented.

**Fix:** Add the endpoint to `api-spec.md` with its request body (`action: 'approve' | 'reject'`, `instructor_notes?: string`) and response shape (`SubmissionStatusData`).

---

## Medium — Missing Functionality or Silent Failures

### 3. `rubric_digest` in status page cannot be polled

**File:** `client/src/utils/api.types.ts:1–9` and `72–81`

`SubmissionData` (POST `/evaluate` response) includes `rubric_digest`. `SubmissionStatusData` (GET `/submissions/{id}` response) does not. The status page shows rubric digest from `history.state.data` passed on navigation from the submit page. If the status page is accessed via direct link, `this.data` is `null` and rubric digest will be blank with no error.

**Fix:** Either accept this gap and omit the rubric digest from the status KV grid, or add `rubric_digest` to the GET response spec and `SubmissionStatusData` type.

---

### 4. `review_status` field is undocumented

**File:** `client/src/utils/api.types.ts:63`, `client/src/pages/status-page/status-page.component.ts:119–123`

`EvaluationResult.review_status` is used to gate the instructor review panel (`showReviewPanel` getter). This field does not appear anywhere in `api-spec.md` or the data model in `design-doc.md §2`. The `EvaluationResult` entity formally lists only `id`, `submission_id`, `deterministic_score`, `ai_feedback_json`, and `metadata_json`. The review panel will silently never appear unless the backend adds this field to its GET response.

**Fix:** Add `review_status` to the `EvaluationResult` data model and document it in `api-spec.md` §7.

---

### 5. Dashboard uses entirely fixture data

**File:** `client/src/pages/dashboard-page/dashboard-page.component.ts`

The dashboard shows a submission table with student names, statuses, and scores, all from inline TypeScript constants. No `GET /submissions` list endpoint exists in the spec. This is intentional for MVP, but the UI gives no indication it is static — instructors interacting with a live backend will see stale fake data with no path to real records.

**Fix:** Either add a note to the UI (e.g., a banner: "Showing sample data — submission list endpoint coming in a future milestone") or scaffold a no-op call that returns an empty state when no endpoint exists.

---

### 6. Assignment form is not wired to the backend

**File:** `client/src/pages/assignment-page/assignment-page.component.ts`

Submitting the assignment creation form sets `saved = true` and displays a hardcoded UUID. `POST /assignments` is fully defined in `api-spec.md` §5 but is never called.

Additionally:
- `rubric_id` (accepted by `POST /assignments`) is absent from the form.
- `dueDate` is in the form but has no counterpart in the API spec or data model.

**Fix:** Wire the form to `POST /assignments` via `EvaluationService`; add a `rubric_id` field (optional UUID); remove `dueDate` unless the data model is extended to include it.

---

## Low — Spec Inconsistencies and Cosmetic Issues

### 7. Login page is not wired to the auth endpoint

**File:** `client/src/pages/login-page/login-page.component.ts`

Both `onSubmit()` and `continueWithSSO()` navigate directly to `/dashboard` without calling `POST /auth/login`. This is acceptable for MVP while `devToken` is in use (CLAUDE.md notes this is a Milestone 2 item), but it should be documented explicitly so it isn't mistaken for a completed auth flow.

---

### 8. Submission status enum is incomplete in the design doc

**Design-doc §2** formally defines the `status` enum as: `Pending`, `Testing`, `Evaluating`, `Completed`, `Failed`.

The frontend additionally handles: `Cloned`, `Cached`, `Awaiting Review`, `EVALUATION_FAILED`.

- `Cloned` and `Cached` appear as status values in the `POST /evaluate` response spec.
- `Awaiting Review` and `EVALUATION_FAILED` appear in `CLAUDE.md` terminal statuses and the design doc AI section, but not in the formal data model enum.

**Fix:** Update the `Submission.status` enum in `design-doc.md §2` to include all six extended values.

---

### 9. `assignment_id` required vs. optional conflict in api-spec.md

`api-spec.md §3` main table lists `assignment_id` as "no" (optional). The embedded duplicate section at line 344 of the same file lists it as "Yes" (required). The design-doc and SRS both show it as required. The UI enforces it as required with UUID pattern validation.

**Fix:** Remove the duplicate section from `api-spec.md` §3 or reconcile both tables to consistently say "required."

---

### 10. `github_url` vs. `github_repo_url` field name inconsistency

`SubmissionData` (POST response, `api.types.ts:3`) uses `github_url`. `SubmissionStatusData` (GET response, `api.types.ts:76`) uses `github_repo_url`. These refer to the same value but have different field names, meaning the status page would need to pull the URL from `this.data?.github_url` (POST state) vs. `this.statusData?.github_repo_url` (GET polling) depending on the code path.

**Fix:** Normalize to one field name across both endpoints in the spec, then update `api.types.ts` accordingly.

---

### 11. Dual `recommendations` shape has ambiguous relationship

`CriterionScore` (`api.types.ts:48`) has a singular `recommendation?: RecommendationObject` on each criterion. `AiFeedback` (`api.types.ts:58`) also has a top-level `recommendations: RecommendationObject[]` array. Design-doc §4 says the model emits one `RecommendationObject` per criterion scoring below Exemplary, which implies the per-criterion field and the top-level array contain the same objects.

The diff viewer consumes only the top-level array. Per-criterion recommendations are not shown in the criteria-scores component. It is unclear whether these are duplicates of the same data or two distinct collections.

**Fix:** Clarify in `design-doc.md §4` whether the top-level `recommendations` array is a flattened copy of per-criterion recommendations or a separate set. Update the TypeScript types to match.

---

### 12. LLM model names in design doc do not exist

`design-doc.md` references `gemini-3.1-pro-preview` and `gemini-3.1-flash-lite`. These identifiers do not exist in Google's Gemini API (current naming: `gemini-2.5-pro`, `gemini-2.0-flash-lite`). No UI impact, but Milestone 3 backend work will fail to initialize these models by name.

**Fix:** Update `design-doc.md §4` with the correct model identifiers before starting Milestone 3 LLM integration.
