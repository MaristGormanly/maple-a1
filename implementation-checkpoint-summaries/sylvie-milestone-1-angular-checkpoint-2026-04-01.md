# Sylvie Milestone 1 Checkpoint Summary

# Date: 4/1/26

## Context and Scope

This checkpoint summarizes the work completed in this session for **Sylvie's portion of Milestone 1** of MAPLE A1. Specifically, this session closes the one item left open in the previous checkpoint (2026-03-29): the Angular scaffold.

The previous checkpoint noted:

> **"I have not completed the Angular framework that is required to complete my milestone."**

That item is now complete. All four of Sylvie's Milestone 1 tasks are implemented and verified.

---

## What Was Outstanding Before This Session

The prior checkpoint covered Tasks 1–3 in full:
- GitHub PAT-based repository cloning into `data/raw/`
- Repository pre-processor stripping `node_modules`, `venv`, compiled binaries, `.git`
- SHA + normalized rubric digest caching key; cache hit skips re-cloning

The only incomplete item was:
- **Task 4: Angular scaffold — student submission form (GitHub URL + assignment ID), status page**

---

## Core Changes Made in This Session

### 1. Angular Project Initialized in `client/`

An Angular 21 project was initialized inside `client/` using the Angular CLI:

```
ng new maple-client --routing --style=scss --skip-git --directory . --force
```

The `--force` flag was needed because the directory already contained the four placeholder subdirectories (`components/`, `pages/`, `services/`, `utils/`). Those subdirectories were preserved alongside Angular's generated `src/app/` structure.

Angular 21 uses the standalone component architecture — there is no `AppModule`. Bootstrap and providers are configured in `src/app/app.config.ts`. `provideHttpClient()` was added to this file to enable Angular's HTTP client across the app.

### 2. Environment Configuration Added

`src/environments/environment.ts` and `src/environments/environment.prod.ts` were created with:

- `apiBaseUrl`: `http://localhost:8000` for local dev, empty string for prod (relative URL)
- `devToken`: a signed JWT for authenticating against the backend during local development

The dev token is a real signed JWT — not a placeholder string. It was generated using `create_access_token()` from `server/app/utils/security.py` against the `SECRET_KEY` set in `.env`. A plain string will not pass the backend's `jwt.decode()` validation.

`ACCESS_TOKEN_EXPIRE_MINUTES` in `.env` was extended to `43200` (30 days) to avoid token expiry during Milestone 1 development. The token was regenerated after this change.

### 3. TypeScript API Types Created

`client/src/utils/api.types.ts` defines four interfaces that mirror the backend response models exactly as defined in `server/app/main.py`:

- `SubmissionData` — maps to the `SubmissionData` Pydantic model
- `SubmissionResponse` — maps to the `SubmissionResponse` Pydantic model
- `ApiError` — maps to the `ErrorDetails` Pydantic model
- `ResponseMetadata` — maps to the `ResponseMetadata` Pydantic model

These interfaces are the shared contract between the Angular service layer and the backend. Any future backend response shape changes must be reflected here.

### 4. EvaluationService Created

`client/src/services/evaluation.service.ts` wraps `POST /api/v1/code-eval/evaluate`.

Key implementation decisions:

- **FormData, not JSON.** The endpoint is `multipart/form-data`. The service uses `new FormData()` as the POST body. `Content-Type` is never set manually — the browser sets it automatically with the correct multipart boundary when `FormData` is passed to `HttpClient`.
- **`assignment_id` omitted when empty.** The field is only appended to `FormData` if non-empty. An empty string would be sent as a string, not as `null`.
- **Authorization header.** `Authorization: Bearer ${environment.devToken}` is attached on every request via `HttpHeaders`. The TODO comment marks this as a stub to be replaced when `POST /api/v1/code-eval/auth/login` is implemented in Milestone 2.
- **`catchError` normalises all failures.** Both HTTP errors (4xx/5xx from the backend) and network failures are caught and converted into a `SubmissionResponse` with `success: false`, so component code never needs to handle a thrown Observable error.

### 5. Submit Page Built

`client/src/pages/submit-page/` contains the student submission form, routed at `/submit` (default route from `/`).

Form fields:
- `githubUrl` — required; validated with `/^https:\/\/github\.com\/[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+\/?$/`. The pattern enforces that both an owner segment and a repo segment are present. An earlier, too-permissive pattern (`/^https:\/\/github\.com\/.+/`) was identified in an audit and corrected in this session.
- `assignmentId` — optional, no validation
- `rubric` — file input (`accept=".json,.txt"`), handled outside the `FormGroup` via a `(change)` event binding

On success: navigates to `/status/:submission_id` passing the full `SubmissionData` object via router state.

On error: displays `response.error.message` prominently above the form. If the error is a network failure (no HTTP response), displays a generic fallback message.

The submit button is disabled and relabelled "Submitting..." while a request is in flight.

### 6. Status Page Built

`client/src/pages/status-page/` displays the submission result, routed at `/status/:id`.

On load, `ngOnInit` reads `history.state.data` — populated by the submit page's `router.navigate(..., { state: { data } })` call.

**If data is present:** Displays submission ID, status badge (green for `cloned` or `cached`, unstyled for anything else), GitHub URL, assignment ID (or "None"), abbreviated commit hash (12 chars), abbreviated rubric digest (12 chars), and a "Submit another" link.

**If data is absent** (user navigated directly by URL or refreshed): Displays a placeholder message noting that `GET /api/v1/code-eval/submissions/:id` is pending backend implementation. No HTTP calls are made from this component.

A clearly marked TODO comment in `ngOnInit` marks where polling logic should be added when Dom implements the GET endpoint in Milestone 2.

### 7. Routing Configured

`client/src/app/app.routes.ts` final routing table:

| Path | Behaviour |
|---|---|
| `/` | redirect → `/submit` |
| `/submit` | `SubmitPageComponent` |
| `/status/:id` | `StatusPageComponent` |
| `**` | redirect → `/submit` |

`client/src/app/app.html` was replaced with `<router-outlet />` (the generated placeholder template was removed).

### 8. Local Dev Environment Set Up

- **Python virtualenv** created at `server/.venv` with `requirements.txt` installed
- **`.env`** created from `.env.example` with a generated `SECRET_KEY` and `GITHUB_PAT` filled in
- All environment values needed to run the server locally are now present

---

## Audit Findings Addressed in This Session

A full audit of all four Milestone 1 tasks was run against the codebase before this checkpoint was written. Findings addressed:

1. **URL regex too permissive** — Fixed. Pattern now enforces `owner/repo` structure client-side.
2. **Dev token must be a real JWT** — The original prompt suggested a plain placeholder string. This was identified as incorrect before implementation. A properly signed JWT was generated and placed in `environment.ts`.
3. **`ACCESS_TOKEN_EXPIRE_MINUTES` too short** — Extended to 30 days to avoid expiry during development.

---

## Remaining Incomplete or Deferred Items

The following items are **not** claimed as complete by this checkpoint:

- **`GET /api/v1/code-eval/submissions/:id` endpoint** — not implemented. Required for status polling. Depends on Dom's Milestone 2 backend work.
- **Real auth/login flow** — `POST /api/v1/code-eval/auth/login` is not implemented. The Angular app uses a dev token stub. The `devToken` in `environment.ts` must be replaced when the login endpoint is live.
- **Multi-worker cache safety** — The JSON cache index at `data/cache/repository-cache-index.json` is not safe for concurrent writes across multiple backend workers. Acceptable for Milestone 1 single-worker local dev; must be migrated to a database or distributed cache before production multi-instance deployment.
- **Dev token committed in `environment.ts`** — The signed JWT is tracked in git. This is acceptable for Milestone 1 local dev but must be replaced with a real auth flow before any production or shared environment deploy.

---

## Integration Notes for Dom and Jayden

**For Dom:**
- The Angular status page has a TODO at `status-page.component.ts:19–21` marking exactly where `GET /api/v1/code-eval/submissions/:id` should be called once the endpoint exists.
- The Angular types in `client/src/utils/api.types.ts` must stay in sync with any future changes to the `SubmissionResponse` or `SubmissionData` Pydantic models in `main.py`.

**For Jayden:**
- CORS is configured for `http://localhost:4200` (`CORS_ORIGINS` in `.env`). If Angular's dev server is run on a different port, this value must be updated before requests will succeed.
- `GITHUB_PAT` must be set in the server environment before the app boots. The `get_required_github_pat()` function checks `os.getenv()` at call time, so setting it post-startup will not work with the current settings model.
- The `data/cache/` directory must be writable and persistent across restarts. It is created automatically by the cache layer if absent.
- `ng build` output is at `client/dist/maple-client/`. This is the directory to serve as static files.

---

## Testing and Validation Completed

- `ng build` completed without errors or warnings at the end of this session.
- All eight checklist items from the Milestone 1 Angular scaffold review were verified as passing:
  1. Sends `multipart/form-data`
  2. Includes all three required fields
  3. Attaches `Authorization` header
  4. Navigates to `/status/:id` on success
  5. Displays backend error messages on failure
  6. Status page displays `SubmissionData`
  7. Status page makes no HTTP calls
  8. `ng build` clean

---

## Final Summary

This session completes Sylvie's Milestone 1 scope. All four tasks are now implemented:

1. GitHub PAT-based repository cloning *(completed prior session)*
2. Repository pre-processor *(completed prior session)*
3. SHA + rubric digest caching key *(completed prior session)*
4. Angular scaffold — **completed this session**

A student can now open the Angular app at `http://localhost:4200`, submit a GitHub URL and rubric file, and receive a `submission_id` back from the backend. The end-to-end Milestone 1 deliverable is functional for local development.

Outstanding items (status page polling, real auth) are explicitly deferred to Milestone 2 and clearly marked in the code with TODO comments.
