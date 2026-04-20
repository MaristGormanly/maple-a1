# Prompt 02 — Deployment documentation refactor (agent instructions)

## Original prompt (archived)

> *Preserved verbatim from the author. Slight typo in source: “Contect” → “Context” left as-is inside the quote.*

> **Role:** An expert Software Engineer that specializes in making readable documentation.
>
> **Task:**
>
> 1. Review `docs/deployment.md` and find any repetetive instructions or unorganized subsections.
> 2. Plan a new deployment document that allows a new engineer to the codebase to easily understand how to work in the production environment.
> 3. Give verbose instructions on mimicking production logic in a local environment under its own section. There should be instructions for duplicating production database schemas once it is created.
> 4. Make it clear and explicit when the server administrator (Jayden) needs to be contacted. Include what commands and detailed steps Jayden needs to take in order to give permissions to other users in the Digital Ocean production environment.
>
> **Contect:** Review `docs/design-doc.md` to resolve ambigutity or ask me questions to resolve amiguity.
>
> **Reminders:**
>
> 1. Make sure the content of the file remains intact.
> 2. Do not make up coding or system logic. Only use the context and `docs/design-doc.md` source of truth documents.
> 3. Be extremely specific and detailed when explaining steps. It should be assumed that anyone reading this document is new to the codebase environment and production VPS architecture of Digital Ocean.

---

## Expanded agent prompt (use this to execute the work)

You are refactoring **only** `docs/deployment.md` in the MAPLE A1 repository. Your output is an **edited `docs/deployment.md`** (and optionally minimal cross-links elsewhere **only if the user explicitly asks**; default is **do not** create or edit other markdown files). Follow every constraint below.

### 1. Authoritative sources (strict order)

1. **`docs/design-doc.md`** — Use it to resolve **architecture intent**, component relationships, and **planned** infrastructure (what the system is *supposed* to include). When `docs/deployment.md` and `docs/design-doc.md` differ, **do not silently “fix” facts**: either (a) present both with explicit labels such as **“As deployed today (from deployment.md)”** vs **“Target / design (from design-doc.md)”**, or (b) add a short **“Open questions for Jayden”** bullet list and stop short of inventing reconciliation.
2. **`docs/deployment.md`** — Treat every **concrete operational fact** already written here as content that must **remain accurate and present** after your edit (IP addresses, hostnames, paths, usernames, service names, command sequences, tables). **“Content remains intact”** means: no removal of true operational detail; you may **reorder, deduplicate, and rephrase** for clarity, but you must **preserve** all substantive instructions and facts unless the user later confirms an error.
3. **`.env.example`** — Use **only** for **variable names**, example shapes, and comments that already appear there. Do **not** invent new environment variables or claim runtime behavior not described in `docs/design-doc.md` or existing code you have **read** in this repo.

**Forbidden:** Inventing repository layout, scripts, endpoints, Docker commands, migration state, or server configuration that is **not** in those sources or **not** verifiable from files you actually open in the workspace (e.g. `server/`, CI configs). If something is required by the design doc but **not** implemented or not documented in-repo, state that gap explicitly instead of fabricating steps.

### 2. First-pass analysis (do this before rewriting)

1. Read **`docs/deployment.md`** end-to-end and produce a **private inventory** (in your reasoning, not necessarily in the doc) of:
   - **Repeated ideas** (e.g. database access described in more than one place, Jayden escalation repeated, SSH vs `maple` user context repeated).
   - **Subsections that jump between audiences** (new hire vs Jayden vs emergency).
   - **Cross-references** that assume prior knowledge (e.g. “see section X” without a stable heading anchor).
2. Read **`docs/design-doc.md`** focusing on:
   - **§2 System Architecture** (FastAPI, PostgreSQL, pgvector, Docker sandbox, LLM layer — only where relevant to **deployment and environments**).
   - **§6 Deployment and Infrastructure Plan** (DigitalOcean Droplet, Managed PostgreSQL, App Platform for Angular, CI/CD expectations, Nginx/TLS, secrets).
   - **§8 Timeline and Milestones** items that mention provisioning, `.env`, CORS, rate limits, or production checks — **only** to clarify intent where `docs/deployment.md` is silent.
3. Reconcile **known tension** without fabrication:
   - **Design doc** describes (among other things) an Angular frontend on **DigitalOcean App Platform**, a **4GB/2vCPU** Droplet, Docker via **`/var/run/docker.sock`**, **Managed PostgreSQL with pgvector**, **GitHub Actions** on `dev`, manual deploy for pilot, **domain + Certbot**.
   - **Current `docs/deployment.md`** states **Ubuntu 22.04** Droplet at **`161.35.125.120`**, **Nginx (IP-only for now)**, **systemd `maple-a1.service`**, **Managed PostgreSQL 16**, deploy via **`git pull` on `main`**, app under **`/opt/maple-a1`**, **`maple`** user for app work, **`root`** for SSH and service restart.
   - Where design and current doc disagree (e.g. branch name `dev` vs `main`, App Platform vs not mentioned, domain/TLS vs IP-only), **document the delta explicitly** in `docs/deployment.md` in a small **“Design vs current deployment”** or **“Known gaps”** subsection **without** claiming the unmentioned pieces are already done unless you have evidence in-repo.

### 3. Target structure for the new `docs/deployment.md` (outline)

Reorganize into a **linear onboarding path** for a **new engineer**, then **reference** sections. Suggested top-level sections (titles adjustable, order logical):

1. **Purpose and audience** — Who this doc is for; read order; link to `docs/design-doc.md` for product/architecture depth.
2. **Production architecture at a glance** — Table or short diagram **consistent with facts already in `docs/deployment.md`**, augmented **only** with non-contradictory bullets from **`docs/design-doc.md` §6** (clearly labeled if aspirational).
3. **Access and accounts** — DigitalOcean dashboard, GitHub/org access **only if stated** in existing docs; do not invent org names.
4. **SSH and server users** — `root` vs `maple`, keypair rules, **exact commands already documented** (ed25519 example, `ssh -i ... root@161.35.125.120`, `su - maple`, path `/opt/maple-a1`). Preserve Jayden’s obligation for `authorized_keys`.
5. **Environment variables** — Local vs production paths; table of variable **groups** as already documented; **no new secrets**.
6. **Database connectivity** — Single consolidated section: from Droplet as `maple` using `.env` fields; note `DATABASE_URL` vs `psql` and `+asyncpg`; laptop access (tunnel vs trusted IP) in one place; Jayden’s role once.
7. **Deploy procedure** — Preserve the **exact** command block (SSH → `su - maple` → `cd /opt/maple-a1` → `git pull origin main` → venv → `pip install` → `alembic upgrade head` → `exit` → `systemctl restart maple-a1`). If the repo **does not yet** contain Alembic migration files, add a **non-fabricated** note: e.g. that `alembic upgrade head` is the **intended** command per current documentation and Milestone expectations in `docs/design-doc.md`, and that engineers should confirm migration layout in `server/` before running — **only after you verify the repo state**; if migrations are absent, say so explicitly.
8. **Logs, restarts, secret rotation** — Consolidate `journalctl`, compromised secret steps without duplicating Jayden contact blocks unnecessarily (one primary escalation table + cross-links).
9. **NEW: Local development and mimicking production** — See §4 below (mandatory, verbose subsection).
10. **NEW: Copying / duplicating production database schema locally** — See §5 below (mandatory).
11. **NEW: When to contact Jayden (server administrator)** — See §6 below (mandatory); must include **DigitalOcean permissioning** steps for Jayden.
12. **Quick reference** — One-page table: scenario → action → who → link to section.

Use **consistent heading anchors** and **avoid repeating** the same Jayden paragraph in five places; use **one** canonical callout and **“See § When to contact Jayden.”**

### 4. Required section — “Local development and mimicking production” (verbose)

Write for a reader who has **never** seen this repo. Base content **only** on:

- **`docs/design-doc.md`**: local FastAPI service, PostgreSQL persistence, Docker for **sandboxed** execution, env-based secrets, need for **pgvector** in managed DB for RAG (when that milestone applies).
- **`.env.example`**: how to create `.env`, variable groups, local vs production-like values.
- **Existing `docs/deployment.md`**: production paths and behaviors to **mirror conceptually** (not copy secrets).

You **must**:

1. Explain **what “production-like” means** in MAPLE A1 terms: same **categories** of dependencies (Postgres, env vars, optional Docker for execution) **without** claiming identical hardware or DigitalOcean networking.
2. Step-by-step **local setup** at a high level: clone repo, Python venv location if documented in README or `server/` — **if not documented**, say “follow README” or “standard Python venv under `server/`” **only** if true after reading README; otherwise state the gap.
3. Call out **differences** explicitly: e.g. production uses **Managed PostgreSQL** and **SSL**; local often uses **localhost** Postgres; production uses **systemd**; local uses **manual uvicorn** or project scripts **only if documented**.
4. Reference **`docs/design-doc.md`** for **Docker sandbox** and **`/var/run/docker.sock`** on the Droplet so locals understand **why** Docker may be required for full behavior — **do not** invent docker-compose files unless they exist in the repo.

You **must not** invent Makefile targets, npm scripts, or “run this one command” orchestration unless they exist in committed files you verified.

### 5. Required section — “Duplicating production database schemas locally” (after production DB exists)

This section addresses **schema parity**, not copying **student data** (warn about **PII/FERPA**; `docs/design-doc.md` §7 mentions privacy considerations).

1. **Preferred path (when the repo has Alembic migrations):** Explain that schema should be applied locally with the **same migration chain** as production (e.g. `alembic upgrade head`), using a **local** Postgres instance and a **local** `.env` pointing at it — **only** if Alembic is actually configured in-repo; **if not**, state clearly that migrations are **not yet present** and that this subsection applies **once** they exist, per **`docs/design-doc.md` §8 Milestone 1**.
2. **Optional path (dump/restore):** Describe **conceptually** that an admin may use `pg_dump`/`pg_restore` for schema-only or full dumps **with Jayden approval** for anything touching production. **Do not** invent dump flags; give **generic** examples (`pg_dump --schema-only`) as **illustrative** and tell the reader to confirm with Jayden and official PostgreSQL docs.
3. **pgvector:** If `docs/design-doc.md` requires pgvector, state that **local Postgres must enable the extension** to mirror production RAG storage — **without** inventing DigitalOcean-specific extension enablement steps unless in `docs/deployment.md`.

### 6. Required section — “When to contact Jayden” + DigitalOcean permissions (Jayden runbook)

**For all engineers:** Use a **decision table**: each row = trigger (e.g. need DO dashboard, SSH, secrets, laptop DB access, compromised secret, unclear doc), **what not to do** (share private keys, paste `.env` in Slack), and **what Jayden does**.

**For Jayden (DigitalOcean production environment — permissions for other users):** You must add a subsection **“Jayden: granting access (DigitalOcean, Droplet, database)”** that is **actionable** and **honest about evidence**:

1. **Include every Jayden responsibility already listed** in the current `docs/deployment.md` (team invite, SSH `authorized_keys`, secure channel for secrets, trusted IP / tunnel for DB, assisting secret rotation).
2. **DigitalOcean control plane (team members and roles):** The repository may **not** document exact DigitalOcean UI copy. You **may** add steps **only** if you label them clearly as **“Standard DigitalOcean team workflow (verify in current DigitalOcean docs/UI)”** and you **prefer citing** official DigitalOcean documentation URLs for:
   - Inviting users to a **Team** or **Project**
   - Role types (e.g. **Owner**, **Member**, **Billing**) — **do not** assert specific permission matrices; point to DigitalOcean’s role documentation
   - **Managed Database trusted sources** / firewall rules for Droplet and developer IPs
3. **SSH / Droplet:** Provide **concrete Linux steps** for Jayden that are **standard** and **aligned** with current doc:
   - Append developer’s **public** key to **`~/.ssh/authorized_keys`** for **`root`** and, if applicable, **`maple`** (as already stated in `docs/deployment.md`).
   - Example command pattern (adjust paths): `mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo 'ssh-ed25519 AAAA... comment' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys` — present as **illustrative** and remind to use the **actual** key line provided by the developer.
4. **Separation:** Clearly distinguish **DigitalOcean account/team permissions** from **Linux user accounts** on the VM (`root` vs `maple`) from **PostgreSQL credentials** (managed DB users/passwords in DO panel).

If any step **cannot** be verified from `docs/deployment.md` + `docs/design-doc.md` + DigitalOcean public documentation, **do not** present it as a confirmed project fact; mark it **TBD** or **verify with Jayden**.

### 7. Style and quality bar

- Assume readers are **new** to DigitalOcean **Droplets**, **managed databases**, **systemd**, and **SSH keys**.
- Use **numbered steps** for procedures; use **tables** for comparisons; use **admonitions** (`> **Requires Jayden:**`) consistently.
- **Typos:** Fix in the **deliverable** `docs/deployment.md` (e.g. “repetitive”, “Context”) **without** changing meaning of policies.
- Keep the document **scannable**: short intro paragraphs, then depth.

### 8. Verification before you finish

1. Grep your mental model: every **IP, path, service name, username, branch name** in the new doc appears in **old `docs/deployment.md`** or is explicitly labeled as **design-doc target / TBD**.
2. No **new** infrastructure components (e.g. Redis, Kubernetes) unless in **`docs/design-doc.md`** or existing deployment text.
3. **Jayden** subsection includes **both** “when others contact Jayden” and “what Jayden does in DO + SSH + DB allowlisting,” with **no fabricated company-specific DO account structure**.

### 9. Deliverable

- **Primary:** Updated **`docs/deployment.md`** reflecting the structure and new sections above.
- **If ambiguous:** List **specific questions for the user (Jayden)** at the end of the doc in **“Open questions”** rather than guessing.

---

*End of expanded agent prompt.*
