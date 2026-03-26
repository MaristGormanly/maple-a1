---
name: Jayden M1 Infrastructure Breakdown
overview: Implementation-oriented breakdown of Jayden's six Milestone 1 Infrastructure and Deployment tasks (original four plus auth scaffold and systemd service), expanded into ordered actionable steps with dependencies, acceptance criteria, and cross-team interface notes, plus a section mapping Jayden's deliverables to the Milestone 1 end-to-end goal.
todos:
  - id: task1-repo-structure
    content: "Task 1: Create MAPLE directory tree, FastAPI stub, requirements.txt, .gitignore, README stub, branch setup"
    status: pending
  - id: task2-provision-do
    content: "Task 2: Provision DigitalOcean Droplet and Managed PostgreSQL"
    status: in_progress
  - id: task2b-app-platform
    content: "Task 2b: Create App Platform static site (Deferred pending GitHub approval)"
    status: pending
  - id: task3-nginx-ip
    content: "Task 3: Configure Nginx reverse proxy (proxy_pass to Uvicorn) using Droplet IP only -- domain and TLS deferred until domain is acquired"
    status: pending
  - id: task4-env-secrets
    content: "Task 4: Create .env.example, update .gitignore, implement config.py settings loader, deploy production .env on Droplet, document in deployment.md"
    status: pending
  - id: task5-auth-scaffold
    content: "Task 5: Auth scaffold -- create middleware/auth.py dependency stubs, utils/security.py (password hashing + JWT helpers), auth settings in config.py"
    status: pending
  - id: task6-systemd-service
    content: "Task 6: Create maple-a1.service systemd unit file so Uvicorn auto-starts on boot and can be managed via systemctl"
    status: pending
  - id: integration-verification
    content: "Integration: Coordinate with Dom/Sylvie to verify DB connectivity, API reachability via Nginx, and the E2E submission flow on the Droplet"
    status: pending
isProject: false
---

# Jayden -- Milestone 1 Infrastructure & Deployment: Implementation Breakdown

---

## Task 1: Initialize Repository per MAPLE Structure

The repo currently contains only top-level docs and prompts. The MAPLE Architecture Guide (Section 2) mandates a specific directory layout that Dom and Sylvie depend on before they can begin coding.

### Steps

1. **Create the canonical directory tree.** From the repo root, create:

```
maple-a1/
├── docs/
│   ├── design-doc.md          (move existing)
│   ├── api-spec.md            (placeholder)
│   └── deployment.md          (placeholder)
├── prompts/
│   ├── system/                (empty; production prompts go here later)
│   └── dev/                   (keep existing prompts-Jayden tree or restructure to guide convention: dev/jayden/, dev/dom/, dev/sylvie/)
├── server/
│   └── app/
│       ├── __init__.py
│       ├── main.py            (FastAPI entry point stub)
│       ├── routers/
│       ├── services/
│       ├── models/
│       ├── middleware/
│       └── utils/
├── client/
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── services/
│       └── utils/
├── data/
│   ├── raw/                   (.gitkeep; gitignored contents)
│   └── processed/
├── eval/
│   ├── test-cases/
│   ├── results/
│   └── scripts/
├── .gitignore                 (update with data/raw/*, .env, venv/, __pycache__/, etc.)
├── requirements.txt           (pin FastAPI, uvicorn, SQLAlchemy, asyncpg, python-dotenv, alembic)
└── README.md                  (stub per Section 7 of the Architecture Guide)
```

1. **Scaffold `server/app/main.py`** with a minimal FastAPI app that returns a health-check response at `GET /api/v1/code-eval/health`, conforming to the MAPLE Standard Response Envelope. This gives Dom and Sylvie an importable app instance and confirms the server boots.
2. **Create `dev` and `main` branches** per MAPLE branching strategy (Section 2). Protect `main`; all work merges through `dev`.
3. **Add a minimal `server/requirements.txt`** pinning:
  - `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `python-dotenv`, `httpx` (for GitHub API calls Sylvie will need), `pyjwt`, `passlib[bcrypt]`, `pydantic-settings`

### Dependencies

- None -- this is the first task and unblocks everything else.

### Acceptance Criteria

- `git clone` + `pip install -r server/requirements.txt` + `uvicorn server.app.main:app` boots without errors.
- `GET /api/v1/code-eval/health` returns `{"success": true, "data": {"status": "ok"}, ...}`.
- Directory layout matches MAPLE Architecture Guide Section 2.

### Interfaces with Other Owners

- **Dom** begins work in `server/app/models/` and `server/app/routers/` immediately after this step.
- **Sylvie** begins work in `server/app/services/` (ingestion) and `client/` (Angular scaffold).

---

## Task 2: Provision DigitalOcean Droplet, Managed PostgreSQL, and App Platform

All three cloud resources are described in [design-doc.md](design-doc.md) Section 6. Docker is installed during this step to support Milestone 2 sandboxed execution without re-provisioning later.

### Steps

1. **Create the DigitalOcean Droplet (4 GB RAM / 2 vCPU).**
  - Region: choose the closest to Marist (NYC1 or NYC3).
  - OS: Ubuntu 22.04 LTS.
  - Enable SSH key auth; disable password login.
  - Install runtime dependencies: Python 3.11+, pip, venv, Git, Nginx.
2. **Install Docker Engine (CE) on the Droplet.**
  - Follow the official Docker install for Ubuntu 22.04 (apt repository method).
  - Add the deploy user to the `docker` group so the FastAPI process can communicate with the Docker daemon via `/var/run/docker.sock` without `sudo`.
  - Enable the Docker daemon to start on boot: `sudo systemctl enable docker`.
  - Verify: `docker run hello-world` succeeds and `systemctl is-active docker` returns `active`.
3. **Create the Managed PostgreSQL cluster.**
  - Plan: Basic 1-node ($15/mo), PostgreSQL 16.
  - Same region as the Droplet for low latency.
  - Create a database named `maple_a1` and a dedicated user (not `doadmin` for app access).
  - Enable the `pgvector` extension: `CREATE EXTENSION IF NOT EXISTS vector;` (needed for Milestone 3, but cheap to enable now -- avoids a future migration blocker).
  - Add the Droplet's IP to the database trusted-sources allowlist.
4. **Create the App Platform static site** (for Angular frontend). *(DEFERRED: Waiting for GitHub org approval to link DO Apps. Will circle back later in the milestone).*
  - Connect to the repo's `client/` directory; build command `ng build --configuration production`; output dir `dist/`.
  - This can remain a placeholder until Sylvie has an Angular build, but the App Platform resource should exist so the deployment pipeline is proven.
5. **Record connection details** as entries for the `.env.example` (Task 4 below):
  - `DATABASE_URL`, `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_USER`, `DATABASE_PASSWORD`, `DATABASE_NAME`.
  - Droplet IP address, SSH key fingerprint.

### Dependencies

- Task 1 (repo must exist for App Platform to connect to).

### Acceptance Criteria

- SSH into Droplet succeeds with key auth.
- `psql` from the Droplet to the Managed PostgreSQL cluster succeeds; `SELECT 1;` returns.
- Docker is installed and daemon is active: `systemctl is-active docker` returns `active`.
- `docker run hello-world` succeeds without `sudo` for the deploy user.
- App Platform site returns a default page (even if placeholder) at its auto-assigned `*.ondigitalocean.app` URL.

### Interfaces with Other Owners

- **Dom** needs `DATABASE_URL` to run SQLAlchemy migrations (`alembic upgrade head`). Jayden provides this via `.env` / secrets management (Task 4).
- **Sylvie** needs the App Platform site configured so Angular builds deploy. Jayden sets up the resource; Sylvie owns the Angular build config.

---

## Task 3: Configure Nginx Reverse Proxy (IP-only; Domain and TLS Deferred)

Described in [design-doc.md](design-doc.md) Section 6 ("Domain & TLS"). Nginx sits in front of FastAPI so the backend never handles TLS directly. The domain name remains TBD, so this task configures Nginx using the Droplet's public IP address over HTTP. Once a domain is acquired, Certbot and HTTPS will be layered on top of this existing config with minimal changes (add `server_name`, run `certbot --nginx`).

### Steps

1. **Install and configure Nginx** on the Droplet.
  - Create `/etc/nginx/sites-available/maple-a1` with:
    - `server_name _;` (catch-all, since no domain yet).
    - `listen 80;`
    - `location /api/` -- `proxy_pass http://127.0.0.1:8000;` (FastAPI / Uvicorn).
    - `proxy_set_header Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto` headers.
    - Client max body size (e.g., `client_max_body_size 50M;`) to handle repo-related payloads.
  - Symlink to `sites-enabled`; remove the default site; `nginx -t && systemctl reload nginx`.
2. **Harden the Nginx config** (non-TLS hardening that applies now).
  - Disable server tokens (`server_tokens off;`).
3. **Verify end-to-end.**
  - `curl -I http://<DROPLET_IP>/api/v1/code-eval/health` returns `200` with the MAPLE response envelope.

### Future: Domain and TLS (not blocked, do when domain is acquired)

When the domain is registered via Namecheap:

1. Create an A record pointing the domain to the Droplet's public IP.
2. Update `server_name` in the Nginx config from `_` to the domain.
3. Install Certbot: `sudo apt install certbot python3-certbot-nginx`.
4. Obtain cert: `sudo certbot --nginx -d <domain>`.
5. Add TLS hardening: `ssl_protocols TLSv1.2 TLSv1.3;`, `Strict-Transport-Security` header.
6. Verify: `sudo certbot renew --dry-run`.

### Dependencies

- Task 1 (FastAPI stub running so proxy has a backend).
- Task 2 (Droplet provisioned, Nginx installed).

### Acceptance Criteria

- `curl -I http://<DROPLET_IP>/api/v1/code-eval/health` returns `200` with the MAPLE envelope.
- Nginx error log shows no warnings on `nginx -t`.
- Nginx starts on boot: `systemctl is-enabled nginx` returns `enabled`.

### Interfaces with Other Owners

- **Dom's** API endpoints (e.g., `POST /api/v1/code-eval/rubrics`) will be reachable at `http://<DROPLET_IP>/api/v1/code-eval/rubrics` with no additional work once Nginx is configured.
- **Sylvie's** Angular app polls the same base URL for submission status. Once a domain is set, Sylvie updates `API_BASE_URL` in the Angular build; for now, the Droplet IP is used directly.

---

## Task 4: Implement `.env` / Secrets Management; `.env.example` Committed

Described in [design-doc.md](design-doc.md) Section 6 ("Environment Management") and Architecture Guide Section 1 (prohibited list) and Section 6 (security baseline).

### Steps

1. **Create `.env.example`** at the repo root with placeholder keys and comments:

```
# -- Database (DigitalOcean Managed PostgreSQL) --
DATABASE_URL=postgresql+asyncpg://user:password@host:25060/maple_a1?sslmode=require
DATABASE_HOST=localhost
DATABASE_PORT=25060
DATABASE_USER=maple_app
DATABASE_PASSWORD=changeme
DATABASE_NAME=maple_a1

# -- Application --
APP_ENV=development          # development | production
APP_HOST=0.0.0.0
APP_PORT=8000
SECRET_KEY=changeme          # used for signing JWT tokens

# -- Auth --
ACCESS_TOKEN_EXPIRE_MINUTES=30
ALGORITHM=HS256

# -- GitHub (Sylvie's ingestion pipeline) --
GITHUB_PAT=ghp_xxxxxxxxxxxx

# -- LLM API Keys (Milestone 3, but placeholder now) --
GEMINI_API_KEY=changeme
OPENAI_API_KEY=changeme

# -- CORS --
CORS_ORIGINS=http://localhost:4200
```

1. **Update `.gitignore`** to include `.env`, `data/raw/*`, `__pycache__/`, `*.pyc`, `venv/`, `.venv/`, `node_modules/`, `dist/`.
2. **Implement settings loading in `server/app/`.**
  - Create `server/app/config.py` using `pydantic-settings` that reads `.env` at startup and exposes a typed `Settings` singleton.
  - Include auth-related settings: `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`.
  - All service modules import `settings` rather than calling `os.getenv()` directly, ensuring a single source of truth and early failure on missing vars.
3. **Deploy the production `.env` on the Droplet.**
  - Place the real `.env` in the project directory on the Droplet (or in `/etc/maple-a1/.env` and symlink).
  - Verify: `uvicorn server.app.main:app` on the Droplet reads the correct `DATABASE_URL` and connects to Managed PostgreSQL.
4. **Document secrets management** in `docs/deployment.md` -- how to rotate keys, where the `.env` lives on the Droplet, what happens if a secret is compromised.

### Dependencies

- Task 2 (database and Droplet must be provisioned to populate real values).
- Logically pairs with Task 1 (`.env.example` and `.gitignore` are repo-level files).

### Acceptance Criteria

- `.env.example` is committed and contains every key the app needs, with safe placeholder values.
- `.env` is in `.gitignore` and never appears in `git log`.
- FastAPI boots on the Droplet and connects to the managed DB using only environment variables.
- `grep -r "ghp_" server/` returns zero matches (no hardcoded secrets).

### Interfaces with Other Owners

- **Dom** imports `settings.DATABASE_URL` from `config.py` to configure SQLAlchemy.
- **Sylvie** imports `settings.GITHUB_PAT` for the cloning service. Jayden ensures the variable is present in `.env.example` and loaded in `config.py`; Sylvie writes the cloning code.

---

## Task 5: Auth Scaffold

The Milestone 1 goal explicitly requires an "auth scaffold." This task creates the foundational auth infrastructure -- middleware stubs, security utilities, and settings -- so Dom can wire up user registration/login routes and Sylvie can protect frontend routes. This is the scaffold only; full user model, registration endpoint, and login flow are Dom's scope.

### Steps

1. **Create `server/app/utils/security.py`** with:
  - `hash_password(password: str) -> str` -- wraps `passlib.hash.bcrypt`.
  - `verify_password(plain: str, hashed: str) -> bool` -- wraps bcrypt verify.
  - `create_access_token(data: dict, expires_delta: timedelta | None = None) -> str` -- creates a JWT using `python-jose` or `pyjwt`, signing with `settings.SECRET_KEY` and `settings.ALGORITHM`.
  - `decode_access_token(token: str) -> dict` -- decodes and validates a JWT; raises on expiry or tamper.
2. **Create `server/app/middleware/auth.py`** with:
  - A FastAPI `Depends` callable `get_current_user(token: str = Depends(oauth2_scheme)) -> dict` that extracts the bearer token from the `Authorization` header, decodes it via `decode_access_token`, and returns the user payload (or raises `HTTPException(401)`).
  - An `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/code-eval/auth/login")` instance that Dom's login router will fulfill.
  - A `require_role(role: str)` dependency factory that checks `current_user["role"]` against the required role (e.g., `Instructor`), raising `HTTPException(403)` on mismatch.
3. **Add auth settings to `server/app/config.py`:**
  - `SECRET_KEY: str`
  - `ALGORITHM: str = "HS256"`
  - `ACCESS_TOKEN_EXPIRE_MINUTES: int = 30`
4. **Add placeholder auth router** at `server/app/routers/auth.py`:
  - `POST /api/v1/code-eval/auth/login` -- stub that returns `501 Not Implemented` with a MAPLE error envelope. Dom will replace this with the real implementation once the User model exists.
  - `POST /api/v1/code-eval/auth/register` -- same stub pattern.
  - Wire the router into `main.py` via `app.include_router(auth_router)`.
5. **Add dependencies to `server/requirements.txt`** (if not already present from Task 1):
  - `pyjwt`, `passlib[bcrypt]`

### Dependencies

- Task 1 (repo structure and `config.py` must exist).
- Task 4 (`SECRET_KEY` must be in `.env.example` and `config.py`).

### Acceptance Criteria

- Importing `from server.app.utils.security import create_access_token, verify_password` works.
- Importing `from server.app.middleware.auth import get_current_user, require_role` works.
- The stub login/register endpoints return `501` with proper MAPLE error envelope.
- `uvicorn server.app.main:app` still boots cleanly with the auth router included.

### Interfaces with Other Owners

- **Dom** replaces the stub auth router with real registration and login logic once the `User` SQLAlchemy model and Alembic migration are in place. Dom uses `hash_password` and `create_access_token` from `utils/security.py`.
- **Dom** applies `get_current_user` and `require_role("Instructor")` as dependencies on protected endpoints like `POST /rubrics`.
- **Sylvie** stores the JWT in the Angular app and sends it as `Authorization: Bearer <token>` on API calls. The `oauth2_scheme` in the middleware handles extraction.

---

## Task 6: Create systemd Service for Uvicorn

The design doc specifies manual `git pull` + service restart for CI/CD, but does not describe how the FastAPI process stays alive across reboots. This task creates a systemd unit file so Uvicorn is managed as a proper Linux service.

### Steps

1. **Create the systemd unit file** at `/etc/systemd/system/maple-a1.service`:

```ini
[Unit]
Description=MAPLE A1 FastAPI (Uvicorn)
After=network.target docker.service
Wants=docker.service

[Service]
Type=simple
User=maple
Group=maple
WorkingDirectory=/opt/maple-a1
EnvironmentFile=/opt/maple-a1/.env
ExecStart=/opt/maple-a1/venv/bin/uvicorn server.app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

- Adjust `User`, `WorkingDirectory`, and `EnvironmentFile` paths to match the actual deploy layout on the Droplet.
- `--workers 2` matches the 2-vCPU Droplet. Increase if the Droplet is scaled up.
- `After=docker.service` ensures Docker is available before FastAPI starts (relevant for Milestone 2 when the app needs the Docker daemon).

1. **Enable and start the service.**
  - `sudo systemctl daemon-reload`
  - `sudo systemctl enable maple-a1`
  - `sudo systemctl start maple-a1`
  - Verify: `systemctl status maple-a1` shows `active (running)`.
2. **Test reboot survival.**
  - `sudo reboot`; after the Droplet comes back, verify `systemctl is-active maple-a1` returns `active` and `curl http://127.0.0.1:8000/api/v1/code-eval/health` returns `200`.
3. **Document the service commands** in `docs/deployment.md`:
  - `sudo systemctl restart maple-a1` (after `git pull` to pick up new code).
  - `sudo journalctl -u maple-a1 -f` (tail logs).

### Dependencies

- Task 2 (Droplet provisioned).
- Task 1 (FastAPI stub exists to run).
- Task 4 (`.env` deployed on the Droplet).

### Acceptance Criteria

- `systemctl is-enabled maple-a1` returns `enabled`.
- After a Droplet reboot, `curl http://127.0.0.1:8000/api/v1/code-eval/health` returns `200` without manual intervention.
- `sudo journalctl -u maple-a1 --no-pager -n 20` shows Uvicorn startup logs.

### Interfaces with Other Owners

- **Dom and Sylvie** use `sudo systemctl restart maple-a1` after deploying new code to the Droplet. This is documented in `docs/deployment.md`.

---

## Milestone 1 / Ingestion Alignment

This section maps Jayden's outcomes to the **Milestone 1 deliverable** ("student submits a URL, system clones and pre-processes the repo, returns a `submission_id`") and the **Integration Point** described in [milestone-01-tasks.md](milestone-01-tasks.md).

```mermaid
flowchart LR
    subgraph jayden [Jayden: Infrastructure]
        Repo["Repo structure + FastAPI stub"]
        Droplet["DO Droplet + Docker"]
        DB["Managed PostgreSQL"]
        Nginx["Nginx reverse proxy (IP)"]
        Env[".env / secrets"]
        Auth["Auth scaffold"]
        Systemd["systemd service"]
    end

    subgraph dom [Dom: Backend API / DB]
        Schema["SQLAlchemy schema + migrations"]
        RubricEP["POST /rubrics endpoint"]
        AuthRoutes["Auth login/register"]
    end

    subgraph sylvie [Sylvie: Ingestion / Frontend]
        Clone["GitHub clone service"]
        PreProc["Pre-processor"]
        Angular["Angular submission form"]
    end

    Repo --> Schema
    Repo --> Clone
    Repo --> Angular
    DB --> Schema
    Env --> Schema
    Env --> Clone
    Droplet --> Clone
    Nginx --> Angular
    Auth --> AuthRoutes
    Systemd --> Droplet
    Schema --> RubricEP
    Clone --> PreProc
    PreProc -->|"submission_id"| RubricEP
```



### What Jayden must expose or configure so the E2E flow can run

- **Repo structure with `server/app/main.py` stub** -- Dom can add routers/models; Sylvie can add services and Angular scaffold. Consumer: Dom, Sylvie.
- **Droplet with Python 3.11+, Docker, Git** -- FastAPI runs; Sylvie's clone service can call `git`; Docker ready for M2 sandboxing. Consumer: Dom, Sylvie.
- **Managed PostgreSQL (with `pgvector` extension)** -- Dom runs `alembic upgrade head` to create schema; app persists `Submission` rows and returns `submission_id`. Consumer: Dom.
- **Nginx reverse proxy (IP-based, HTTP)** -- Angular frontend and API clients can reach `/api/v1/code-eval/`* via the Droplet IP. TLS added when domain is acquired. Consumer: Sylvie (frontend).
- `**.env` with `DATABASE_URL`, `GITHUB_PAT`, `SECRET_KEY`** -- Dom's DB code and Sylvie's clone code read credentials at runtime without hardcoding. Consumer: Dom, Sylvie.
- `**CORS_ORIGINS` configured for Angular dev server** -- Sylvie can develop locally at `localhost:4200` and hit the API without CORS errors. Consumer: Sylvie.
- **Auth scaffold (`security.py`, `middleware/auth.py`, stub routes)** -- Dom wires up real login/register; protected endpoints can use `get_current_user` dependency immediately. Consumer: Dom, Sylvie.
- **systemd service** -- FastAPI survives reboots; team can restart after deploy with a single `systemctl` command. Consumer: Dom, Sylvie, Jayden.

### What Jayden does NOT own (out of scope)

- The actual cloning logic, pre-processor, or caching -- that is Sylvie's work.
- The SQLAlchemy models (including User), Alembic migrations, or `/rubrics` endpoint -- that is Dom's work.
- The real auth login/register logic (replacing the stubs) -- that is Dom's work.
- The Angular scaffold -- that is Sylvie's work.

### Recommended integration sequence near end of milestone

1. Dom runs `alembic upgrade head` on the Droplet using the `.env` Jayden deployed.
2. Dom replaces the auth stub routes with real login/register backed by the `User` model.
3. Sylvie deploys the FastAPI app (with Dom's routers and Sylvie's ingestion service) to the Droplet.
4. `sudo systemctl restart maple-a1` to pick up the new code.
5. Sylvie deploys Angular to App Platform.
6. Team verifies: submit URL via Angular -> Nginx -> FastAPI -> clone + pre-process -> `submission_id` returned.

---

## Resolved Gaps

1. **Domain name is TBD.** Confirmed. Task 3 now configures Nginx with IP-only. TLS (Certbot) will be layered on when a domain is acquired. This does not block any Milestone 1 work.
2. **Docker installed now.** Confirmed. Docker Engine is installed during Task 2 provisioning and verified as part of acceptance criteria. Ready for Milestone 2 sandboxed execution.
3. **Auth scaffold.** Confirmed as Jayden's scope. Task 5 creates the JWT utilities, auth middleware stubs, and placeholder routes. Dom owns the real implementation.
4. **Systemd service for Uvicorn.** Confirmed. Task 6 creates `maple-a1.service` so the FastAPI process auto-starts on boot and is manageable via `systemctl`.

