# MAPLE A1 — Milestone 3 Forensic Technical Audit
**Date:** 2026-04-19  
**Auditor:** Claude (automated forensic traversal)  
**Scope:** Full codebase alignment with `docs/milestones/milestone-03-tasks.md` and `docs/design-doc.md`

---

## Executive Summary

A comprehensive audit of the MAPLE A1 codebase against Milestone 3 requirements reveals that **Sylvie's 8 tasks (18–25) are fully implemented** and **Dom's 9 tasks (9–17) are also fully implemented** despite being marked `[ ]` in the task file. Jayden's 8 tasks (1–8) remain pending. The codebase is architecturally complete and production-ready for end-to-end M3 execution once Jayden's LLM infrastructure (`llm.complete`, RAG retrieval, linter execution) is implemented. No critical bugs or architectural flaws were detected.

---

## 1. Feature Synthesis & Modular Architecture

### Dependency Map

```
Angular StatusPageComponent
  └── EvaluationService (HTTP)
        └── GET /api/v1/code-eval/submissions/{id}
              └── submissions.py router
                    └── submissions.py service layer
                          └── EvaluationResult model (PostgreSQL)
                                └── ai_feedback_json (JSON column)

POST /evaluate (M2 entry point)
  └── pipeline.py run_pipeline()
        ├── M2 Phase: Docker → test_parser → calculate_score → persist_evaluation_result()
        └── M3 Phase (_run_evaluating_phase):
              ├── ast_chunker.extract_chunks()         [✅ done]
              ├── run_pass1()                           [✅ done — needs llm.complete]
              ├── run_pass2() (conditional)             [✅ done — needs rag_retriever, linter]
              ├── run_pass3()                           [✅ done — needs llm.complete]
              ├── compute_review_flags()                [✅ done]
              └── update_evaluation_result()            [✅ done]
```

### Component Status Summary

| Layer | Module | Status |
|-------|--------|--------|
| Frontend | `CriteriaScoresComponent` | ✅ Complete |
| Frontend | `DiffViewerComponent` | ✅ Complete |
| Frontend | `StatusPageComponent` (review panel, style guide display, polling) | ✅ Complete |
| API | `POST /submissions/{id}/review` | ✅ Complete |
| API | `GET /submissions/{id}` (AI fields, visibility logic) | ✅ Complete |
| Service | `pipeline.py` (M3 orchestration) | ✅ Complete |
| Service | `ai_passes.py` (Pass 1, 2, 3) | ✅ Complete |
| Service | `llm_schemas.py` (JSON schemas) | ✅ Complete |
| Service | `llm_validator.py` (repair retry) | ✅ Complete |
| Service | `review_flags.py` (NEEDS_HUMAN_REVIEW logic) | ✅ Complete |
| Service | `ast_chunker.py` | ✅ Complete |
| Service | `submissions.py` (persist + update) | ✅ Complete |
| Model | `EvaluationResult` (`review_status`, `instructor_notes`) | ✅ Complete |
| Migration | `20260419001_add_review_columns` | ✅ Complete |
| **Infrastructure** | `llm.py` (`complete()` stub) | ❌ Pending (Jayden) |
| **Infrastructure** | `rag_retriever.py` | ❌ Pending (Jayden) |
| **Infrastructure** | `linter.py` / `linter_runner.py` | ❌ Pending (Jayden) |
| **Infrastructure** | pgvector schema (`style_guide_chunks`) | ❌ Pending (Jayden) |

---

## 2. Ambiguities, Predictive Errors, & Interface Mismatches

| Severity | Error Cause | Error Explanation | Origin Location(s) |
|:---------|:-----------|:------------------|:-------------------|
| Low | Recommendations data shape inconsistency | The backend flattens `criteria_scores[].recommendation` into a top-level `recommendations[]` array (submissions.py:118–122). The Angular type `CriterionScore` still has `recommendation?: RecommendationObject` (api.types.ts:48), which is never populated in the API response — the field always arrives as `undefined` on the frontend. The UI uses the flat array (status-page.component.ts:105–107) which works correctly, but the nested field is a dead contract. This is non-breaking now; if a future component tries to read `criterion.recommendation`, it will silently get `undefined`. | `server/app/routers/submissions.py:118–122`, `client/src/utils/api.types.ts:48` |
| Informational | LLM readiness probe uses source inspection | `pipeline.py:97–113` probes `llm.complete` by inspecting its source code for the string `"raise NotImplementedError"`. This is a creative solution but fragile: if Jayden renames the exception or wraps it, the probe misfires and the M3 phase activates against a non-functional stub. | `server/app/services/pipeline.py:97–113` |
| Informational | `"Rejected"` status not in Angular terminal set | `TERMINAL_STATUSES` in `status-page.component.ts:10` does not include `"Rejected"`. After an instructor rejects a submission, a student viewing it would continue polling indefinitely. This is likely intentional (students may not view their own submissions in the current prototype), but worth flagging for M4. | `client/src/pages/status-page/status-page.component.ts:10` |

---

## 3. Ambiguity Resolution & Action Plan

### Issue 1 (Low): Recommendations shape — dead `recommendation` field on `CriterionScore`

**Remediation (when time permits, not blocking M3):**
1. In `server/app/routers/submissions.py:117`, stop stripping `recommendation` from criteria scores — pass it through as-is.
2. The frontend `recommendations[]` getter can then be derived from the criteria scores array: `criteriaScores.filter(c => c.recommendation).map(c => c.recommendation!)`.
3. Remove the separate `recommendations` extraction loop at `submissions.py:118–122`.

**Definition of Done:** `CriterionScore.recommendation` on the Angular side matches the backend object; `api.types.ts` remains unchanged; `DiffViewerComponent` still receives the same flat array.

### Issue 2 (Informational): LLM readiness probe

**Remediation:**
Replace the source-inspection probe with an explicit feature flag:
```python
# In llm.py, add at module level:
LLM_READY = False  # Jayden sets to True when complete() is implemented

# In pipeline.py:
def _is_llm_ready() -> bool:
    return getattr(llm, "LLM_READY", False)
```

**Definition of Done:** No `inspect` usage; probe is a simple boolean attribute check.

---

## 4. Security & Vulnerability Assessment

### JWT Role Enforcement — `POST /submissions/{id}/review`

**Code (`server/app/routers/submissions.py:144`):**
```python
current_user: dict = Depends(require_role("Instructor"))
```
✅ Enforced. Only users with the `Instructor` role can reach this endpoint.

### Ownership Validation

**Code (`server/app/routers/submissions.py:170`):**
```python
if submission.assignment.instructor_id != current_user_id:
    return error_response(403, "FORBIDDEN", "...")
```
✅ An instructor can only review submissions for their own assignments. Cross-assignment manipulation is blocked.

### State Machine Integrity

**Code (`server/app/routers/submissions.py:173–178`):**
```python
if submission.status != "Awaiting Review":
    return error_response(400, "VALIDATION_ERROR", ...)
```
✅ Prevents approve/reject on already-completed, failed, or pending submissions.

### Input Validation

**Code (`server/app/routers/submissions.py:18–20`):**
```python
class ReviewRequest(BaseModel):
    action: Literal["approve", "reject"]
    instructor_notes: str | None = None
```
✅ Pydantic enforces enum. No free-form action strings accepted.

### Secret Handling

- `llm.py` applies `redact()` and `redact_dict()` before all external LLM calls — strips GitHub PATs, email addresses, and env var values.
- Angular `environment.ts` uses `devToken` from environment module, not hardcoded in service files.
- No hardcoded credentials found in any source file.

✅ Secret handling is correct.

### Potential Concern: Student Access to AI Feedback

**Code (`server/app/routers/submissions.py:116`):**
```python
viewer_is_privileged = role in {"Instructor", "Admin"}
show_ai = viewer_is_privileged or er.review_status == "approved"
```
✅ Students only see AI feedback after instructor approval. `review_status` defaults to `"pending"`, so feedback is gated by default.

---

## 5. Efficiency & Optimization Recommendations

### 5.1 Eager Loading on GET /submissions/{id}

**Location:** `server/app/routers/submissions.py:55–70`

The current query loads `Submission` and then accesses `submission.evaluation_result` and `submission.assignment` as lazy-loaded relationships. Under async SQLAlchemy this triggers N+1 implicit awaits.

**Low-Risk Recommendation:** Add `selectinload` options to the initial query:
```python
from sqlalchemy.orm import selectinload

result = await db.execute(
    select(Submission)
    .where(Submission.submission_id == submission_id)
    .options(
        selectinload(Submission.evaluation_result),
        selectinload(Submission.assignment),
    )
)
```
**Risk:** None — purely additive; removes implicit lazy-load round trips.

### 5.2 Pipeline LLM Readiness Probe (addressed above)

Source inspection (`inspect.getsource`) is slightly expensive. Replacing it with a module-level flag (see Section 3) eliminates the call entirely.

### 5.3 Chunk Cap in AST Chunker

**Location:** `server/app/services/pipeline.py:82` — `_MAX_CHUNKS_PER_REPO = 200`

This is a reasonable cap but is a magic number. It should be a configurable setting via `pydantic-settings` / `.env` so instructors with large repos can tune it without a code change.

**Risk:** None — additive config option.

---

## 6. Task Completion Verification — Checkbox Update Required

The following tasks are **implemented in code but incorrectly marked `[ ]`** in `docs/milestones/milestone-03-tasks.md`. They should be updated to `[x]`:

| # | Task | Evidence |
|---|------|----------|
| 9 | JSON schemas for pass outputs | `server/app/services/llm_schemas.py` — all three pass schemas + RecommendationObject schema defined |
| 10 | Schema validation + repair retry | `server/app/services/llm_validator.py` — `validate_and_repair()` with one-shot retry and `EvaluationFailedError` |
| 11 | Pass 1 test reconciliation | `server/app/services/ai_passes.py:199` — fully implemented |
| 12 | AST-aware code chunk extraction | `server/app/services/ast_chunker.py` — `CodeChunk` + `extract_chunks()` with Python AST + regex fallback |
| 13 | Pass 2 style review (conditional) | `server/app/services/ai_passes.py:441` — skip logic, RAG hook, Pass 2 schema validation |
| 14 | Pass 3 synthesis | `server/app/services/ai_passes.py:711` — recommendation validation, uncertainty preservation, schema validation |
| 15 | `NEEDS_HUMAN_REVIEW` flag logic | `server/app/services/review_flags.py:58` — all four trigger conditions implemented |
| 16 | Pipeline orchestration (AI passes) | `server/app/services/pipeline.py:233` — full M3 evaluating phase with error handling |
| 17 | Update `persist_evaluation_result` | `server/app/services/submissions.py:57, 116` — both `persist` and `update` functions |

**Tasks correctly marked `[ ]` (genuinely pending — Jayden's scope):** 1–8

**Tasks correctly marked `[x]` (Sylvie's scope):** 18–25

---

## 7. Conclusion

**The MAPLE A1 Milestone 3 codebase is architecturally complete.** All pipeline logic, API contracts, data models, and Angular UI components have been implemented and are integration-ready.

The sole remaining work is Jayden's infrastructure layer:
1. `services/llm.py` — `complete()` with retry, fallback chain, and timeouts
2. `services/rag_retriever.py` — cosine similarity retrieval against pgvector
3. `services/linter.py` — `pylint`/`eslint` execution inside Docker containers
4. Alembic migration — `style_guide_chunks` table with pgvector extension
5. Docker base images — `pylint`/`eslint` pre-installed

Once those five components are implemented, the `_is_llm_ready()` probe in `pipeline.py:97` will activate the M3 evaluating phase automatically — no other integration work is required.
