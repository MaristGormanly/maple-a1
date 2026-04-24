# MAPLE A1 — User Stories

This document consolidates the user stories for the MAPLE A1 Code Submission Evaluator. It is extracted from [`design-doc.md`](./design-doc.md) §1 for easier reference during planning, milestone scoping, and evaluation.

## MVP Scope Note

For the pilot, A1 operates as an **instructor-driven evaluator**. The instructor (not the student) submits GitHub repository URLs to the system on the student's behalf, using their own Personal Access Token to authorize repository access. Student-facing submission, login, and per-student PAT onboarding are deferred post-MVP. This removes the need for student authentication, session management, and credential provisioning during the pilot, while still exercising the full ingestion → sandbox → AI → review pipeline.

## Core MVP User Stories

1. **Instructor submission on behalf of students** — As an instructor, I want to submit a student's GitHub repository URL to an assignment so that the system can evaluate it without requiring the student to hold an account in A1.

2. **Instructor assignment setup** — As an instructor, I want to create an assignment ID linked to a rubric so that I can submit student GitHub URLs against it, and the system can access each repository through my instructor-level Personal Access Token (granted via course-wide collaborator or GitHub Classroom membership).

3. **Automated test execution** — As an instructor, I want the system to run deterministic test suites against student code so that functional correctness can be evaluated consistently and objectively.

4. **Rubric-aligned grading** — As an instructor, I want evaluations to map directly to rubric criteria so that grades remain consistent with course grading standards.

5. **AI feedback generation** — As an instructor, I want detailed feedback with actionable recommendations (for example localized suggestions) explaining why a student's code lost points so that I can forward pedagogically useful guidance to the student after review.

6. **Instructor review before release** — As an instructor, I want to review AI-generated feedback before forwarding it to students so that I can correct errors and maintain final grading authority.

7. **Secure code execution** — As a system administrator, I want student code to run inside isolated containers so that malicious or poorly written code cannot compromise the grading infrastructure.

8. **Asynchronous processing visibility** — As an instructor, I want to poll the system for status updates as a submission is processed so that I know when the evaluation is complete without needing persistent real-time connections.

## Secondary / Stretch User Stories

1. **Historical grading records** — As an instructor, I want evaluation results stored in a database so that I can review grading history and analyze student performance trends.

2. **Evaluation transparency** — As a student, I want visibility into test results and structured feedback explanations so that I understand how my score was determined and can verify the system's reasoning.
