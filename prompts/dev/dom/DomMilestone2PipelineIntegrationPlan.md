# Dom — Milestone 2 Pipeline Integration Plan

## Context

The [Milestone 2 forensic audit](../../../audits/milestone-02-forensic-audit-2026-04-11.md) identified that the standalone modules (`test_parser.py`, `language_detector.py`, `scoring.py`) existed with tests but were **not wired** into `pipeline.py`. The pipeline was using inline helper functions (`_language_info`, `_minimal_test_results`, `_deterministic_score`) instead of the real services. Additionally, the `POST /evaluate` HTTP response hardcoded `"cached"` / `"cloned"` for `status` even when the async pipeline was dispatched, creating a mismatch between the API response and the DB lifecycle.

Executed from Cursor plan **Dom M2 pipeline integration** (`dom_m2_pipeline_integration_8a63aec5.plan.md`).

## Checklist

1. **Wire services into `pipeline.py`**
   - [x] Import and call `detect_language_version` (replaces `_language_info`)
   - [x] Import and call `parse_test_results` (replaces `_minimal_test_results`)
   - [x] Import and call `calculate_deterministic_score` (replaces `_deterministic_score`)
   - [x] Drive `_eval_image` from detected language (language-to-image map)
   - [x] Remove dead private helpers
   - [x] Set `timeout_seconds=30` (design-doc §8 alignment)

2. **Align `metadata_json` with plan schema**
   - [x] `language`: full dict from `detect_language_version`
   - [x] `exit_code`: container exit code
   - [x] `resource_constraint_metadata`: from parser output
   - [x] `test_summary`: `{framework, passed, failed, errors, skipped}`

3. **Fix `POST /evaluate` response status**
   - [x] Return `"Pending"` in `SubmissionData.status` when `assignment_id` is present
   - [x] Update `docs/api-spec.md` §3 to document `"Pending"` as a valid status value
   - [x] Update integration tests to expect `"Pending"` for assignment flows

4. **Expose evaluation metadata on `GET /submissions/{id}`**
   - [x] Add `evaluation.metadata` with `language` and `test_summary` from stored `metadata_json`
   - [x] Update `docs/api-spec.md` §7 example response

5. **Tests**
   - [x] Update `test_pipeline.py` with parseable pytest fixtures and `detect_language_version` mock
   - [x] Assert `metadata_json` shape (`language`, `exit_code`, `resource_constraint_metadata`, `test_summary`)
   - [x] Full test suite (83 tests) passes

## Out of scope for Dom

- Real Docker SDK integration / volume mounts — remains Jayden's task
- `docker_client.run_container` is still a stub returning `exit_code=1`; the pipeline correctly handles this through the parser and scorer
- Frontend polling and result display — remains Sylvie's task
