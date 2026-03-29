# Milestone 1 SHA + Rubric Digest Cache Key Prompts

## Purpose

This file contains ready-to-use prompts for Milestone 1, Task 3:

- Implement `SHA + normalized rubric digest` caching key; skip re-cloning on cache hit

These prompts are designed to keep implementation aligned with:

- `docs/milestones/milestone-01-tasks.md`
- `docs/design-doc.md`
- `milestone-01-pat-cloning-process.md`
- `milestone-01-repository-preprocessor-prompts.md`

The goal is to add caching to the repository ingestion flow without drifting beyond the current Milestone 1 scope.

---

## Prompt 1: Read Requirements And Plan

Use this first to make the assistant gather context before editing code.

```text
Read these files carefully and summarize the exact requirements for Milestone 1, Task 3:

- docs/milestones/milestone-01-tasks.md
- docs/design-doc.md
- milestone-01-pat-cloning-process.md
- milestone-01-repository-preprocessor-prompts.md
- server/app/main.py
- server/app/preprocessing.py
- server/app/config.py

Focus only on the caching requirement:
- implement a cache key based on commit SHA + normalized teacher-rubric digest
- skip re-cloning when that cache key is already available

Then produce:
1. A short summary of the required behavior
2. A list of files you expect to create or edit
3. A concise implementation plan
4. Any ambiguities or risks

Important constraints:
- Stay within Milestone 1 scope
- Do not add AI grading, Docker execution, or broad database work just for this task
- Preserve the current Task 1 clone contract unless the docs clearly justify a change
- Preserve compatibility with later persistence, evaluation, and polling work
- If the docs use `assignment_id` in one place and a teacher-supplied rubric in another, call that out explicitly and propose the most Milestone-accurate resolution before editing
- Do not invent or hardcode a temporary internal `rubric_id` when a rubric fingerprint would be more accurate to the teacher-driven review flow
```

---

## Prompt 2: Implement The Cache Key

Use this after the planning prompt.

```text
Implement Milestone 1, Task 3: SHA + normalized rubric digest caching key with clone-skip behavior on cache hit.

Requirements:
- Build a cache key from the repository commit SHA and a normalized fingerprint of the teacher-supplied rubric
- Avoid re-cloning and re-preprocessing when the same SHA + rubric combination has already been processed
- Keep the implementation deterministic and easy to inspect locally
- Keep the implementation safe for private GitHub repositories

Design expectations:
- Resolve the repository commit SHA before deciding whether to clone when possible
- Do not satisfy the cache requirement with a cache check that only runs after a fresh clone
- Use a dedicated caching utility/module instead of burying all logic inside the route handler
- Store enough metadata to identify cache hits clearly and support later extension
- Keep names, structure, and return values clear and testable
- Do not expose secrets or log PATs

Milestone alignment:
- Students currently submit `github_url` and an assignment context, but the review flow may also need a teacher-supplied rubric payload
- The cache key should use `SHA + normalized rubric digest`
- If the rubric is supplied live at evaluation time, fingerprint that payload instead of guessing an internal `rubric_id`
- Keep any optional assignment context separate from the rubric fingerprint logic

Implementation guidance:
- Decide how to resolve the commit SHA without performing a full clone on every request
- Decide where cache metadata should live for Milestone 1, for example a local JSON index or other lightweight store
- Keep cache-hit behavior explicit:
  - what data is returned
  - what status is returned
  - whether the existing local processed repo path is reused
- Keep cache-miss behavior compatible with the existing clone + preprocess flow

After implementation:
- Run lint or diagnostics for changed files
- Run a lightweight verification showing both cache miss and cache hit behavior
- Summarize exactly what changed
```

---

## Prompt 3: Integrate Without Breaking Tasks 1 And 2

Use this if you want the assistant to connect the cache into the current ingestion flow carefully.

```text
Integrate the SHA + normalized rubric digest cache into the existing Milestone 1 backend flow without breaking:
- Task 1: PAT-based repository cloning
- Task 2: repository preprocessing

Current behavior to preserve:
- repositories can still be validated and cloned securely
- the checked-out commit hash is still captured correctly
- preprocessing still runs on cache misses

Integration guidance:
- Decide where the cache check belongs in the flow:
  1. before clone, after remote SHA resolution
  2. after clone, using the cloned SHA
  3. a hybrid approach

Use the requirements docs to justify the choice before editing.

Important:
- Prefer the approach that actually allows skipping re-cloning on cache hit
- If the current route contract needs to change, explain why and keep the response structured
- If the docs conflict about `assignment_id` versus a teacher-supplied rubric payload, call out the conflict and choose the more Milestone-accurate implementation path
- Do not silently introduce persistence assumptions that depend on unfinished teammate work

After changes:
- Verify cache miss behavior still clones and preprocesses correctly
- Verify cache hit behavior skips clone/preprocess correctly
- Verify the route response still matches the intended Milestone 1 contract as closely as possible
```

---

## Prompt 4: Add Tests For Cache Hits And Misses

Use this if you want the assistant to create repeatable tests instead of only ad hoc checks.

```text
Add automated tests for the Milestone 1 SHA + normalized rubric digest caching behavior.

Test scenarios should include:
1. Cache miss: no existing entry, so the repository is validated, cloned, and preprocessed
2. Cache hit: same commit SHA and same normalized rubric digest, so clone/preprocess are skipped
3. Cache miss when commit SHA changes
4. Cache miss when rubric content changes but commit SHA stays the same
5. Invalid or unreadable cache metadata case
6. Response contract remains structured on both hit and miss

Constraints:
- Keep tests lightweight and local
- Do not require Docker
- Do not require live GitHub network calls for unit-level tests
- Prefer mocks and deterministic fixtures over external dependencies
- Add only the smallest reasonable test surface that materially reduces regression risk

If the repository does not yet have a cache metadata structure, create the smallest reasonable one for this task.
Then run the tests and report the results.
```

---

## Prompt 5: Review For Spec Alignment

Use this after implementation and testing.

```text
Review the SHA + normalized rubric digest cache implementation against these requirement sources:

- docs/milestones/milestone-01-tasks.md
- docs/design-doc.md
- milestone-01-pat-cloning-process.md

Focus on:
- whether the cache key truly uses commit SHA + normalized rubric digest
- whether cache hits skip re-cloning as required
- whether preprocessing is skipped only when appropriate
- whether the implementation stays within Milestone 1 scope
- whether the implementation remains compatible with later persistence and evaluation work
- whether tests cover the meaningful hit/miss and mismatch cases

Return:
1. Findings first, ordered by severity
2. Any requirement mismatches
3. Residual risks
4. A brief final verdict on whether Task 3 is complete
```

---

## One-Shot Prompt

Use this if you want a single prompt instead of the staged workflow above.

```text
Implement Milestone 1, Task 3: SHA + normalized rubric digest caching key so the system skips re-cloning on cache hit.

Before editing, read:
- docs/milestones/milestone-01-tasks.md
- docs/design-doc.md
- milestone-01-pat-cloning-process.md
- milestone-01-repository-preprocessor-prompts.md
- server/app/main.py
- server/app/preprocessing.py

Then:
1. Summarize the exact Task 3 requirements
2. Explain how the current flow can determine commit SHA early enough to avoid unnecessary re-clones
3. Resolve the `assignment_id` versus teacher-supplied rubric requirement mismatch explicitly before coding
4. Implement the caching logic in a dedicated backend utility/module
5. Integrate it into the current ingestion flow in the most Milestone-accurate way
6. Add or run lightweight tests that verify cache miss and cache hit behavior
7. Check lint/diagnostics for changed files
8. Report any remaining requirement gaps

Constraints:
- Stay within Milestone 1 scope only
- Do not add AI grading, Docker execution, or unrelated database work
- Do not break the existing clone/preprocess behavior on cache misses
- Keep secrets out of logs and out of cache metadata
- Prefer deterministic local cache metadata over speculative infrastructure dependencies
- Call out any doc conflict instead of guessing
```
