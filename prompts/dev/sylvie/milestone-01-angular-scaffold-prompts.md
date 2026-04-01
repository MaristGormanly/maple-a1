# Milestone 1 Angular Scaffold Prompts

## Purpose

This file contains ready-to-use prompts for Milestone 1, Task 4:

- Angular scaffold: student submission form (GitHub URL + assignment ID), status polling page

These prompts are designed to keep implementation aligned with:

- `docs/milestones/milestone-01-tasks.md`
- `docs/design-doc.md`
- `server/app/main.py` (the evaluate endpoint contract)

The goal is to produce a minimal Angular UI that completes the end-to-end Milestone 1 deliverable:
a student opens the app, fills in the form, submits, and sees a `submission_id` come back.

---

## Backend Contract (Read Before Implementing)

The Angular client talks to one endpoint:

**`POST /api/v1/code-eval/evaluate`**

- **Content-Type:** `multipart/form-data` (not JSON)
- **Auth:** Bearer token required in `Authorization` header
- **Form fields:**
  - `github_url` (string, required) — e.g. `https://github.com/student/repo`
  - `assignment_id` (string, optional)
  - `rubric` (file upload, required) — `.json` or `.txt` rubric file
- **Success response shape:**
  ```json
  {
    "success": true,
    "data": {
      "submission_id": "sub_abc123def456",
      "github_url": "https://github.com/student/repo",
      "assignment_id": "CS101-A1",
      "rubric_digest": "<sha256 hex>",
      "status": "cloned",
      "local_repo_path": "data/raw/...",
      "commit_hash": "<full sha>"
    },
    "error": null,
    "metadata": { "timestamp": "...", "module": "a1", "version": "1.0.0" }
  }
  ```
- **Error response shape:**
  ```json
  {
    "success": false,
    "data": null,
    "error": { "code": "VALIDATION_ERROR", "message": "..." },
    "metadata": { ... }
  }
  ```

**Important:** The endpoint requires a valid JWT Bearer token. For Milestone 1, the auth
service (`POST /api/v1/code-eval/auth/login`) is not yet implemented. The Angular app
should include a placeholder auth service that allows a hardcoded dev token to be
injected via environment config, so the UI can be demo'd locally without a working login flow.

---

## Scope

This task includes:

- initializing an Angular project inside `client/`
- a submission form page (`/submit`) with GitHub URL, assignment ID, and rubric file inputs
- a status display page (`/status/:id`) showing the response after submission
- an `EvaluationService` that posts form-data to the backend
- basic client-side validation (URL format, required fields)
- CORS-compatible requests to `http://localhost:8000` for local dev

This task does not include:

- a real login or registration flow (auth is deferred)
- live status polling via repeated GET requests (the polling endpoint does not exist yet)
- instructor views, rubric management UI, or evaluation results display
- production build configuration, Docker, or CI integration
- anything beyond what is needed to complete the end-to-end Milestone 1 submit → response flow

---

## Design Constraints

- The existing `client/src/` directory has four empty subdirectories: `components/`, `pages/`,
  `services/`, `utils/`. Place Angular files in those locations rather than restructuring.
- The backend is at `http://localhost:8000` during local development. Store this in
  `environment.ts` so it is easy to change.
- The rubric input must be a file upload (`<input type="file">`), not a text area. The
  backend expects an `UploadFile`, not inline JSON in the request body.
- The Angular app must use `FormData` (not `HttpClient` JSON mode) for the evaluate
  request, because the endpoint is multipart form-data.
- Keep the Angular project itself minimal. No state management libraries, no UI component
  libraries unless Angular Material is already a dependency. Plain reactive forms are fine.

---

## Prompt 1: Read Context And Plan

Use this first to make the assistant understand the backend contract before touching any code.

```text
Read these files carefully before proposing any implementation:

- docs/milestones/milestone-01-tasks.md
- docs/design-doc.md
- server/app/main.py
- prompts/dev/sylvie/milestone-01-angular-scaffold-prompts.md

Then produce:
1. A summary of exactly what the Angular scaffold must do for Milestone 1
2. The exact shape of the POST /api/v1/code-eval/evaluate request (content-type, fields, file upload)
3. The exact shape of the success and error responses the UI must handle
4. A list of files you expect to create (keep it minimal)
5. A note on how to handle auth for local dev since the login endpoint is not implemented
6. Any risks or ambiguities before you write a single line of code

Do not edit any files yet.
```

---

## Prompt 2: Initialize The Angular Project

Use this after planning. The `client/` directory is currently empty except for placeholder
`.gitkeep` files. This prompt initializes the Angular workspace.

```text
Initialize an Angular project inside the client/ directory of this repository.

Requirements:
- Use Angular routing (--routing flag)
- Use SCSS for styles (--style=scss)
- Do not initialize a new git repo inside client/ (--skip-git)
- The project should generate files that respect the existing structure:
    client/src/components/
    client/src/pages/
    client/src/services/
    client/src/utils/

Steps:
1. Check whether the Angular CLI (ng) is installed. If not, explain what to install.
2. Run `ng new maple-client --routing --style=scss --skip-git --directory .` from inside
   the client/ directory to generate into the existing directory.
3. Verify that angular.json, package.json, tsconfig.json, and src/app/ were created.
4. Add `environment.ts` and `environment.prod.ts` to src/environments/ with:
   - `apiBaseUrl: 'http://localhost:8000'` for local dev
   - `apiBaseUrl: ''` (empty string, relative) for prod
5. Enable `HttpClientModule` in AppModule (or provideHttpClient in standalone setup).
6. Report what was created and any issues.

Do not implement any components yet.
```

---

## Prompt 3: Build The Evaluation Service

Use this after the Angular project is initialized.

```text
Create an EvaluationService in client/src/services/evaluation.service.ts.

This service wraps the POST /api/v1/code-eval/evaluate endpoint.

Backend contract:
- URL: POST /api/v1/code-eval/evaluate
- Content-Type: multipart/form-data
- Auth: Bearer token in Authorization header
- Fields:
    github_url  (string, required)
    assignment_id  (string, optional — omit the field entirely if empty)
    rubric  (File, required — the uploaded rubric file)
- Success response: { success: true, data: { submission_id, github_url, assignment_id,
  rubric_digest, status, local_repo_path, commit_hash }, error: null, metadata: {...} }
- Error response: { success: false, data: null, error: { code, message }, metadata: {...} }

Implementation requirements:
1. Create TypeScript interfaces for SubmissionResponse, SubmissionData, ApiError, and
   ResponseMetadata in client/src/utils/api.types.ts.
2. The service method signature should be:
   submitEvaluation(githubUrl: string, assignmentId: string | null, rubricFile: File): Observable<SubmissionResponse>
3. Build the FormData object inside the method. Only append assignment_id if it is non-empty.
4. Use Angular's HttpClient to POST with the FormData. Do not manually set Content-Type —
   the browser sets it automatically with the boundary when using FormData.
5. For Milestone 1, add a hardcoded dev token via environment config:
   - Add `devToken: 'dev-token-placeholder'` to environment.ts
   - The service should attach `Authorization: Bearer ${environment.devToken}` on every request
   - Add a comment explaining this is a stub to be replaced when the login endpoint is live
6. Use catchError to return structured error objects instead of throwing.

After implementing:
- Show the full content of evaluation.service.ts and api.types.ts
- Note any open questions about the auth stub approach
```

---

## Prompt 4: Build The Submission Form Page

Use this after the evaluation service exists.

```text
Create the student submission form page at client/src/pages/submit-page/.

This page should be routed at /submit. Make it the default route (redirect from /).

Form fields:
1. GitHub URL (required)
   - text input
   - client-side validation: must be a non-empty string starting with https://github.com/
   - show an inline error if the URL is invalid before submission
2. Assignment ID (optional)
   - text input
   - no validation required
3. Rubric file (required)
   - file input, accept=".json,.txt"
   - show an inline error if no file is selected on submit attempt
4. Submit button
   - disabled while a request is in flight
   - shows "Submitting..." label during submission

Behavior:
- On successful response: navigate to /status/:submission_id, passing the full
  SubmissionData object via router state (router.navigate(['/status', id], { state: { data } }))
- On error response: display the error.message field prominently above the form
- On network error (Observable error): display a generic "Submission failed — check the
  console for details" message

Implementation notes:
- Use Angular Reactive Forms (FormGroup, FormControl, Validators)
- The file input is not part of the FormGroup — handle it separately via a template
  reference variable and a (change) event binding that captures the selected File object
- Use EvaluationService.submitEvaluation() for the HTTP call
- Keep the template simple: no modals, no toast libraries

After implementing, show the component TypeScript and HTML template.
```

---

## Prompt 5: Build The Status Display Page

Use this after the submission form exists.

```text
Create the status display page at client/src/pages/status-page/.

This page should be routed at /status/:id.

Behavior:
- On load, read router state first: if the component was navigated to from the submit form,
  `history.state.data` will contain the SubmissionData object — display it immediately.
- If router state is absent (e.g., user navigated directly by URL), show a placeholder
  message: "Status lookup is not yet available. A GET /submissions/:id endpoint is pending
  backend implementation."
- Do not make any HTTP calls in this component for Milestone 1. The polling endpoint does
  not exist yet.

Display when data is available:
- Submission ID (bold, prominent)
- Status badge: "cloned" or "cached" (green), or any other status (gray)
- GitHub URL
- Assignment ID (or "None" if absent)
- Commit hash (abbreviated to first 12 characters)
- Rubric digest (abbreviated to first 12 characters)
- A "Submit another" link that navigates back to /submit

Implementation notes:
- Type the component's data property as SubmissionData | null
- Use the existing SubmissionData interface from client/src/utils/api.types.ts
- Keep the template minimal — a simple card/box layout is fine

After implementing, show the component TypeScript and HTML template.
Do not add polling logic. Add a clearly visible comment where polling would go in a
future milestone.
```

---

## Prompt 6: Wire Up Routing And Verify Locally

Use this after both pages are built.

```text
Wire up Angular routing so the submission form and status page are reachable.

Routing configuration:
- /  →  redirect to /submit
- /submit  →  SubmitPageComponent
- /status/:id  →  StatusPageComponent
- **  →  redirect to /submit (catch-all)

After configuring routing:
1. Confirm AppRoutingModule (or app.routes.ts) contains the correct routes
2. Confirm AppComponent template contains <router-outlet>
3. Run `ng build` and report any TypeScript or template compilation errors
4. If there are errors, fix them before proceeding

Do not add navigation guards, lazy loading, or authentication redirects. Keep it as
simple as possible for Milestone 1.
```

---

## Prompt 7: Review For Milestone 1 Alignment

Use this after the Angular scaffold is built and compiles cleanly.

```text
Review the Angular scaffold against the Milestone 1 requirements in:

- docs/milestones/milestone-01-tasks.md
- docs/design-doc.md
- server/app/main.py (the evaluate endpoint contract)

Check each of the following:

1. Does the submission form send multipart/form-data (not JSON)?
2. Does it include all three required fields: github_url, rubric (file), and optional assignment_id?
3. Does it attach the Authorization header on the evaluate request?
4. Does it correctly navigate to /status/:id on success?
5. Does it display backend error messages when the request fails?
6. Does the status page display the SubmissionData returned from the backend?
7. Does the status page avoid making HTTP calls (since the GET endpoint doesn't exist yet)?
8. Does `ng build` complete without errors?

Return:
1. A checklist of the above items with pass/fail for each
2. Any requirement mismatches
3. A final verdict on whether Task 4 is complete
```

---

## One-Shot Prompt

Use this if you want a single prompt to do everything above in one pass.

```text
Implement Milestone 1, Task 4: Angular scaffold for the student submission form and status
display page.

Before writing any code, read:
- docs/milestones/milestone-01-tasks.md
- docs/design-doc.md
- server/app/main.py

The backend contract for POST /api/v1/code-eval/evaluate:
- multipart/form-data (not JSON)
- fields: github_url (string), assignment_id (string, optional), rubric (file upload)
- requires Authorization: Bearer <token> header
- success response includes submission_id, status, commit_hash, rubric_digest

Implement in order:
1. Initialize the Angular project inside client/ (--routing --style=scss --skip-git)
2. Add environment.ts with apiBaseUrl and a devToken placeholder for local dev auth
3. Create client/src/utils/api.types.ts with TypeScript interfaces for SubmissionResponse,
   SubmissionData, ApiError, ResponseMetadata
4. Create client/src/services/evaluation.service.ts with submitEvaluation() method that
   posts FormData with Authorization header
5. Create client/src/pages/submit-page/ with a reactive form for github_url (required,
   URL validated), assignment_id (optional), and rubric file input (required)
6. On form success, navigate to /status/:id passing SubmissionData via router state
7. On form error, display the backend error.message above the form
8. Create client/src/pages/status-page/ that reads SubmissionData from router state and
   displays submission_id, status, commit_hash, github_url; show a placeholder if
   navigated to directly (no polling yet)
9. Configure routing: / → /submit, /submit → form, /status/:id → status page
10. Run ng build and fix any compilation errors

Constraints:
- Use FormData for the HTTP request — do not send JSON to this endpoint
- Do not implement real auth; use a dev token stub from environment.ts
- Do not add polling HTTP calls on the status page — the GET endpoint doesn't exist yet
- Keep the UI plain; no external component libraries
- Place files in the existing client/src/ subdirectories

After completing, report:
- Files created
- ng build result
- Any open items or gaps relative to the milestone requirement
```
