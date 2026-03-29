# Sylvie Milestone 1 Checkpoint Summary

## Context and Scope

This checkpoint summarizes the work completed during this session for **Sylvie's portion of Milestone 1** of MAPLE A1. The scope of this work is the **repository ingestion pipeline and related backend contract alignment**, not the full milestone across the entire team.

Two scope boundaries are especially important:

1. **The Angular framework work for Sylvie's milestone responsibilities has not been completed in this session.** The backend ingestion pipeline is in good shape, but the Angular scaffold that would let a student submit through the UI is still outstanding.
2. **Student/source intake still happens through a GitHub repository URL, not direct raw code submission.** The backend is now aligned to teacher-provided rubric content at evaluation time, but the student code itself is still sourced from a GitHub repository clone.

This distinction matters because the current code now reflects a more accurate grading contract for rubric handling, while still preserving the Milestone 1 ingestion model of repository-based submission.

## Core Changes Made in This Session

## 1. Evaluation Contract Was Refactored to Accept Teacher-Provided Rubric Content

The `POST /api/v1/code-eval/evaluate` request model was updated so the backend now expects a required `rubric` payload directly in the evaluation request.

The route now accepts:

- `github_url`
- optional `assignment_id`
- teacher-provided `rubric`

This is a significant contract correction because it removes the assumption that the backend must already know a pre-standardized rubric through an internal ID. Instead, the backend can now evaluate the submission using the rubric content actually provided for that review event.

This change was needed because the previous request shape did not reflect the teacher-driven review workflow described in the discussion. The corrected contract better matches the real grading premise: the rubric used for evaluation is part of the review input, not just an internal lookup artifact.

## 2. Rubric Fingerprinting Replaced Internal `rubric_id` Cache Coupling

One of the most important functional changes in this session is the new caching strategy:

- **Milestone 1 now accepts teacher-provided rubric content at evaluation time and fingerprints that rubric for caching, so cache reuse is based on `commit_sha + rubric_digest` rather than an internal `rubric_id`.**

The backend now computes a normalized rubric fingerprint and uses the resulting digest in the repository cache key.

This was implemented in the cache utility layer, where rubric content is normalized and hashed before the cache key is built.

That means the cache key now reflects:

- the exact repository version being evaluated, via commit SHA
- the effective rubric content being used for that evaluation, via rubric digest

This is much more accurate for the real workflow than using an internal `rubric_id`, because a teacher can provide a revised rubric even if no internal registry entry has changed.

## 3. Rubric Normalization Logic Was Added

To support reliable caching, rubric content is normalized before hashing.

This includes:

- whitespace canonicalization for plain-text rubric input
- canonical JSON serialization for object/list rubric input
- stable digest generation from normalized content

This matters because caching should not miss or duplicate entries due to irrelevant formatting differences. Two semantically identical rubrics with different key order or extra whitespace should produce the same digest whenever possible.

The normalization metadata is also stored in cache metadata so future work can understand how the digest was derived.

## 4. The Old Assignment-to-Rubric Registry Assumption Was Removed

The previous milestone-only local abstraction that resolved an internal rubric identity from assignment data was removed from the active path.

This is important because it eliminates an implementation detail that no longer matched the corrected workflow. Instead of pretending a rubric identity already exists before evaluation, the backend now derives a rubric fingerprint from the actual rubric content supplied at request time.

This simplifies the mental model of the pipeline:

- assignment context may still exist
- rubric input is now explicit
- cache behavior is based on real evaluation inputs

## 5. Response Data Was Updated to Expose the Effective Rubric Fingerprint

The success response now includes:

- `assignment_id`
- `rubric_digest`
- `commit_hash`
- `local_repo_path`
- `status`

This improves observability for Milestone 1 and makes it easier to understand why a cache hit occurred. It also gives future stages of the pipeline a stable identifier for the rubric content actually used in the run.

## 6. Documentation Was Corrected to Match the Actual Backend Contract

The following documentation was updated during this session so the written design better matches the implemented ingestion path:

- `docs/design-doc.md`
- `docs/resources/maple-a1.md`
- `docs/milestones/milestone-01-tasks.md`
- `milestone-01-cache-key-prompts.md`

These changes were necessary because the docs had drifted in a few ways:

- some sections still described evaluation in terms of `rubric_id`
- some examples still implied old response shapes
- one SRS resource claimed `/evaluate` accepted raw content, which is **not true in the current backend**

The docs now more clearly distinguish:

- external rubric standards supplied by teachers
- internal technical standards from style guides
- repository-based code intake in Milestone 1

---

## Important Architectural Clarification Added in This Session

This session also clarified a conceptual distinction that future work needs to preserve:

- **External evaluation standards** come from the teacher-provided rubric submitted at evaluation time.
- **Internal technical standards** come from style guides and linter/rule systems that will be implemented in later milestones.

This means the rubric and the style-guide system are not the same thing.

The backend now reflects that distinction more clearly:

- the evaluation route accepts the teacher's rubric
- the cache fingerprints that teacher rubric
- style-guide-based internal standards remain a later concern

This should prevent future confusion where rubric scoring rules and code-quality/style standards get collapsed into the same concept.

To explicitly preserve this point for future context:

**Internal technical standards from style guides remain a separate concern for later milestones.**

---

## How This Connects to the SRS and Design Specs

This session's work supports the SRS and design materials in several concrete ways.

## Repository Ingestion Alignment

The design documentation for Milestone 1 and the ingestion pipeline requires that the system:

- validate GitHub repository access
- clone the repository securely with a GitHub PAT
- strip unnecessary files before downstream analysis
- avoid redundant work with SHA-based caching

This session preserved and strengthened that ingestion path.

## Rubric-Grounded Evaluation Alignment

The broader system specification expects evaluation to be grounded in rubric criteria. This session improved that alignment by ensuring the rubric used for evaluation is supplied directly and fingerprinted as part of the run, rather than being treated as an opaque pre-existing internal identifier.

That makes the implementation more faithful to the actual evaluation semantics: grading depends on the rubric content, not merely a stored label.

## Reliability and Cost Alignment

The design docs emphasize caching as an important performance and budget control measure. By basing the cache on `commit_sha + rubric_digest`, the system now avoids unnecessary re-cloning and future re-evaluation when both the repository content and rubric content are unchanged.

That is especially important for later AI-assisted milestones, because cache reuse will help reduce repeated downstream work and cost.

## Accurate Scope Alignment

The updated documentation now makes it clearer that the current implementation is still:

- repository-based for student/source intake
- not yet raw-content based
- not yet style-guide enforced
- not yet the Angular submission UI

This is valuable because it keeps the implementation honest relative to both the SRS and the milestone boundaries.

---

## How Future Features Need to Interact With This Work

Future milestones should build on this session's changes rather than bypass them.

## 1. Future Evaluation and AI Pipeline Work Must Use the Teacher-Supplied Rubric Path

Any later grading stages, including deterministic scoring and LLM-based evaluation, should treat the request-provided rubric as the authoritative external grading standard for that run.

They should not reintroduce a hidden dependency on a mandatory internal `rubric_id` unless that value is derived after normalization and remains clearly secondary to the actual rubric content.

If a future standardized rubric persistence layer is added, it should still preserve this logic:

- live rubric input can be normalized
- normalized rubric can optionally be stored
- caching and evaluation should remain grounded in effective rubric content

## 2. Future Cache-Aware Features Must Respect `commit_sha + rubric_digest`

Any future reuse of repository artifacts, test results, or evaluation outputs should be careful to key off the same semantic identity:

- the exact student repository revision
- the exact rubric content used

If future code adds only `assignment_id`-based reuse without considering rubric digest, it could accidentally return stale grading results for a changed rubric.

## 3. Future Style-Guide/Lint Features Must Stay Separate From Rubric Fingerprinting

When style-guide enforcement and internal technical standards are implemented in later milestones, that logic should be treated as a distinct subsystem.

It may influence evaluation, but it should not erase the distinction between:

- rubric-defined course expectations
- language/style-guide technical standards

If future evaluation combines both, it should do so explicitly and transparently.

## 4. Future Raw Code Submission Support Should Extend, Not Replace, Current Intake Semantics

At this stage, **student/source intake still occurs through a GitHub repository URL rather than direct raw code submission**.

If a future milestone adds raw source upload or pasted source content, that new intake path should still integrate with the same downstream concepts:

- preprocessing or source normalization
- rubric fingerprinting
- cache identity tied to code state plus rubric state

In other words, the code-intake mechanism may change later, but the corrected rubric contract established in this session should remain intact.

---

## Testing and Validation Completed

The work completed in this session was reviewed and verified against the current backend test suite.

The relevant tests cover:

- invalid GitHub URL rejection
- missing GitHub PAT behavior
- invalid/expired PAT handling
- inaccessible repository handling
- empty teacher rubric rejection
- cache miss behavior
- cache hit behavior
- cache invalidation when commit SHA changes
- cache invalidation when teacher rubric content changes
- unreadable cache metadata
- preprocessing error handling
- clone failure handling
- preprocessing path stripping for ignored directories and compiled artifacts

The current server tests passed successfully during session verification.

This is especially important because the contract change was not just cosmetic. It affected:

- request validation
- cache key semantics
- cache metadata
- route responses
- documentation assumptions

The tests help confirm that the route still behaves correctly while using the new rubric-driven caching model.

---

## Remaining Incomplete or Deferred Items

The following items are intentionally not being claimed as completed by this checkpoint:

- **Angular scaffold work is not complete.**
- direct raw code submission is not implemented
- later style-guide-based internal standards are not implemented
- later deterministic execution and AI evaluation stages are not implemented as part of this ingestion checkpoint

This checkpoint should therefore be understood as:

- a strong completion point for **Sylvie's backend ingestion responsibilities**
- a clarification and correction of the rubric/caching contract
- not a claim that the entire project or full milestone is complete

---

## Final Summary

During this session, Sylvie's Milestone 1 ingestion work was brought into better alignment with the actual teacher-driven grading workflow. The key correction was moving away from an internal `rubric_id` assumption and toward teacher-provided rubric content submitted at evaluation time. The backend now fingerprints that rubric and uses `commit_sha + rubric_digest` as the effective cache identity. This makes cache reuse reflect the real grading inputs rather than an internal milestone placeholder.

At the same time, the implementation preserved the current Milestone 1 ingestion model:

- repository intake still starts from a GitHub URL
- the repository is validated and cloned securely with a PAT
- preprocessing strips irrelevant directories and compiled artifacts
- cache hits skip unnecessary clone/preprocess work

Just as importantly, the session clarified the distinction between external rubric standards and internal technical standards from style guides, ensuring that later milestones can add style review without collapsing it into rubric identity.

To restate the two most important submission notes clearly:

1. **I have not completed the Angular framework that is required to complete my milestone.**
2. **Milestone 1 now accepts teacher-provided rubric content at evaluation time and fingerprints that rubric for caching, so cache reuse is based on `commit_sha + rubric_digest` rather than an internal `rubric_id`. Internal technical standards from style guides remain a separate concern for later milestones. At this stage, student/source intake still occurs through a GitHub repository URL rather than direct raw code submission.**
