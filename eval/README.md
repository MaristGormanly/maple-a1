# Evaluation artifacts (`eval/`)

This directory follows the MAPLE A1 layout described in [`docs/design-doc.md`](../docs/design-doc.md) §5 (Evaluation Plan): automated checks and pilot metrics are expected to live under `eval/` per MAPLE conventions referenced there.

| Path | Purpose |
|------|---------|
| `eval/test-cases/` | Test cases for functional / pipeline evaluation |
| `eval/results/` | Outputs from evaluation runs (e.g. metrics, logs agreed with the team) |
| `eval/scripts/` | Scripts that drive evaluation or aggregate results |

Add content as milestones progress (e.g. Milestone 4 pilot metrics). Do not commit sensitive student data; see **Risk 5 (FERPA)** in `docs/design-doc.md` §7.
