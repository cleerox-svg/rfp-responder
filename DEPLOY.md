# NaughtRFP — AWS Deployment Guide

> Deploy NaughtRFP to a single AWS EC2 instance at `https://rfp.naughtid.com`.
> **Estimated setup time: 20–30 minutes** (including DNS + HTTPS).

---

## Architecture

```
Internet ──► EC2 Security Group (ports 80, 443)
                  │
               Nginx :80  → redirects to HTTPS
               Nginx :443 (nginx:alpine container)
                  │   ssl_certificate from /etc/letsencrypt (host mount)
                  │   proxy_buffering off for SSE streams
               Gunicorn :5000  (python:3.11-slim container)
                  │   gthread workers, --timeout 300
             Flask / NaughtRFP
                  │
            Docker volume: naughtrfp_data mounted at /data/
            ├── naughtrfp.db      (SQLite — persists across restarts)
            ├── uploads/           (uploaded RFP files)
            └── exports/           (generated response files)
```

---

## Step 1 — Launch EC2 Instance

1. Go to **EC2 → Launch Instance** in the AWS console
2. **AMI:** Ubuntu Server 22.04 LTS *(recommended)* or Amazon Linux 2023
3. **Instance type:** `t3.medium` (2 vCPU, 4 GB RAM)
   - Minimum for running Claude models in parallel (6 Answer Agent workers)
   - `t3.small` works but may be slow on large RFPs
4. **Storage:** 20 GB gp3 (default)
5. **Key pair:** Create or select one — download the `.pem` file
6. **Security Group — add these inbound rules:**

   | Type  | Protocol | Port | Source        |
   |-------|----------|------|---------------|
   | SSH   | TCP      | 22   | My IP         |
   | HTTP  | TCP      | 80   | 0.0.0.0/0     |
   | HTTPS | TCP      | 443  | 0.0.0.0/0     |

7. Launch and note the **Public IPv4 address**

---

## Step 2 — Run the Setup Script

SSH into your instance and run the one-shot setup script:

```bash
# From your local machine
chmod 400 your-key.pem
ssh -i your-key.pem ubuntu@YOUR_EC2_IP       # Ubuntu
# or:
ssh -i your-key.pem ec2-user@YOUR_EC2_IP     # Amazon Linux

# On the EC2 — clone and run setup:
git clone https://github.com/cleerox-svg/rfp-responder.git
cd rfp-responder
bash deploy/aws-setup.sh
```

The script installs Docker, Docker Compose, creates `.env`, builds the containers, and starts everything. It will pause to let you edit `.env`. At the end it will prompt whether to configure HTTPS — **say N for now and do Step 2b first.**

---

## Step 2b — Configure Route 53 DNS

> Complete this before running Certbot. The DNS record must be live before Certbot can verify domain ownership.

### Allocate an Elastic IP (so your domain stays valid across reboots)

1. Go to **EC2 → Elastic IPs → Allocate Elastic IP address**
2. Select the new allocation, click **Actions → Associate Elastic IP address**
3. Select your EC2 instance → click **Associate**
4. Note the Elastic IP address (e.g. `3.92.x.x`)

> **Why Elastic IP?** A regular EC2 public IP changes every time the instance stops and starts. An Elastic IP is static — your `rfp.naughtid.com` A record stays valid across reboots and stops.

### Create the DNS record

1. Go to **Route 53 → Hosted zones → naughtid.com**
2. Click **Create record**
3. Set:
   - **Record name:** `rfp`  *(this creates `rfp.naughtid.com`)*
   - **Record type:** `A`
   - **Value:** your Elastic IP (e.g. `3.92.x.x`)
   - **TTL:** `300`
4. Click **Create records**

DNS propagates in 1–5 minutes. Verify with:

```bash
nslookup rfp.naughtid.com
# Should return your Elastic IP
```

### Get the HTTPS certificate

SSH back into your EC2 and re-run the setup script, or run the Certbot step manually:

```bash
cd rfp-responder
bash deploy/aws-setup.sh
# Answer 'y' when prompted: "Set up HTTPS for rfp.naughtid.com?"
```

The script will:
1. Install Certbot
2. Temporarily stop the Nginx container (frees port 80)
3. Issue a free Let's Encrypt cert for `rfp.naughtid.com` using standalone mode
4. Restart the full stack — Nginx now serves HTTPS on port 443
5. Install a cron job for automatic cert renewal (runs daily at 03:00)

After this completes, open **https://rfp.naughtid.com** in your browser.

---

## Step 3 — Configure Your API Key

The script creates a `.env` file and pauses for you to fill it in:

```bash
nano .env
```

Set these two values:

```env
LITELLM_API_KEY=sk-your-key-here
LITELLM_BASE_URL=https://api.anthropic.com
```

> **⚠ LiteLLM vs Direct Anthropic API**
>
> `llm.atko.ai` is Okta's **internal** LiteLLM proxy — only reachable from within Okta's corporate network or VPN. From a public AWS EC2 you have two options:
>
> | Scenario | `LITELLM_BASE_URL` | API Key |
> |---|---|---|
> | EC2 outside Okta VPN | `https://api.anthropic.com` | Personal Anthropic key from console.anthropic.com |
> | EC2 inside Okta VPN / VPN tunnel | `https://llm.atko.ai` | `sk-` LiteLLM key from llm.atko.ai/ui/api-keys |
>
> You can also change the URL and key any time in the app's **Settings** page without restarting.

After editing `.env`, press Enter to let the script build and start the containers.

---

## Step 4 — Open the App

Navigate to `https://rfp.naughtid.com` in your browser (takes ~20-30s on first boot while Gunicorn initialises).

**First-time setup:**
1. Go to **Settings** → verify API key is shown → click **⚡ Test Connection**
2. Go to **Knowledge Base** → click **⊕ Seed Okta Knowledge** (loads 25 baseline entries)
3. Optional: run `py seed_sig.py` inside the container to load 615 SIG Core entries (see below)
4. Go to **Dashboard** → upload `sample_rfp.csv` to test the full 9-agent pipeline

---

## Seeding the Full Knowledge Base (optional)

The SIG Core 2024 spreadsheet (`Okta_SIG_Core.xlsm`) is not in the repo. To seed the full 657-entry KB:

```bash
# Copy the xlsm file into the container
docker compose cp /path/to/Okta_SIG_Core.xlsm app:/app/

# Run the seed script inside the container
docker compose exec app python seed_sig.py
docker compose exec app python seed_confluence.py
```

---

## Day-to-Day Operations

```bash
# View live logs
docker compose logs -f app

# Check container status
docker compose ps

# Restart app after changing .env
docker compose restart app

# Pull latest code and redeploy
git pull origin master
docker compose build --no-cache
docker compose up -d

# Stop everything (data is preserved in the volume)
docker compose down

# Stop instance when not demoing (saves ~$1/hour)
# Use AWS console: EC2 → Instances → Stop
# Note: Elastic IP remains associated — no DNS update needed on restart
```

---

## CI/CD — Auto Deploy from GitHub

Every push to `master` automatically deploys to `rfp.naughtid.com` via GitHub Actions.

### One-time setup — add GitHub Secrets

Go to **GitHub → cleerox-svg/rfp-responder → Settings → Secrets and variables → Actions → New repository secret** and add these three secrets:

| Secret name | Value |
|---|---|
| `EC2_HOST` | `rfp.naughtid.com` (or the Elastic IP while DNS is propagating) |
| `EC2_USER` | `ubuntu` (Ubuntu) or `ec2-user` (Amazon Linux) |
| `EC2_SSH_KEY` | Contents of your `.pem` key file (open in a text editor, paste the whole thing including `-----BEGIN RSA PRIVATE KEY-----`) |

### How to get your private key content

```bash
cat your-key.pem
# Copy everything from -----BEGIN ... to -----END ...
```

### Deploy flow

```
git push origin master
        │
        ▼
GitHub Actions runner (ubuntu-latest)
        │
        └── SSH into rfp.naughtid.com
              │
              ├── git pull origin master
              ├── docker compose build --no-cache app
              ├── docker compose up -d --no-deps app
              └── health check: GET /api/kb/stats × 6 attempts
```

Total deploy time: ~2–3 minutes (most of that is Docker image rebuild).

### Deployment status

View live deploy runs at:
`https://github.com/cleerox-svg/rfp-responder/actions`

### Manual deploy (without pushing)

If you need to redeploy without a code change (e.g. after editing `.env`):

```bash
ssh -i your-key.pem ubuntu@rfp.naughtid.com
cd rfp-responder
docker compose restart app
```

---

## Backup the Database

```bash
# Copy SQLite DB from the volume to your local machine
docker compose exec app cp /data/naughtrfp.db /tmp/backup.db
docker compose cp app:/tmp/backup.db ./naughtrfp-backup-$(date +%Y%m%d).db
```

---

## TLS Certificate Renewal

Certbot auto-renewal is handled by a root cron job installed during setup (runs daily at 03:00). It stops Nginx, renews if within 30 days of expiry, then restarts Nginx. To check the renewal schedule:

```bash
sudo crontab -l
```

To manually force a renewal test:

```bash
sudo certbot renew --dry-run
```

---

## Cost Estimate (demo use)

| Resource | Type | Est. monthly |
|---|---|---|
| EC2 t3.medium | On-Demand | ~$30 |
| EBS 20 GB gp3 | Storage | ~$1.60 |
| Elastic IP (associated) | Free while attached | $0 |
| Elastic IP (unassociated) | ~$0.005/hr if released | ~$3.60 |
| Data transfer | First 100 GB free | $0 |
| **Total (running 24/7)** | | **~$32/month** |

**Tip:** Stop the instance when not demoing. EBS data persists. Elastic IP stays associated (no charge). Cost drops to ~$1.60/month (storage only).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| App doesn't load at port 80 | Security group missing HTTP rule | Add inbound rule port 80 → 0.0.0.0/0 |
| HTTPS not working | Security group missing HTTPS rule | Add inbound rule port 443 → 0.0.0.0/0 |
| Certbot fails "connection refused" | DNS not propagated yet | Wait 5 min, run `nslookup rfp.naughtid.com` to verify |
| Certbot fails "port 80 in use" | Nginx still running | `docker compose stop nginx` then re-run certbot |
| Nginx won't start after certs issued | Cert path mismatch | Verify `/etc/letsencrypt/live/rfp.naughtid.com/` exists |
| "API key not configured" | `.env` LITELLM_API_KEY not set | Edit `.env` → `docker compose restart app` |
| Agent progress freezes mid-stream | Nginx buffering SSE | Verify `nginx.conf` has `proxy_buffering off` on streaming locations |
| `llm.atko.ai` connection refused | Outside Okta VPN | Set `LITELLM_BASE_URL=https://api.anthropic.com` in `.env` or Settings |
| Uploads return 413 | File > 100 MB | Reduce file size or raise `client_max_body_size` in `nginx.conf` |
| Container exits immediately | App crash on startup | `docker compose logs app` to see the error |
| IP changed after instance restart | No Elastic IP | Allocate and associate an Elastic IP (see Step 2b) |
