# Software Requirements Specification (SRS)
## MAPLE Module A1: Code Submission Evaluator

**Version:** 1.0  
**Date:** March 4, 2026  
**Team:** Jayden Xavier Melendez  
**Course:** CMPT 394 Applied AI in Software Development, Marist College  
**Status:** Draft

---

## 1. Introduction

### 1.1 Purpose
This Software Requirements Specification defines the functional and non-functional requirements for the **MAPLE A1 module: Code Submission Evaluator**. It serves as the authoritative reference for the development team and faculty PIs to ensure the system effectively combines traditional automated testing with LLM-based code review.

### 1.2 Scope
The A1 module is a tool that accepts programming assignment submissions, runs them against test suites in a secure environment, and generates structured, actionable AI-powered feedback.

* **The system will:**
    * Support student submissions in Python, JavaScript/TypeScript, and Java.
    * Execute code within **Docker containers** to ensure host isolation and security.
    * Utilize the **GitHub API** to query and clone relevant repositories for analysis.
    * Produce feedback that adheres strictly to a 1-to-1 comparison with rubrics provided by the A5 Rubric Engine.
* **The system will not:**
    * Execute student code directly on the application server.
    * Provide personalized academic advising or course registration.

### 1.3 Definitions, Acronyms, and Abbreviations

| Term | Definition |
| :--- | :--- |
| **MAPLE** | Marist AI Platform for Learning & Engagement. |
| **Sandboxing** | A security mechanism for separating running programs, used here to isolate student code. |
| **LLM** | Large Model (e.g., Gemini 3.1). |
| **RAG** | Retrieval-Augmented Generation. |

---

## 2. Overall Description

### 2.1 Product Perspective
The A1 module operates as an independently deployable service within the MAPLE platform. It adheres to the **Option B** backend stack (Python with FastAPI) and follows the unified repository layout defined in the MAPLE Architecture Guide.

### 2.2 Product Functions
1.  **Repository Ingestion:** Cloning student code into the `data/raw/` directory via the GitHub API.
2.  **Deterministic Evaluation:** Running unit tests within a sandbox to generate a JSON report of passes, fails, and errors.
3.  **Probabilistic Assessment:** Passing the code and JSON test report to an AI model for a "correctness" review.
4.  **Feedback Generation:** Generating a response that includes an overall score and criteria-specific feedback based on the A5 rubric.

### 2.3 Technology Stack
* **Backend:** Python with FastAPI (Option B).
* **Isolation:** Docker containers for sandboxed execution.
* **AI Models:** Gemini 3.1 or 2.5 Flash Lite.
* **Database:** PostgreSQL with `pgvector` for metadata and vector storage.
* **Version Control:** Git / GitHub.

### 2.4 Constraints
* **Security:** Must strictly follow the sandboxed execution protocol.
* **Budget:** Monthly API costs for development and pilot usage must stay under $50.
* **API Standards:** Must follow the REST API response envelope and error code standards.

---

## 3. Specific Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority |
| :--- | :--- | :--- |
| **FR-1.1** | The system shall accept a GitHub URL or raw content via the `/evaluate` endpoint. | P0 |
| **FR-1.2** | The system shall isolate code execution using Docker to prevent host compromise. | P0 |
| **FR-1.3** | The system shall generate a JSON report of test results from the sandbox to provide context to the LLM. | P0 |
| **FR-1.4** | The AI shall generate scores and feedback that map 1-to-1 with criteria provided by the A5 Rubric Engine. | P1 |
| **FR-1.5** | The system shall fetch relevant repositories into the `data/raw/` directory using the GitHub API. | P1 |
| **FR-1.6** | The AI shall focus primarily on "correctness" and adherence to the rubric during code review. | P1 |

### 3.2 Non-Functional Requirements

| ID | Requirement | Metric |
| :--- | :--- | :--- |
| **NFR-1.1** | **Performance** | Evaluations must complete within 60 seconds. |
| **NFR-2.1** | **Reliability** | The system must use a fallback model (e.g., 2.5 Flash Lite) if the primary model fails. |
| **NFR-3.1** | **Security** | API keys and secrets must never appear in source code or history. |
| **NFR-4.1** | **Maintainability** | All AI calls must be routed through a shared service layer with structured logging. |

---

## 4. Interface Requirements

### 4.1 API Interface: Evaluate Endpoint
Per the Architecture Guide, the A1 module must implement the following:

**POST** `/api/v1/code-eval/evaluate`

**Request Body:**
```json
{
  "submission_id": "sub_def456",
  "github_url": "[https://github.com/marist-student/assignment-1](https://github.com/marist-student/assignment-1)",
  "rubric_id": "rubric_ghi789",
  "options": {
    "language": "python",
    "provide_feedback": true
  }
}