# Milestone 4 — Pilot Deployment & Evaluation (Week 14)

**Goal:** System live on DigitalOcean; 10-student pilot executed; evaluation metrics collected. *(Source: `docs/design-doc.md` §8 "Milestone 4 — Pilot Deployment & Evaluation")*

**Deliverable:** Pilot complete; evaluation metrics documented in `eval/results/`; application accessible at production URL with HTTPS. *(Source: `docs/design-doc.md` §8 Milestone 4 deliverable)*

---

## Iteration-by-Iteration Task Table

| Phase | Task ID | Subtask Description | Estimated Effort (Hours) | Dependencies | Human_Action_Required | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 4.A — Production Configuration** | 4.A.1 | SSH to DigitalOcean Droplet; back up existing `/etc/maple-a1/.env` (if present) to `.env.bak.<date>` before edits. | 0.5 | M3 complete; Droplet provisioned in M1 | **Yes** — Team Lead must provide SSH access and current Droplet IP. Output: confirmed SSH login + backup file path. | Read-only prep step; do not edit yet. |
| | 4.A.2 | Populate production `.env` on Droplet with `DATABASE_URL`, `SECRET_KEY`, `GITHUB_PAT`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `CORS_ORIGINS=https://maple-a1.com`, `APP_ENV=production`. Verify file mode `600`, owned by `maple` user. | 1.5 | 4.A.1 | **Yes** — Team Lead must supply production API keys (Gemini, OpenAI, GitHub PAT with `repo:read`) and signed JWT `SECRET_KEY`. Output: secret values delivered via 1Password / secure channel. | `.env` must be gitignored; never commit. Cross-check against `.env.example`. |
| | 4.A.3 | Confirm all secrets gitignored: `git check-ignore -v server/.env` on Droplet working copy; fail loudly if tracked. | 0.25 | 4.A.2 | No | Defensive check per design-doc §6 "Environment Management". |
| | 4.A.4 | Set CORS policy: explicit origin allow-list `https://maple-a1.com`, no wildcard. Verify `server/app/main.py` `CORSMiddleware` reads from `settings.CORS_ORIGINS`. | 1.0 | 4.A.2 | No | Design-doc §8 "Set CORS headers (no wildcard in production)". |
| | 4.A.5 | Configure rate limiting: 30 req/min per IP via `slowapi` or Nginx `limit_req_zone`. Add `/api/v1/code-eval/evaluate` specific zone (stricter, e.g. 5/min) to prevent LLM cost runaway. | 2.0 | 4.A.2 | No | Design-doc §8 "configure rate limiting (30 req/min per IP per Architecture Guide §6)". Include in `docs/deployment.md`. |
| | 4.A.6 | Run `alembic upgrade head` against Managed PostgreSQL; verify `style_guide_chunks` table present and HNSW index built. | 0.5 | 4.A.2 | No | Reuses M3 migrations. |
| | 4.A.7 | Run `python -m app.services.style_guide_ingester` on Droplet to populate 5 style guides in production pgvector. Verify `SELECT language, count(*) FROM style_guide_chunks GROUP BY 1` returns 5 rows. | 1.0 | 4.A.6; `GEMINI_API_KEY` + `OPENAI_API_KEY` present | No | One-time post-deploy step per M3 roadmap. |
| | 4.A.8 | Smoke test: `curl https://api.maple-a1.com/health` returns 200; hit `/api/v1/code-eval/evaluate` with a known-good fixture repo; verify end-to-end 3-pass evaluation completes and persists `ai_feedback_json`. | 1.5 | 4.A.1–4.A.7 | No | Gate for opening pilot to students. |

| Phase | Task ID | Subtask Description | Estimated Effort (Hours) | Dependencies | Human_Action_Required | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 4.B — Pilot Preparation** | 4.B.1 | Recruit 10 pilot students; collect consent for pilot participation and anonymized data collection. | 3.0 | 4.A.8 | **Yes** — Instructor / Marist faculty sponsor must recruit and obtain signed consent. Output: signed consent forms; 10 student accounts provisioned. | FERPA compliance per design-doc §7 Risk 5. |
| | 4.B.2 | Instructor creates pilot assignment: rubric JSON (A5-schema compliant), test suite repo URL, `enable_lint_review: true`, `language_override: null`. | 2.0 | 4.B.1 | **Yes** — Instructor must author and sign off on rubric content and test suite. Output: `rubric.json` + test suite repo pushed. | Store rubric copy in `eval/test-cases/pilot-rubric-v1.json`. |
| | 4.B.3 | Create 5 instructor-graded "gold standard" reference submissions (known-good, known-partial, known-failing) for baseline comparison. | 4.0 | 4.B.2 | **Yes** — Instructor manually grades each reference submission against rubric. Output: `eval/test-cases/pilot-gold/*.json` with human `criteria_scores` and written feedback. | Used by Phase 4.C accuracy checks. |
| | 4.B.4 | Draft student- and instructor-facing survey instruments (Google Forms or equivalent). Student survey covers feedback clarity, workflow ease, improvement value; instructor survey covers time saved, feedback alignment, review UX. | 2.0 | 4.B.1 | **Yes** — Team Lead must approve final survey text and publish. Output: survey URLs. | Design-doc §5 "User Evaluation". |
| | 4.B.5 | Brief pilot participants: 15-min walkthrough of submission flow, status page, and where to find feedback. Share survey link to be completed after results. | 1.5 | 4.B.4 | **Yes** — Instructor runs the session. Output: attendance log. | Runbook walkthrough only; no code changes. |

| Phase | Task ID | Subtask Description | Estimated Effort (Hours) | Dependencies | Human_Action_Required | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 4.C — Pilot Execution & Metrics Collection** | 4.C.1 | Open submissions; monitor Droplet CPU/memory and PostgreSQL connections via `htop` / `pg_stat_activity`. Alert threshold: >80% CPU sustained >5 min. | 4.0 (across pilot window) | 4.A.8, 4.B.5 | No | Design-doc §3 §IV "Sandbox Observability Layer". |
| | 4.C.2 | For each of 10 student submissions: verify pipeline completes; record `submission_id`, `commit_hash`, `latency_ms_total`, model(s) used (from `metadata_json`), cost estimate (from structured logs added in M3). | 2.0 | 4.C.1 | No | Append to `eval/results/pilot-run-log.csv`. |
| | 4.C.3 | **Rubric alignment accuracy:** manually grade the 10 pilot submissions against the rubric (instructor blind to AI scores). Compare AI `criteria_scores` to instructor scores; compute per-criterion absolute delta. **Target: ≥80% of rubric criteria within ±5/100 points.** | 8.0 | 4.C.2, 4.B.3 | **Yes** — Instructor grades each submission independently, *before* seeing the AI score. Output: `eval/results/rubric-alignment.csv` with per-criterion deltas. | Design-doc §5 Rubric alignment table. Blinding is critical to validity. |
| | 4.C.4 | **Evaluation consistency:** pick 1 pilot submission; run 5 repeated evaluations under identical inputs (same commit, same rubric). Record per-criterion score variance. **Target: variance ≤3/100 points.** | 2.0 | 4.C.2 | No | Cache must be disabled / bypassed for this test; document method in result file. |
| | 4.C.5 | **Calibration & flag accuracy:** for each submission, verify `flags` array contains `ai_confidence_low` / `NEEDS_HUMAN_REVIEW` when appropriate. Instructor rates AI feedback usefulness on 1–5 scale for clarity, relevance, instructional value. **Target: avg ≥4/5.** | 3.0 | 4.C.3 | **Yes** — Instructor rates each feedback artifact. Output: `eval/results/calibration-ratings.csv`. | Design-doc §5 Calibration table. |
| | 4.C.6 | **Grading time baseline:** record wall-clock time for (a) instructor to manually grade one submission end-to-end, (b) instructor to review AI feedback for same submission. **Target: review time <3 min vs. manual ~15 min.** | 2.0 | 4.C.3 | **Yes** — Instructor self-times both workflows with stopwatch. Output: `eval/results/grading-time.csv`. | Design-doc §5 Baseline Comparison. |
| | 4.C.7 | Distribute surveys (4.B.4) to 10 students + instructor; aggregate responses into `eval/results/pilot-surveys-summary.md`. | 2.0 | 4.C.2, 4.B.4 | **Yes** — Students + instructor complete survey. Output: raw survey CSV + aggregate summary. | Design-doc §5 "User Evaluation" success criteria. |

| Phase | Task ID | Subtask Description | Estimated Effort (Hours) | Dependencies | Human_Action_Required | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 4.D — Bug Triage & Hotfixes** | 4.D.1 | Daily during pilot: review `app.log` structured JSON for `llm_retry`, `llm_model_exhausted`, `EVALUATION_FAILED`, and Docker exit 137 / 124 events. Open GitHub issue per distinct failure mode. | 3.0 | 4.C.1 | No | Triage-only; do not bundle fixes into feature work. |
| | 4.D.2 | Fix critical bugs (P0 = pipeline failure; P1 = wrong score persisted). Each fix: branch → test → PR → merge to `dev` → deploy. No P2/P3 fixes during pilot window. | 6.0 (estimate; variable) | 4.D.1 | **Yes** — Team Lead prioritizes which issues qualify as P0/P1. Output: issue-by-issue go/no-go decision. | Design-doc §8 "Fix any critical bugs surfaced during pilot". Use existing CI workflow. |
| | 4.D.3 | If production incident requires rollback: execute rollback per `docs/deployment.md` runbook (git revert → `systemctl restart maple-a1`). Document in incident log. | 1.0 (reserved) | 4.D.2 | **Yes** — Team Lead authorizes rollback before execution. Output: signed rollback decision. | Design-doc §7 Risk 2 Contingency (sandbox disable). |

| Phase | Task ID | Subtask Description | Estimated Effort (Hours) | Dependencies | Human_Action_Required | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 4.E — Results Consolidation & Sign-Off** | 4.E.1 | Commit all `eval/results/*` artifacts to repo (no PII; verify redaction). | 1.0 | 4.C.3–4.C.7 | No | Per MAPLE Architecture Guide `eval/` conventions. |
| | 4.E.2 | Write `eval/results/milestone-04-summary.md`: tables of accuracy, consistency, calibration, timing, survey results; call out deviations from targets; link to raw CSVs. | 3.0 | 4.E.1 | No | Referenced from `README.md` in M5. |
| | 4.E.3 | Update `docs/milestones/milestone-04-tasks.md` (this file) with a traceability summary flipping each row to `done` after verification, matching the M3 format. | 1.0 | 4.E.2 | No | M5 prep. |
| | 4.E.4 | Pilot retrospective meeting (team + instructor sponsor). Capture what worked, what didn't, and items deferred to M5 / post-pilot. | 1.5 | 4.E.2 | **Yes** — Instructor sponsor attends and signs off on pilot outcome. Output: signed acceptance note or email. | Final gate before Milestone 5 handoff. |

---

## Critical Human Decision Points (Summary)

| # | Decision / Input | Who | Gate |
|---|------------------|-----|------|
| 1 | Production API keys (Gemini, OpenAI, GitHub PAT, JWT secret) | Team Lead | 4.A.2 |
| 2 | Pilot student recruitment + FERPA consent | Instructor / Marist sponsor | 4.B.1 |
| 3 | Rubric authorship + sign-off | Instructor | 4.B.2 |
| 4 | Gold-standard manual grading (5 reference submissions) | Instructor | 4.B.3 |
| 5 | Survey text approval + publication | Team Lead | 4.B.4 |
| 6 | Blind manual grading of 10 pilot submissions | Instructor | 4.C.3 |
| 7 | Feedback usefulness 1–5 ratings | Instructor | 4.C.5 |
| 8 | Hotfix P0/P1 prioritization | Team Lead | 4.D.2 |
| 9 | Rollback authorization (if incident) | Team Lead | 4.D.3 |
| 10 | Pilot acceptance sign-off | Instructor sponsor | 4.E.4 |

---

## Success Criteria (from `docs/design-doc.md` §5 + §8)

- **Rubric alignment:** ≥80% of criteria within ±5/100 points vs. instructor.
- **Consistency:** score variance ≤3/100 points across 5 repeated runs.
- **Calibration:** avg usefulness rating ≥4/5.
- **Grading time:** instructor review <3 min/submission (vs. ~15 min manual).
- **Survey:** majority of instructors report reduced workload; majority of students report feedback helped understanding.
- **Availability:** production URL reachable via HTTPS throughout pilot window.

---

## Total Estimated Effort

~58 hours across Phases 4.A–4.E, excluding variable bug-fix time (4.D.2) and the pilot monitoring window (4.C.1 runs in background during the submission window).
