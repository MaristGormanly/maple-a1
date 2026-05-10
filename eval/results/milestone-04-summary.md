# Milestone 4 — Pilot Results Summary

> **Status:** TEMPLATE — populated by the pilot operator at task 4.E.2.
> Fill in each section after the corresponding metric is collected.
> Design-doc §5 success targets are pre-filled for reference.

## Pilot Window

- Start: `<YYYY-MM-DD>`
- End: `<YYYY-MM-DD>`
- Participants: `<N>` students, `<M>` instructors
- Assignment: `<title>`
- Rubric: `<eval/test-cases/pilot-rubric-v1.json>` (sha: `<digest>`)

## Headline Results

| Metric | Target (design-doc §5) | Observed | Pass? |
|---|---|---|---|
| Rubric alignment accuracy | ≥80% of criteria within ±5/100 | `<pct>` | `<yes/no>` |
| Evaluation consistency | score range ≤3/100 across 5 runs | `<max_range>` | `<yes/no>` |
| Calibration/flag usefulness | avg ≥4/5 | `<avg>` | `<yes/no>` |
| Grading time (ai_review) | <3 min/submission | `<median_seconds>` | `<yes/no>` |
| Grading time (manual baseline) | ~15 min/submission | `<median_seconds>` | — |
| Availability | HTTPS reachable throughout | `<uptime%>` | `<yes/no>` |

## Raw Data

- Per-submission run log: [`pilot-run-log.csv`](./pilot-run-log.csv)
- Rubric alignment deltas: [`rubric-alignment.csv`](./rubric-alignment.csv)
- Consistency variance: [`consistency.csv`](./consistency.csv)
- Calibration ratings: [`calibration-ratings.csv`](./calibration-ratings.csv)
- Grading time: [`grading-time.csv`](./grading-time.csv)
- Surveys summary: [`pilot-surveys-summary.md`](./pilot-surveys-summary.md)
- Incident log: [`incident-log.md`](./incident-log.md)

## Deviations from Targets

*Document any metric that missed its target, with a short root-cause note and follow-up ticket link.*

## Notable Bugs Surfaced

*Per 4.D.1–4.D.2: list P0/P1 issues found during the pilot, their resolution, and any still-open follow-ups.*

## Retrospective Decisions

*Per 4.E.4: list items agreed as "fix post-pilot" vs. "accept as-is" vs. "defer to M5 reconciliation".*

## Sign-Off

- Instructor sponsor: `<name>`, `<date>`
- Team Lead: `<name>`, `<date>`
