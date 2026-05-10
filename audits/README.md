# Audits

This directory holds forensic audits of the MAPLE A1 codebase. The current
audit lives at the top level; superseded audits are moved to `archive/` when
a new one is published.

## Workflow

1. New audit is written to `audits/post-ui-forensic-audit-YYYY-MM-DD.md`
   (or `audits/milestone-N-audit-YYYY-MM-DD.md` for milestone-scoped audits).
2. The new audit's executive summary should reference the prior audit it
   supersedes by relative path.
3. When a fresh audit lands, the previous top-level audit is moved into
   `audits/archive/`. The archive folder is append-only — never edit a
   committed historical audit.

## Index (latest first)

- `post-ui-forensic-audit-2026-04-30.md` — post-UI integration audit
  (current). Supersedes `archive/comprehensive-forensic-audit-2026-04-30.md`
  and `archive/ui-spec-audit.md`.

## Archive

`audits/archive/` contains:

- `comprehensive-forensic-audit-2026-04-30.md` — pre-remediation snapshot
  (caught the three EXTREME defects fixed in commit `2ab9c7a`).
- `milestone-04-audit-2026-04-30.md` — M4 forensic audit + action plan.
- `milestone-03-audit-2026-04-19.md` — M3 deliverables audit.
- `ui-spec-audit.md` — UI ↔ spec drift snapshot.
- `milestone-01-*` / `milestone-02-*` — earlier milestone audits.

## Conventions

- File name format: `<audit-type>-YYYY-MM-DD.md`, ASCII-lowercase.
- The header block at the top of every audit must record the date,
  auditor, scope, branch, and HEAD SHA at the time of the audit.
- Every Origin Location (file:line) reference must be a working
  Markdown link the IDE can resolve relative to the repo root.
