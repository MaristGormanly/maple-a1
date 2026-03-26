# MAPLE A1 Deployment Guide

## Infrastructure Overview
- **Droplet:** Ubuntu 22.04 (161.35.125.120)
- **Database:** DigitalOcean Managed PostgreSQL 16
- **Reverse Proxy:** Nginx (IP-only for now)
- **Service Management:** systemd (`maple-a1.service`)

## Secrets Management
The application uses a `.env` file for configuration. 

### Local Development
Copy `.env.example` to `.env` and fill in your local values. The `.env` file is gitignored and should NEVER be committed.

### Production (Droplet)
The production `.env` file lives on the Droplet at `/opt/maple-a1/.env`. 
The `maple-a1.service` systemd unit reads this file when starting Uvicorn.

**To update production secrets:**
1. SSH into the Droplet: `ssh -i ~/.ssh/maple-a1 root@161.35.125.120`
2. Edit the file: `nano /opt/maple-a1/.env`
3. Restart the service: `systemctl restart maple-a1`

**If a secret is compromised:**
1. Immediately revoke the compromised key (e.g., GitHub PAT, database password).
2. Generate a new key.
3. Update the `.env` file on the Droplet.
4. Restart the service.

## Deployment Commands

After pushing code to the `main` branch, deploy it to the Droplet:

```bash
# 1. SSH into the Droplet
ssh -i ~/.ssh/maple-a1 root@161.35.125.120

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
To view the live application logs:
```bash
journalctl -u maple-a1 -f
```
