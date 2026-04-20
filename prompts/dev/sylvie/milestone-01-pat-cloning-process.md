# Milestone 1 PAT Cloning Process

## Purpose

This document outlines the process for implementing the Milestone 1 task:

- Implement GitHub PAT-based repository cloning into `data/raw/` using the GitHub API

This work covers the repository ingestion portion of Milestone 1 and supports the larger deliverable where a student submits a GitHub URL and the system clones and pre-processes the repository before returning a `submission_id`.

## Scope

This task includes:

- validating a GitHub repository URL
- authenticating to GitHub with a Personal Access Token (PAT)
- checking repository access with the GitHub API
- cloning the repository into `data/raw/`
- recording the checked-out commit SHA
- preparing the cloned repository for preprocessing
- returning structured success and failure responses

This task does not include:

- AI grading
- LLM prompts or evaluation
- Docker sandbox execution
- rubric scoring
- final feedback synthesis

## Design Constraints

Based on `design-doc.md` and `milestone-01-tasks.md`, this implementation should satisfy the following:

- student submissions are provided as GitHub repository URLs
- private repositories must be accessible through PAT-based authentication
- repositories are cloned into `data/raw/`
- the exact `commit_hash` is captured
- invalid inputs should fail early with `VALIDATION_ERROR`
- secrets must not be committed or logged
- this work should be compatible with later preprocessing, caching, and persistence steps

## Recommended Approach

The best approach is to use both the GitHub API and `git`:

- use the GitHub API first to validate the repository and confirm PAT access
- use authenticated `git clone` over HTTPS to perform the actual clone
- resolve the checked-out commit SHA after clone

The GitHub API is useful for access validation and metadata lookup, but an actual repository clone is still best handled through `git`.

## Implementation Process

### 1. Accept the submission input

For the student submission flow, the minimum expected input should be:

- `github_url`
- `assignment_id`

Example:

```json
{
  "github_url": "https://github.com/student/example-assignment",
  "assignment_id": "asgn_abc123"
}
```

At this stage, the student should not need to submit a `rubric_id` directly. Professor rubrics may vary in structure and are not guaranteed to be standardized when originally created. Because of that, the system should treat rubrics as instructor-provided input that must first be normalized into an internal MAPLE-compatible format.

The intended flow is:

1. An instructor creates or uploads a rubric for an assignment.
2. The backend validates and standardizes that rubric into the internal schema.
3. The assignment stores a reference to the standardized rubric.
4. The student later submits only a GitHub repository URL and an `assignment_id`.
5. The backend uses the `assignment_id` to retrieve the correct standardized rubric during processing.

This keeps the student submission flow simple and ensures that cloning, preprocessing, caching, and later evaluation all rely on a single internal rubric format rather than inconsistent professor-provided input.

In other words:

- `github_url` identifies the student repository to clone
- `assignment_id` identifies which assignment configuration and standardized rubric should be used
- `rubric_id` should be treated as internal system data after rubric normalization, not required student input

### 2. Parse and validate the GitHub URL

Extract:

- repository owner
- repository name

Validation should reject:

- malformed URLs
- non-GitHub URLs
- URLs that do not point to a repository

### 3. Load the PAT securely

The GitHub PAT should be loaded from an environment variable.

Requirements:

- use `.env` locally
- commit only `.env.example`
- never log the PAT
- never return the PAT in an API response
- never hardcode the token in source files

Suggested variable name:

- `GITHUB_PAT`

### 4. Validate repo access with the GitHub API

Before cloning, call the GitHub API to confirm that:

- the repository exists
- the PAT has access

Suggested endpoint:

- `GET /repos/{owner}/{repo}`

Suggested headers:

- `Authorization: Bearer <PAT>`
- `Accept: application/vnd.github+json`

Expected results:

- `200` if the repo exists and access is valid
- `401` if the token is invalid
- `403` if the token lacks permission or is rate-limited
- `404` if the repository is invalid or inaccessible

Useful metadata to capture:

- full repository name
- default branch
- visibility
- clone URL

### 5. Determine the raw clone path

Clone the repository into `data/raw/` using a deterministic folder name.

Possible patterns:

- `data/raw/{owner}-{repo}/`
- `data/raw/{submission_id}/`

For early local development, `data/raw/{owner}-{repo}/` is simple and easy to inspect.

### 6. Clone the repository

After successful API validation:

- perform an authenticated HTTPS clone
- support both public and private repositories
- avoid writing credentials to disk
- fail cleanly if clone exits non-zero

If history is not needed for the Milestone 1 deliverable, a shallow clone is acceptable.

### 7. Capture the resolved commit hash

After cloning:

- resolve `HEAD`
- store the resulting SHA as `commit_hash`

This is required for:

- traceability
- later caching with `commit_hash + standardized rubric version/hash`
- locking the exact version that was processed

### 8. Hand off to preprocessing

Once cloning succeeds, the local repository path should be ready for the next Milestone 1 task:

- strip `node_modules`
- strip `venv`
- strip compiled binaries
- strip `.git`

This PAT cloning task should stop after a verified clone and captured commit SHA.

### 9. Return a structured result

Minimum successful response:

```json
{
  "success": true,
  "data": {
    "submission_id": "sub_123",
    "github_url": "https://github.com/student/example-assignment",
    "local_repo_path": "data/raw/sub_123",
    "commit_hash": "abc123",
    "status": "cloned"
  },
  "error": null,
  "metadata": {
    "module": "a1"
  }
}
```

## Error Handling

### Invalid GitHub URL

Return a validation error when:

- the URL is malformed
- the URL is not a GitHub repository URL
- the owner or repo name cannot be extracted

### Missing or invalid PAT

Return a configuration or authentication error when:

- `GITHUB_PAT` is missing
- the PAT is expired
- the PAT is invalid

### Inaccessible repository

Return `VALIDATION_ERROR` when:

- the repository does not exist
- the PAT does not have access to the private repository

### Clone failure

Return a structured error when:

- the clone command fails
- the destination path is invalid
- the checkout cannot complete

## Security Requirements

- PATs must come from environment variables only
- PATs must never be committed
- PATs must never be written to logs
- local clone directories should be ignored by git
- repository URLs should be sanitized before logging
- this task should remain compatible with the later Regex Redactor work

## Local Testing Plan

### Test 1: Public repository clone

Input:

- valid public GitHub repository URL

Expected result:

- API validation succeeds
- repository is cloned into `data/raw/`
- `commit_hash` is captured

### Test 2: Private repository clone

Input:

- valid private repository URL that the PAT can access

Expected result:

- API validation succeeds
- repository is cloned into `data/raw/`
- `commit_hash` is captured

### Test 3: Malformed repository URL

Input:

- invalid GitHub URL

Expected result:

- request fails before clone
- structured validation error is returned

### Test 4: Missing PAT

Input:

- no configured `GITHUB_PAT`

Expected result:

- request fails immediately
- no clone attempt is made

### Test 5: Unauthorized private repository

Input:

- private repo not accessible by the PAT

Expected result:

- GitHub API validation fails
- no clone attempt is made

## Dependencies on Other Milestones

This task can be started and tested locally without waiting for the full completion of other teammates' milestones.

### Not required to begin

- production infrastructure
- DigitalOcean deployment
- TLS and reverse proxy setup
- final database migrations
- rubric ingestion endpoint
- AI redaction logic

### Helpful but not blocking

- agreed `.env.example` format
- agreed project folder structure
- agreed shape for `submission_id`
- agreed backend response envelope
- agreed assignment-to-standardized-rubric lookup contract

### Needed later for integration

- Dom's persisted `Submission` model and database schema
- rubric normalization and standardized rubric storage
- Jayden's finalized environment and deployment setup
- frontend wiring for student submission and polling

## Git Workflow With `dev`

The team will integrate work into `dev` before merging to `main`, so this task should be developed on a feature branch created from `dev`.

### Recommended branch flow

- `main` is the stable branch
- `dev` is the integration branch
- your work should live on a feature branch such as `feature/pat-repo-cloning`

### If working from the shared repository

1. Fetch the latest remote branches.
2. Check out `dev`.
3. Pull the latest `dev`.
4. Create a new feature branch from `dev`.
5. Commit your PAT cloning work there.
6. Open a pull request into `dev`.

### If working from your own fork

1. Fork the repository on GitHub.
2. Clone your fork locally.
3. Add the original repository as `upstream`.
4. Fetch `upstream`.
5. Create a local `dev` branch tracking `upstream/dev`.
6. Create your feature branch from `dev`.
7. Push the feature branch to your fork.
8. Open a pull request into the original repository's `dev` branch.

### Example command flow

```bash
git clone <your-fork-url>
cd maple-a1
git remote add upstream <original-repo-url>
git fetch origin
git fetch upstream
git checkout -b dev upstream/dev
git checkout -b feature/pat-repo-cloning
git push -u origin feature/pat-repo-cloning
```

### Keeping your branch updated

```bash
git fetch upstream
git checkout dev
git pull upstream dev
git checkout feature/pat-repo-cloning
git merge dev
```

If the team prefers rebasing instead of merging, follow that convention consistently across the team.

## Definition of Done

This task is complete when:

- a PAT can authenticate against GitHub
- public and private repository access can be validated
- the repository can be cloned into `data/raw/`
- the checked-out `commit_hash` is captured
- invalid inputs fail cleanly
- the flow can be demonstrated locally
- the implementation is committed from a feature branch based on `dev`
