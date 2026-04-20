# Delegate: Draft `milestone-02-tasks.md` (requirements-only)

## Role

You are a technical lead drafting a **work breakdown** for **Milestone 2** of MAPLE A1. You produce a single markdown document that engineers can execute without guessing scope.

## Single deliverable

Create `**docs/milestones/milestone-02-tasks.md`** (new file).  
Do **not** modify `docs/design-doc.md`, `docs/api-spec.md`, Milestone 1 task files, or application code.

## Sources of truth (hard constraint)

1. **Read in full** (or systematically enough that no requirement in scope is missed):
  - `docs/design-doc.md`
  - `docs/api-spec.md`
2. **Do not** invent requirements, stretch goals, or implementation details that are **not** stated or clearly implied in those two files.
3. **Do not** use other repository documents, CLAUDE.md, code, or chat context to **add** new functional requirements. If something is ambiguous in the two allowed files, record it as an **open question** in a short appendix (still without inventing answers).
4. **Milestone boundary:** Scope the task list to **Milestone 2** as defined in the design doc (timeline/milestones section). Do **not** fold in Milestone 3+ items (LLM passes, RAG, style-guide ingestion, etc.) unless the same requirement is explicitly required for Milestone 2 in one of the two allowed files.
5. **Relationship to Milestone 1:** Treat Milestone 1 as **already delivered**. Do not duplicate Milestone 1 tasks unless the design doc explicitly lists them again under Milestone 2.

## What the output must contain

### Structure

- **Title and goal** aligned with the design doc’s Milestone 2 name and stated goal.
- **Deliverable** paragraph copied or tightly paraphrased from the design doc / API spec (with source markers).
- **Workstream sections**: group tasks logically (e.g. sandbox/Docker, backend orchestration, persistence, API contract alignment, frontend). Use the same tone and checklist style as `docs/milestones/milestone-01-tasks.md` if helpful—*that file is formatting inspiration only; it is not a source of new requirements.*

### Task granularity

- Each **task** is a single checkbox item that a developer could complete and verify.
- Prefer **many small tasks** over a few vague ones.
- Include **integration** or **end-to-end verification** tasks only if Milestone 2’s deliverable or API spec implies them.

### Mandatory traceability on every task

Append to **each** task a short italicized comment with **both**:

1. **Source file** — always one of: `docs/design-doc.md` or `docs/api-spec.md`.
2. **Marker** — a precise pointer so others can find the text without searching:
  - For the design doc: section number and heading, e.g. `§8 "Milestone 2 — …"`, or another `§` section plus quoted phrase from the bullet/sentence you are satisfying.
  - For the API spec: endpoint or subsection heading, e.g. ``POST /evaluate``, ``GET /submissions/{id}``, or the exact **Error** table / field table you are implementing against.

If a task satisfies **both** documents (e.g. behavior described in design + request/response in API spec), cite **both** with two markers.

**Forbidden:** tasks whose only citation is a file path with no section/heading/endpoint marker.

## Subagent (or second pass): traceability audit

After drafting `milestone-02-tasks.md`, **run a separate verification step** (subagent or explicit second pass) that:

1. Builds a numbered list of **every** task in `milestone-02-tasks.md`.
2. For each task, confirms **at least one** valid citation to `design-doc.md` or `api-spec.md` and that the task text **directly** reflects that citation (no extrapolation).
3. Lists **any** task that fails the check; **revise or remove** those tasks, then update the doc.
4. Optionally adds a final **Traceability summary** subsection: table columns `Task # | Source file | Marker | Verdict (pass/fail)`.

The human-facing outcome is: **zero untraceable tasks** in the final file.

## Explicit non-goals

- Do **not** write or refactor code.
- Do **not** update OpenAPI files, migrations, or configs unless the prompt is later expanded.
- Do **not** add tasks “for best practices” unless the design doc or API spec states them for this milestone.

## Success criteria (self-check before finishing)

- File exists at `docs/milestones/milestone-02-tasks.md`.
- Every task has `design-doc.md` and/or `api-spec.md` markers as specified.
- No requirement appears that cannot be found in those two files.
- Verification step completed; no failing traceability rows remain (or open questions documented without inventing scope).

