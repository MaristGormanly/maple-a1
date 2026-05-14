# MAPLE A1: Code Submission Evaluator

MAPLE A1 is an AI-powered grading and feedback system designed for programming courses. It automates the evaluation of student code by combining deterministic test execution in secure Docker sandboxes with a sophisticated three-pass LLM pipeline for rubric-aligned assessment and style review.

## Key Features

*   **Three-Pass AI Pipeline:**
    *   **Pass 1 (Reconciliation):** Reconciles deterministic test results with rubric criteria.
    *   **Pass 2 (Style Review):** Performs a deep-dive into code quality using RAG-retrieved style guide excerpts and linter violations.
    *   **Pass 3 (Synthesis):** Generates a final, cohesive feedback report in the MAPLE Standard Response Envelope.
*   **Automated Test Discovery:** Optional `auto_discover` mode detects and runs tests within the student repository (Pytest, JUnit, Jest, CTest), eliminating the need for separate instructor test suites.
*   **RAG-Powered Quality:** Uses `pgvector` and `text-embedding-3-large` to retrieve relevant style guide rules for precise, context-aware code quality feedback.
*   **Secure Sandbox Execution:** Runs student code in ephemeral, hardened Docker containers with strict resource limits, no network access, and read-only filesystems.
*   **Multi-Language Support:** First-class support for Python, Java, JavaScript, TypeScript, and C++.
*   **Security & Redaction:** Integrated Regex Redactor strips PII and secrets before LLM transmission; instructor GitHub PATs are encrypted at rest.

## Architecture Overview

MAPLE A1 leverages a hybrid deterministic-probabilistic approach. After a submission is ingested, it is evaluated in a Docker sandbox. The results, along with AST-extracted code chunks and retrieved style guide excerpts, are processed through an orchestrated LLM chain (Gemini 3.1 Pro/Flash and GPT-4o fallback). All responses adhere to a standardized JSON schema and include `NEEDS_HUMAN_REVIEW` flags for low-confidence or ambiguous matches.

*   **Design doc:** [docs/design-doc.md](./docs/design-doc.md)
*   **API specification:** [docs/api-spec.md](./docs/api-spec.md)
*   **Deployment runbook:** [docs/deployment.md](./docs/deployment.md)

## Tech Stack

*   **Backend:** Python 3.12+ with FastAPI (Async)
*   **Frontend:** Angular 21 (Standalone components)
*   **Database:** PostgreSQL 16 + `pgvector`
*   **AI Models:** Gemini 3.1 Pro (Primary), Gemini 3.1 Flash (Style), GPT-4o (Fallback)
*   **Sandbox:** Docker Engine (Ephemeral sibling containers)
*   **Auth:** OAuth2 Bearer JWT (HS256)

## Setup & Running Locally

### 1. Prerequisites

*   Python 3.12+
*   Node.js (v20+)
*   PostgreSQL 16 with `pgvector`
*   Docker (for sandboxed execution)

### 2. Environment Configuration

Copy the template and configure your credentials:

```bash
cp .env.example .env
```

**Required:** `DATABASE_URL`, `SECRET_KEY`, `GITHUB_TOKEN_ENCRYPTION_KEY`, `GEMINI_API_KEY`.

### 3. Initialize the Database

```bash
alembic upgrade head
```

### 4. Start the Application

**Backend:**
```bash
cd server && uvicorn server.app.main:app --reload
```

**Frontend:**
```bash
cd client && ng serve
```

## Docker Compose (Production Prototype)

The system includes a production-ready Compose stack with PostgreSQL, the FastAPI backend, and an Nginx-fronted Angular build.

```bash
docker compose up -d --build
```

## Deployment

MAPLE A1 is deployed on a DigitalOcean Droplet with automated CI/CD. The API is available at `https://api.maple-a1.com`. Full procedures are documented in [docs/deployment.md](./docs/deployment.md).

## Current Status (Milestone 4 Production Prototype)

*   **Working:** Three-pass AI pipeline (fully operational for Java/Python); RAG infrastructure for Python/Java (active); Docker-based linter execution (pylint/eslint); automated test discovery and language detection; instructor account management and rubric ownership; Git-style inline diff viewer for AI recommendations; terminal status polling and instructor review workflow.
*   **Experimental:** C++ and TypeScript/JavaScript support (implemented but requires additional debugging for reliability); RAG for C++ (active but untested at scale).
*   **Verified:** End-to-end evaluation flow for Python and Java from student submission to instructor approval and final grade release.

## Quick Start Guide

Follow these steps to get your first automated evaluation running in MAPLE A1.

### 1. Authentication & Initial Setup
*   **Login:** Access the application at [https://maple-a1.com](https://maple-a1.com) and sign in with your instructor account.
*   **Configure GitHub:** Navigate to **Settings → GitHub Connections**. You must provide your **GitHub Username** and a **Personal Access Token (PAT)** with repository read access. MAPLE A1 uses this token to clone student repositories into the secure sandbox.

### 2. Create an Assignment
*   Navigate to **Assignments → New**.
*   **Test Mode:** Choose "Instructor suite" to provide a link to your own test repository, or "Auto-discover" to let the AI find and run tests built into student repos.
*   **Quality Gates:** Toggle **Enable style and code-quality review** to activate Pass 2 of the AI pipeline (linter-backed analysis).
*   **Save:** Click "Create assignment" and copy the generated **Assignment ID**.

### 3. Submit for Evaluation
*   Navigate to **Submissions → New**.
*   **Student Repo:** Provide the student's GitHub URL.
*   **Grading Standard:** Enter the **Assignment ID** and upload your **Rubric** file (.json, .txt, or .pdf).
*   **Submit:** Click "Submit for evaluation" to start the asynchronous pipeline.

### 4. Monitor & Review Results
*   **Poll Status:** You will be redirected to the **Status Page**. Watch as the pipeline moves from `Testing` to `Evaluating`.
*   **Analyze Feedback:** Once the status is `Awaiting Review`, inspect the **Criteria Scores** and **Recommendations** (featuring Git-style inline diffs).
*   **Instructor Approval:**
    *   Click **Approve & release** to finalize the AI feedback.
    *   Alternatively, click **Override** to manually adjust scores, add private instructor notes, or leave a custom comment for the student.

## Production Access

The application is deployed and available for testing at the following location:

*   **Production URL:** [https://maple-a1.com](https://maple-a1.com)
*   **API Documentation:** [https://api.maple-a1.com/docs](https://api.maple-a1.com/docs)

Instructors can log in via GitHub to manage assignments and review student submissions.

## Estimated Operating Costs

Based on May 2026 pricing and a 100-student pilot (approx. 500 evaluations/month), the estimated monthly operating cost for MAPLE A1 is **~$105–$125**.

| Item | Service Detail | Est. Cost/Mo |
| :--- | :--- | :--- |
| **Backend Compute** | DigitalOcean Droplet (4GB RAM, 2vCPU, Shared) | $24.00 |
| **Managed Database** | DigitalOcean PostgreSQL (1 Node, 2GB RAM, 25GB SSD) | $22.00 |
| **Frontend Hosting** | DigitalOcean App Platform (Static Site) | $5.00 |
| **Primary LLM** | Gemini 3.1 Pro (Passes 1 & 3) | $40.00 – $55.00 |
| **Style/Utility LLM** | Gemini 3.1 Flash-Lite (Pass 2) | $10.00 – $15.00 |
| **Fallback LLM** | GPT-4o (Standard Tier) | $3.00 – $5.00 |
| **Domain/SSL** | Annualized (maple-a1.com) | ~$1.00 |
| **Total** | | **~$105 – $125** |

*Note: LLM costs vary based on repository size and rubric complexity. Costs can be further optimized via SHA-based caching and Batch API processing.*

## Team Members

| Name | Primary Responsibilities |
|---|---|
| Jayden | Infrastructure, Docker Sandbox, LLM Service, RAG, Linters |
| Dom | Backend API, Database, Pipeline Logic, AI Evaluation |
| Sylvie | Repository Ingestion, API Contracts, Angular UI |

## AI Disclosure

AI tools (Gemini CLI, Claude Code) were used for code scaffolding, integration debugging, and documentation synchronization. Prompt logs are available in `prompts/dev/`.

