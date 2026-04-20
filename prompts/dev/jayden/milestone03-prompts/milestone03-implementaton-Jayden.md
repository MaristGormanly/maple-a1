# Milestone 3 — Jayden workstream: refined agent prompt

This file holds the **original user prompt** and a **refined multi-agent prompt** for implementing and documenting Jayden’s Milestone 3 tasks. When stating requirements for MAPLE A1 behavior, architecture, or APIs, agents must ground claims in **`docs/` only** (for example `docs/design-doc.md`, `docs/api-spec.md`, `docs/deployment.md`). Do not treat `CLAUDE.md`, code comments, or chat memory as authoritative specs.

---

## Original prompt

> Review the tasks for `docs/milestones/milestone-03-tasks.md`. Only focus on the tasks for Jayden. Create an actionable plan to work through each task step by step. The plan should include the delegation of subagents for research, planning, subtask creation, implementation, testing, error correction, and a final agent for documenting interface strategies for Sylvie and Dom's part in milestone03. A final agent should be used to write the implementation summary of Jayden's parts only to `prompts/dev/jayden/milestone03-task-implementation-summaries.md`. You are only allowed to reference the strict documentation documents for the parts of the maple a1 system found in `docs/`.

---

## Refined prompt (for AI agents)

### Role: orchestrator

You are the **orchestrator** for Jayden’s Milestone 3 scope. Your job is to produce a **step-by-step execution plan**, sequence work by **dependencies**, delegate specialized work to **subagents** (below), and ensure outputs land in the right places. You **do not** skip dependency order (for example: pgvector schema before ingestion; ingestion before chunking and embedding; chunks before retrieval; base images before linter execution in containers).

**Authoritative task list (Jayden only):** read and follow the eight checkboxes under **“Jayden — LLM Service, RAG Infrastructure, Linter Execution”** in `docs/milestones/milestone-03-tasks.md`, including each task’s cited `docs/design-doc.md` (and `docs/deployment.md` where specified) markers.

**Documentation rule:** When describing how MAPLE A1 should behave, which files or services exist, or integration expectations, cite or paraphrase **only** sources under `docs/` (for example `docs/design-doc.md`, `docs/milestones/milestone-03-tasks.md`, `docs/deployment.md`, `docs/api-spec.md`). For **implementation**, you may read and edit the codebase, but **specs and interface contracts** for what the system must do come from `docs/`.

---

### Subagent roster and when to delegate

Use **separate focused subagents** (or clearly separated phases if your runtime has no subagents). Each subagent returns **concise artifacts**: findings, decisions, file lists, or diffs—not generic essays.

| Subagent | Responsibility | Primary inputs |
|----------|----------------|----------------|
| **Research** | Map current repo state to M3 Jayden tasks: locate `services/llm.py`, Docker or sandbox services, Alembic, models, M2 runtime. Note gaps versus `docs/design-doc.md` and `docs/milestones/milestone-03-tasks.md`. | `docs/`, codebase |
| **Planning** | Ordered plan with dependencies, acceptance checks per task, and risks (API keys, pgvector, Docker). | Research notes, `docs/milestones/milestone-03-tasks.md` |
| **Subtask creation** | Break each Jayden checkbox into implementable steps (migration shape, function signatures, test cases, logging fields). | Planning output |
| **Implementation** | Apply code and migrations per plan; keep changes scoped to Jayden-owned surfaces (`llm.py`, RAG, ingestion, retrieval modules, Docker client or runner or images, migrations, `docs/deployment.md` where the task explicitly requires it). | Subtasks, `docs/` |
| **Testing** | Unit and integration tests: mocks for LLM and embeddings where appropriate; database and pgvector tests if the environment supports them; Docker and linter tests as feasible. | Implementation |
| **Error correction** | Reproduce failures, fix root cause, re-run targeted tests; document residual limitations. | Failing tests, logs |
| **Interface and handoff (Sylvie and Dom)** | **Final documentation subagent (not the implementation summary):** produce a short **interface strategies** note for **Dom** and **Sylvie** grounded in `docs/`: callable surfaces Jayden exposes (for example `llm.complete()`, `retrieve_style_chunks(...)`, linter JSON shape, metadata fields pipelines and UI depend on). Explicitly list **what Dom should call** versus **what Sylvie’s API and UI consume downstream**, without inventing fields not backed by `docs/design-doc.md` or `docs/api-spec.md`. Replace the placeholder body under `## Handoff: interface strategies for Dom and Sylvie (Milestone 3)` in **this same file**, **after** the implementation summary section. | `docs/design-doc.md`, `docs/api-spec.md`, `docs/milestones/milestone-03-tasks.md` |
| **Implementation summary (Jayden only)** | **Final subagent:** after Jayden-owned work is done (or a defined milestone is reached), write **only** Jayden-scope outcomes: what shipped, files touched, how to run tests, open risks, and pointers to `docs/` sections. Replace the placeholder under `## Implementation summary — Jayden (Milestone 3)` in **this file** (`prompts/dev/jayden/milestone03-task-implementation-summaries.md`). Do not duplicate Dom or Sylvie task write-ups; reference their integration via the handoff section instead. | Git diff, tests, `docs/` |

---

### Context snapshot (Jayden’s eight tasks — names only)

Use `docs/milestones/milestone-03-tasks.md` for full acceptance criteria and citations.

1. LLM `complete()`: two retries per model, exponential backoff, structured logging, populate response dataclasses.  
2. Model fallback chain plus configurable timeouts (30 seconds and 60 seconds), redaction before external calls, terminal failure behavior per `docs/design-doc.md`.  
3. Alembic plus pgvector: `style_guide_chunks` table, extension, index strategy per task text.  
4. `style_guide_ingester.py`: fetch five named style guides, parse version, HTML and PDF handling per task.  
5. Semantic chunking plus `text-embedding-3-large` embeddings persisted to the database.  
6. `rag_retriever.py`: `retrieve_style_chunks(...)`, cosine similarity, language filter, threshold and no-match logging per task.  
7. Linter execution in Docker: structured violations JSON; reuse M2 container hardening per `docs/design-doc.md`.  
8. Base images: pylint and eslint with pinned versions; document in `docs/deployment.md`.

---

### Task for the orchestrator (deliverables)

1. **Plan:** step-by-step order respecting dependencies in `docs/milestones/milestone-03-tasks.md`.  
2. **Execute:** delegate to the subagent roster; merge results; keep scope Jayden-only.  
3. **Summary doc:** final subagent replaces the placeholder under `## Implementation summary — Jayden (Milestone 3)` in this file.  
4. **Handoff doc:** final subagent replaces the placeholder under `## Handoff: interface strategies for Dom and Sylvie (Milestone 3)` in this file (after the summary).

---

### Important reminders

- **Specs from `docs/` only** for system behavior and cross-role contracts; code is for execution and verification.  
- **Dependency chain:** follow the “Depends on” notes under Jayden’s tasks in `docs/milestones/milestone-03-tasks.md`.  
- **Integration layer:** Jayden supplies infrastructure; Dom orchestrates passes; Sylvie exposes review UI and endpoints—describe boundaries in the handoff section using `docs/` language.  
- **Single file for agent outputs:** append handoff and Jayden implementation summary here; do not scatter summary across other prompt files unless the user asks.  
- **Minimal scope:** avoid unrelated refactors; match existing project patterns.  
- **Reproducibility:** pin tool versions where the milestone text requires it (linters, embeddings model name).

---

## Implementation summary — Jayden (Milestone 3)

*(To be filled by the final summary subagent when Jayden-owned implementation is complete. Jayden-only scope; cite `docs/` for behavior.)*

---

## Handoff: interface strategies for Dom and Sylvie (Milestone 3)

*(To be filled by the final handoff subagent after Jayden’s interfaces are known. Ground all claims in `docs/`.)*
