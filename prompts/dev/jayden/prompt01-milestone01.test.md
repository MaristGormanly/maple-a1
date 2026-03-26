Jayden:

> Do a deep an thorough analysis of the requirements needed (and could be applied at this time) to the Tasks delegated to Jayden in @milestone-01-tasks.md while using @design-doc as a reference for all specific requirements for development.

---

# Test & Verification Prompt — Jayden's Milestone 1 Implementation

## Your Role

You are a **QA verification agent** for the MAPLE A1 project. Your job is to audit Jayden's Milestone 1 implementation against the acceptance criteria and requirements defined in two authoritative sources:

1. **Implementation plan:** `@prompts/dev/jayden/prompt01-milestone01.plan.md` — contains the task breakdown, step-by-step requirements, acceptance criteria, and interface contracts for each of Jayden's six tasks.
2. **Design reference:** `@design-doc` — the canonical design document for MAPLE A1, which defines the system architecture, API conventions (e.g., the Standard Response Envelope), security baseline, and deployment topology.

You are **not** implementing anything. You are reading the code that already exists, comparing it line-by-line against what the plan and design doc require, and producing a structured verdict for each task.

## Files Under Test

These are the files Jayden has created or modified. Read each one before evaluating:

| File | Relevant Task(s) |
|---|---|
| `server/app/main.py` | Task 1 (FastAPI stub, health endpoint, CORS, router wiring) |
| `server/app/config.py` | Task 4 (pydantic-settings loader, auth settings) |
| `.env.example` | Task 4 (placeholder keys for every required variable) |
| `server/app/utils/security.py` | Task 5 (password hashing, JWT create/decode) |
| `server/app/middleware/auth.py` | Task 5 (get_current_user, require_role, OAuth2 scheme) |
| `server/app/routers/auth.py` | Task 5 (stub login/register returning 501) |
| `docs/deployment.md` | Tasks 4 & 6 (secrets management, systemd commands, deploy steps) |

## What to Evaluate

For **each task** listed below, do the following:

1. **Restate the acceptance criteria** from the plan (quote them verbatim).
2. **Check each criterion** against the actual code. For criteria that can be verified by reading source code alone, give a PASS or FAIL with a one-line justification. For criteria that require a running server or live infrastructure (e.g., "SSH into Droplet succeeds"), mark them as REQUIRES_LIVE_ENV and explain what a tester would need to do.
3. **Flag any deviations** — places where the implementation differs from the plan (even if the deviation is arguably an improvement). Note whether the deviation is a risk or is benign.
4. **Check interface contracts** — verify that the code exposes the imports, function signatures, and settings that Dom and Sylvie are documented as depending on.

### Tasks to Cover

- **Task 1: Repository Structure & FastAPI Stub** — directory layout, health endpoint returning MAPLE Standard Response Envelope, router wiring.
- **Task 4: .env / Secrets Management** — `.env.example` completeness, `.gitignore` coverage, `config.py` fail-fast validation, auth-related settings present, `deployment.md` secrets documentation.
- **Task 5: Auth Scaffold** — `security.py` functions (`hash_password`, `verify_password`, `create_access_token`, `decode_access_token`), `middleware/auth.py` dependencies (`get_current_user`, `require_role`, `oauth2_scheme`), stub routes returning 501 with MAPLE error envelope, router wired into `main.py`.
- **Task 6: systemd Service** — `deployment.md` documents `systemctl restart`, `journalctl` log tailing, and the deploy workflow.

> **Note:** Tasks 2 and 3 (DigitalOcean provisioning, Nginx config) are infrastructure-only and cannot be verified from source code. Exclude them from the code audit but mention any references or documentation gaps you find.

## Output Format

Structure your response as follows:

```
## Task <N>: <Title>

### Acceptance Criteria Checklist
- [ ] <criterion> — PASS | FAIL | REQUIRES_LIVE_ENV — <justification>

### Deviations from Plan
- <description of deviation, risk assessment>

### Interface Contract Check
- <import path or function signature> — PASS | FAIL — <note>

### Verdict: PASS | PARTIAL | FAIL
```

After all tasks, include a **Summary** section with:
- Overall readiness assessment (is the scaffold sufficient for Dom and Sylvie to begin their work?).
- A prioritized list of any issues that must be fixed before the milestone integration sequence can proceed.
- Any gaps between what the plan promised and what the code delivers.
