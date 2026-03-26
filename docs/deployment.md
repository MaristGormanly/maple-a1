# Welcome to MAPLE A1 — Deployment & Onboarding

Welcome to the team! This guide walks you through everything you need to get access to our infrastructure, connect to the production environment, and deploy code. Work through each section in order and you should be up and running quickly.

## Infrastructure Overview

Here is what our production stack looks like — you do not need to set any of this up yourself, but it helps to know the lay of the land:

| Component | Details |
|-----------|---------|
| **Server** | Ubuntu 22.04 Droplet (`161.35.125.120`) on DigitalOcean |
| **Database** | DigitalOcean Managed PostgreSQL 16 |
| **Reverse Proxy** | Nginx (IP-only for now) |
| **Process Manager** | systemd (`maple-a1.service`) |

---

## What You Need to Do (Step by Step)

### 1. Get DigitalOcean Dashboard Access

You will need access to the DigitalOcean dashboard so you can see the Droplet, the managed database, firewalls, and other project resources.

**Your steps:**

1. Create a [DigitalOcean](https://www.digitalocean.com/) account if you do not have one yet. Use whatever email the team agrees on.
2. Send your account email to **Jayden** and ask to be added to the MAPLE A1 team.

> **Requires Jayden (admin):** Jayden will invite you to the DigitalOcean team/project and assign you the appropriate role. Once you accept the invite, you will be able to view all project resources in the dashboard.

### 2. Set Up SSH Access to the Droplet

You will use SSH to connect to the production server for deployments, log viewing, and debugging. Every developer gets their own keypair — we never share private keys.

**Your steps:**

1. Generate a keypair on your machine:

   ```bash
   ssh-keygen -t ed25519 -C "your.name@school.edu" -f ~/.ssh/maple-a1-team
   ```

2. Send **only your public key** (the `.pub` file) to **Jayden**:

   ```bash
   cat ~/.ssh/maple-a1-team.pub
   ```

   Never send your private key. Never paste keys in GitHub issues or public channels.

3. Once Jayden confirms your key is installed, test the connection:

   ```bash
   ssh -i ~/.ssh/maple-a1-team root@161.35.125.120
   ```

   Use whatever path and filename you chose in step 1. The examples elsewhere in this doc may reference Jayden's key path (`~/digital_ocean_keygen.txt`) — yours will be different.

> **Requires Jayden (admin):** Jayden will SSH into the Droplet and append your public key to the server's `authorized_keys` file. If deploys run under the **`maple`** user, he will add it there too. He will let you know when it is ready.

### 3. Get Your Environment Variables (`.env`)

The app is configured through a `.env` file. You need one for local development and you should understand how the production one works.

#### Local Development

1. Copy the example file to create your own:

   ```bash
   cp .env.example .env
   ```

2. Fill in your local values. The `.env` file is git-ignored and must **never** be committed.

Here is what each group of variables controls:

| Variable Group | What It Configures |
|----------------|--------------------|
| `DATABASE_*` / `DATABASE_URL` | Connection to PostgreSQL (use your local DB for development) |
| `APP_ENV`, `APP_HOST`, `APP_PORT` | Application environment and server binding |
| `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT authentication signing and token lifetime |
| `GITHUB_PAT` | GitHub Personal Access Token for the ingestion pipeline |
| `GEMINI_API_KEY`, `OPENAI_API_KEY` | LLM provider keys (placeholders until Milestone 3) |
| `CORS_ORIGINS` | Allowed CORS origins for the frontend |

> **Requires Jayden (admin):** For any credentials you cannot generate yourself (database passwords, shared API keys, the GitHub PAT), contact Jayden. He will share them through a secure channel — never through GitHub or Slack messages.

#### Production

The production `.env` lives on the Droplet at `/opt/maple-a1/.env`. The `maple-a1.service` systemd unit reads it when starting Uvicorn. You should not need to edit this unless you are updating a secret or adding a new environment variable.

### 4. Database Access

Your local development setup will typically use a local PostgreSQL instance. If you ever need to connect directly to the **production** database from your laptop (for debugging, migrations, etc.), you have two options:

- **SSH tunnel through the Droplet** (preferred) — route your local `psql` connection through the server.
- **Temporary trusted IP** — your IP gets added to the database's allowlist temporarily.

> **Requires Jayden (admin):** Either approach requires Jayden to configure access. Reach out to him and specify what you need and for how long.

---

## Deploying Code

After your PR is merged to `main`, here is how you deploy to production:

```bash
# 1. SSH into the Droplet (use YOUR key path)
ssh -i ~/.ssh/maple-a1-team root@161.35.125.120

# 2. Switch to the maple user
su - maple

# 3. Pull latest code
cd /opt/maple-a1
git pull origin main

# 4. Install any new dependencies
source venv/bin/activate
pip install -r server/requirements.txt

# 5. Run database migrations (if any)
alembic upgrade head

# 6. Exit back to root and restart the service
exit
systemctl restart maple-a1
```

## Viewing Logs

To tail the live application logs on the Droplet:

```bash
journalctl -u maple-a1 -f
```

## If a Secret Is Compromised

If you suspect any secret (GitHub PAT, database password, API key, etc.) has been leaked:

1. **Immediately** revoke the compromised credential at its source.
2. Generate a replacement.
3. Update `/opt/maple-a1/.env` on the Droplet.
4. Restart the service: `systemctl restart maple-a1`.

> **Contact Jayden immediately** if you are unsure how to revoke a credential or need help rotating production secrets.

---

## Quick Reference — When to Contact Jayden

| You need… | What Jayden does |
|-----------|-----------------|
| DigitalOcean dashboard access | Sends you a team invite and assigns your role |
| SSH access to the Droplet | Adds your public key to `authorized_keys` |
| Dev `.env` credentials you cannot generate yourself | Shares values through a secure channel |
| Direct database access from your laptop | Adds a trusted IP or sets up tunnel documentation |
| Help with a compromised secret | Assists with revocation and rotation |

If anything in this guide is unclear or out of date, open an issue or message Jayden directly.
