This file is to help me understand what I am building for maple-a1.

## Jayden — Docker Container Runtime (6 tasks)

**Summary:** By the end of these tasks, the Docker runtime layer will be fully operational: the Droplet has Docker accessible, the SDK can spin up hardened ephemeral containers from language-specific images, TTL enforcement kills runaway containers, and log output is normalized before it reaches any business logic. These tasks are independently verifiable with a standalone integration test against the Docker daemon — no pipeline business logic is required.

**Tasks:**

- Verify Docker is installed and the `maple-a1.service` process user has access to `/var/run/docker.sock` on the DigitalOcean Droplet; document the socket permission setup in `docs/deployment.md`. — *`docs/design-doc.md` §6 "The FastAPI backend will have direct access to the Docker Daemon via the native UNIX socket `/var/run/docker.sock`"*; also §8 "Implement Docker SDK integration: spin up ephemeral sibling containers via `/var/run/docker.sock`"*
- Integrate Docker SDK: spin up ephemeral sibling containers via the host UNIX socket `/var/run/docker.sock` (no Docker-in-Docker). — *`docs/design-doc.md` §8 "Implement Docker SDK integration: spin up ephemeral sibling containers via `/var/run/docker.sock`"*
- Define language-specific base images for the sandbox: Python/Pytest, Java/JUnit, JavaScript/Jest, TypeScript/Jest. — *`docs/design-doc.md` §8 "Define language-specific base images: Python/Pytest, Java/JUnit, JavaScript/Jest, TypeScript/Jest"*
  > *Depends on: Docker socket task above (images are pulled/built against the live daemon).*
- Implement container security hardening: run with `--no-new-privileges`, drop all Linux capabilities, mount root filesystem read-only, and apply CPU and memory limits via Docker SDK. — *`docs/design-doc.md` §8 "Implement container security hardening: `--no-new-privileges`, dropped Linux capabilities, read-only FS, CPU/memory limits, 30s TTL"*; also `docs/design-doc.md` §7 "Risk 2: Docker Sandbox Misconfiguration" (mitigation)*
  > *Depends on: Docker SDK integration task above (hardening flags are applied at container creation).*
- Implement a 30-second TTL: forcibly kill containers that exceed the time limit; map exit code `124` (timeout) and `137` (OOM kill) to a `resource_constraint_metadata` flag injected into the evaluation reasoning object rather than failing silently. — *`docs/design-doc.md` §8 "30s TTL" and §3 §IV "Resource Constraints: exit codes 137 (OOM) or 124 (Timeout) … inject a Resource Constraint Metadata flag"*
  > *Depends on: Docker SDK integration task above. The `resource_constraint_metadata` flag is consumed by Dom's test result capture task.*
- Implement log normalization using a circular buffer: retain the first 2 KB and last 5 KB of the execution trace; discard the middle to prevent context bloat. — *`docs/design-doc.md` §8 "Implement log normalization: circular buffer keeping first 2KB + last 5KB of execution trace"*; also `docs/design-doc.md` §3 §IV "Log Normalization: Circular Buffer truncates logs, retaining only the first 2KB and last 5KB"*
  > *Depends on: Docker SDK integration task above. Normalized log output is the raw input consumed by Dom's test result capture task.*

Explanation:

### Where your work sits in Milestone 2

Milestone 2 is “run student tests in Docker and show a score.” You own the **execution substrate**: making sure the FastAPI process on the server can talk to Docker safely, start the right kind of container for each language, enforce time and memory limits, and hand **predictable, bounded output** (logs + exit semantics) to Dom’s pipeline. You are **not** responsible for mounting student repos, parsing pytest/Jest output into JSON, or the HTTP API shape—that is Dom’s layer—but you **produce the signals** (exit codes, normalized logs) his code will consume.

**“Independently verifiable with a standalone integration test”** means: you can write a test that only needs a machine with Docker running (your laptop or the Droplet). It proves containers start, hardening applies, TTL fires, and logs truncate—without needing the full `POST /evaluate` flow.

---

### Production pieces you will touch (first-time friendly)

- **DigitalOcean Droplet** — A Linux VM in the cloud where MAPLE runs in production. “Docker is installed on the Droplet” means the Docker **daemon** (`dockerd`) runs on that VM, same as on your Mac, but remotely.
- `**maple-a1.service`** — A **systemd** unit file that starts the FastAPI app (via Uvicorn) on boot and restarts it if it crashes. The **process user** is whoever systemd runs the service as (often something like `www-data` or a dedicated user). That user must be allowed to use Docker; see the socket task below.
- `**/var/run/docker.sock`** — A **Unix domain socket** the Docker daemon listens on. When the Docker CLI or the **Docker SDK** “talks to Docker,” they send API requests over this socket. File permissions on the socket decide **which OS users** may control Docker. Giving your app access is normal for “Docker on the same host as the app”; it is powerful (root-equivalent on many setups), which is why the design pairs it with **hardened, short-lived containers** and strict limits—not arbitrary student code on the host.

---

### Task 1 — Socket access and documentation

**Goal:** Confirm Docker works on the Droplet and the same user that runs `maple-a1.service` can create containers.

**Typical checks (concepts, not a single mandated command):** `docker version` or `docker info` as an admin; then verify the service user can run a trivial `docker run --rm hello-world` (or equivalent) **as that user**. If permission is denied on the socket, common fixes include adding the user to the `docker` group and re-login, or documented socket ACLs—**your deliverable includes writing the chosen approach in `docs/deployment.md`** so the next deploy is repeatable.

---

### Task 2 — Docker SDK, host socket, “sibling” containers

**Goal:** From Python (FastAPI’s process), create and run containers using the **official Docker SDK for Python** (`docker` PyPI package), configured to use `**unix:///var/run/docker.sock`** (the default on Linux when the library talks to the local daemon).

**Sibling containers vs Docker-in-Docker (DinD):** **Sibling** means your app process runs on the **host** (or in a VM), and each student job is a **new container** next to it, sharing the **same** Docker daemon. **DinD** would mean running Docker *inside* a container—a heavier pattern you are explicitly **not** using. Siblings are simpler and match “one Droplet, one daemon, many ephemeral runners.”

---

### Task 3 — Language-specific base images

**Goal:** For each supported stack, define a **base image** (Dockerfile and/or published image tags) that already contains the test runner: **Python + pytest**, **Java + JUnit** (tooling to run JUnit tests), **Node + Jest** for plain JS and TS. Dom will later mount the cleaned student tree and instructor tests; your images supply the **runtime and test command environment** so those mounts can execute predictably.

**Method:** Build or pull images on the daemon, document tags, and keep them minimal and version-pinned where possible so grading stays reproducible.

---

### Task 4 — Container security hardening (flags you are implementing)

These are defense-in-depth so that if something is misconfigured, student code has less room to harm the host or other tenants:

- `**--no-new-privileges`** — Prevents processes in the container from gaining *more* privileges via setuid/setgid-style escalation paths.
- **Drop Linux capabilities** — Linux “capabilities” slice root into finer permissions; dropping them removes many dangerous powers (e.g. raw network tricks, mount operations) unless explicitly added back.
- **Read-only root filesystem** — The container’s main filesystem is not writable; writes go to explicit writable mounts (e.g. tmpfs or a volume Dom adds later). That limits persistence and many abuse patterns.
- **CPU and memory limits** — Set via Docker’s resource API (backed by cgroups). This caps burst CPU and RAM so one submission cannot starve the whole Droplet.

You apply these when **creating** the container spec in the SDK, not as afterthoughts.

---

### Task 5 — 30-second TTL and exit codes `124` / `137`

**Goal:** Guarantee **bounded wall-clock time**: if tests hang, you **stop** the container (SIGKILL or equivalent after timeout semantics).

- **Exit code 137** — Often interpreted as **128 + 9 (SIGKILL)**. In practice, when a process is killed due to **out-of-memory (OOM)** or aggressive termination, operators and orchestrators often surface **137**. Your design asks you to treat OOM-style kills distinctly from a clean test failure.
- **Exit code 124** — Conventionally used by tools like `**timeout*`* on Linux to mean “command exceeded time limit.” Your milestone text maps **124 → timeout** for **resource_constraint_metadata**.

`**resource_constraint_metadata`:** A structured flag (or small object) you attach to the evaluation/reasoning payload so Dom (and later the UI) can say “this run hit a **resource limit**” instead of treating it like a normal test failure or silently dropping the distinction.

---

### Task 6 — Log normalization (“circular buffer”)

**Goal:** Test output can be **huge** (verbose frameworks, stack traces). Sending megabytes into parsers and LLMs later is expensive and noisy. The design keeps **context at both ends**: **first 2 KB** (startup, command, early errors) and **last 5 KB** (final failures, summary lines), and **discards the middle**. That is not a classic ring buffer in memory for the whole stream; it is a **streaming truncation policy** that mimics “head + tail” preservation—sometimes described as a circular buffer in product docs when the implementation rotates or windows what is retained.

**Contract:** Dom’s parser consumes **your normalized string** as the canonical execution trace input.

---

### How to work day to day

1. **Prove locally first** — Same Docker SDK code against your laptop’s Docker Desktop validates most behavior before SSH.
2. **Prove on the Droplet** — Socket permissions and cgroup behavior are most faithful on the real VM image.
3. **Keep Dom’s interface stable** — Document what you return for: clean exit, non-zero test failure, timeout (124), OOM/heavy kill (137), and normalized logs.

You finish Milestone 2’s runtime layer when those six behaviors are true, tested, and documented—then Dom wires business logic on top.

# Implementation Iterative Summaries

