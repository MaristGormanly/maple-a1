My Prompt: """Task: Review the tasks for Jayden in @milestone-01-tasks.md. Break down tasks into actionable steps required to complete the summary goal and Ingestion point Milestone 1. Refer to @design-doc.md for any questions about creating tasks for implementation."""

Meta Prompt:

**Objective**

Produce an **implementation-oriented breakdown** of work so Milestone 1 can be completed, focused on **Jayden’s Infrastructure & Deployment** scope in `milestone-01-tasks.md`, while staying aligned with the **Milestone 1 goal** (deployable skeleton: DB, auth scaffold, repo ingestion; local E2E: URL → clone/pre-process → `submission_id`) and the **cross-team integration** described under “Integration Point” in that file.

**Inputs to use**

1. **`milestone-01-tasks.md`** — Use Jayden’s task list and summary as the primary scope; use the milestone **Goal**, **Deliverable**, and **Integration Point** sections so steps account for how Jayden’s platform supports Dom’s API/DB work and Sylvie’s ingestion/frontend work.
2. **`design-doc.md`** — When turning bullets into implementation tasks, resolve ambiguities using the SRS (architecture, components, security expectations, API/storage concepts). Do not invent requirements that contradict these docs; call out gaps explicitly if the docs are silent.

**What to produce**

1. **Jayden-specific steps** — For each checkbox under Jayden, expand into **ordered, actionable steps** (concrete enough to execute or ticket), including dependencies, acceptance criteria, and obvious interfaces with other owners (e.g., what must be true on the server for the ingestion pipeline and API to run).
2. **Milestone 1 / ingestion alignment** — Add a short section that maps Jayden’s outcomes to the **Milestone 1 deliverable** and **integration** (what Jayden must expose or configure so “student submits URL → clone/pre-process → `submission_id`” can run in the target environment), without duplicating Dom/Sylvie implementation detail unless it defines a **dependency** on Jayden (hosting, TLS, DB connectivity, secrets, reverse proxy routes, etc.).

**Clarifications**

- “Ingestion point” was meant to mean **only** Jayden’s work, restrict the breakdown to infrastructure that **enables** ingestion (network, TLS, proxy, runtime, secrets, managed DB hosting), not Sylvie’s cloning/pre-processor code.
- Prefer **verbs and artifacts** in each step (e.g., “Create X”, “Configure Y”, “Verify Z”) rather than paraphrasing the original bullets.