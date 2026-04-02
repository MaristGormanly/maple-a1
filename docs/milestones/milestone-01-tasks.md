# Milestone 1 — Core Infrastructure (End of Week 9)

**Goal:** Deployable skeleton with database, auth scaffold, and repository ingestion. No AI yet.

**Deliverable:** Local end-to-end run: student submits a URL, system clones and pre-processes the repo, returns a `submission_id`.

---

## Jayden — Infrastructure & Deployment

**Summary:** By the end of these tasks, the project will have a live, secured server environment on DigitalOcean with a reverse proxy, TLS, managed PostgreSQL, and proper secrets management. This is the foundational platform everything else runs on.

**Tasks:**
- [x] Initialize repo per MAPLE structure (`docs/`, `server/app/`, `client/src/`, `data/`, `eval/`, `prompts/`)
- [ ] Provision DigitalOcean Droplet (4GB/2vCPU), Managed PostgreSQL, App Platform
- [ ] Configure Nginx reverse proxy and Let's Encrypt TLS certificate via CertBot
- [x] Implement `.env` / secrets management; `.env.example` committed to repo

---

## Dom — Backend API, Database & Security

**Summary:** By the end of these tasks, the server will have a fully migrated PostgreSQL schema, a validated rubric ingestion endpoint, and a regex-based redactor that sanitizes secrets before any future LLM calls. This forms the backend core that the frontend and ingestion pipeline both depend on.

**Tasks:**
- [x] Implement PostgreSQL schema: `User`, `Assignment`, `Rubric`, `Submission`, `EvaluationResult` via SQLAlchemy migrations
- [x] Implement `POST /api/v1/code-eval/rubrics` endpoint with A5-compatible JSON schema validation
- [x] Implement Regex Redactor in `services/llm.py` (strip PATs, env vars, emails before any external call)

---

## Sylvie — Repository Ingestion Pipeline & Frontend

**Summary:** By the end of these tasks, a student can open the Angular app, submit a GitHub URL with an assignment ID, and the system will clone the repo, strip irrelevant files, cache the result, and return a `submission_id` — completing the end-to-end Milestone 1 deliverable.

**Tasks:**
- [x] Implement GitHub PAT-based repository cloning into `data/raw/` using the GitHub API
- [x] Implement Repository Pre-processor: strip `node_modules`, `venv`, compiled binaries, `.git`
- [x] Implement SHA + normalized rubric digest caching key; skip re-cloning on cache hit
- [ ] Angular scaffold: student submission form (GitHub URL + assignment ID), status polling page

---

## Integration Point

The Milestone 1 deliverable spans all three groups. Jayden's infrastructure hosts it, Dom's schema and endpoint persist it, and Sylvie's ingestion pipeline and frontend drive it. A brief integration session near the end of the milestone to wire the pieces together is recommended.
