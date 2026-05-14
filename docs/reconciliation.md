# Design Doc Reconciliation

## Delivered vs. Specified

The design doc described MAPLE A1 as an instructor-driven grading assistant that combines deterministic test execution with AI-assisted rubric feedback. The implementation delivered the core MVP version of that plan: an Angular/FastAPI application with authenticated instructor workflows, GitHub repository submission through `POST /api/v1/code-eval/evaluate`, instructor PAT-based repository access, preprocessing, SHA/rubric-digest caching, asynchronous pipeline execution, and status polling.

On the backend, the project now persists users, assignments, rubrics, submissions, evaluation results, and style-guide chunks. The evaluation pipeline runs student code in Docker sandboxes with language profiles, resource limits, read-only mounts, log normalization, structured test parsing, and deterministic scoring. The AI layer also follows the planned shape: redaction before external calls, a centralized LLM wrapper with retries and fallback, Pass 1/Pass 2/Pass 3 orchestration, schema validation and repair, AST/code chunking, linter hooks, and pgvector-backed style-guide retrieval. On the frontend, the delivered status and review UI shows pipeline progress, test summaries, criteria scores, style findings, diff recommendations, and instructor approve/override controls.

