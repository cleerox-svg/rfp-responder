#!/bin/bash
# NaughtRFP — AWS EC2 one-shot setup script
# Supports: Ubuntu 22.04 LTS, Amazon Linux 2, Amazon Linux 2023
#
# Usage (run after SSH into a fresh EC2 instance):
#   bash deploy/aws-setup.sh
#
# Or directly from GitHub (before cloning):
#   curl -fsSL https://raw.githubusercontent.com/cleerox-svg/rfp-responder/master/deploy/aws-setup.sh | bash

set -e

echo ""
echo "  NaughtRFP — AWS EC2 Setup"
echo "  ─────────────────────────────────────────"

# ── 1. Install Docker ──────────────────────────────────────────────────────
echo "  [1/6] Installing Docker..."

if command -v dnf &>/dev/null; then
    # Amazon Linux 2023
    sudo dnf update -y
    sudo dnf install -y docker
    sudo systemctl enable docker
    sudo systemctl start docker
    sudo usermod -aG docker ec2-user || sudo usermod -aG docker $USER

elif command -v amazon-linux-extras &>/dev/null; then
    # Amazon Linux 2
    sudo yum update -y
    sudo amazon-linux-extras install docker -y
    sudo service docker start
    sudo systemctl enable docker
    sudo usermod -aG docker ec2-user

elif command -v apt-get &>/dev/null; then
    # Ubuntu 22.04
    sudo apt-get update -y
    sudo apt-get install -y ca-certificates curl gnupg
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
        | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin
    sudo systemctl enable docker
    sudo systemctl start docker
    sudo usermod -aG docker $USER
else
    echo "  ERROR: Unsupported OS. Install Docker manually: https://docs.docker.com/engine/install/"
    exit 1
fi

# ── 2. Install Docker Compose plugin ──────────────────────────────────────
echo "  [2/6] Installing Docker Compose..."
DOCKER_CONFIG=${DOCKER_CONFIG:-$HOME/.docker}
mkdir -p "$DOCKER_CONFIG/cli-plugins"
curl -SL "https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-$(uname -s)-$(uname -m)" \
    -o "$DOCKER_CONFIG/cli-plugins/docker-compose"
chmod +x "$DOCKER_CONFIG/cli-plugins/docker-compose"

# ── 3. Clone / update repo ────────────────────────────────────────────────
echo "  [3/6] Getting NaughtRFP..."
if [ -d "rfp-responder/.git" ]; then
    echo "  Repo already exists — pulling latest..."
    cd rfp-responder
    git pull origin master
else
    git clone https://github.com/cleerox-svg/rfp-responder.git
    cd rfp-responder
fi

# ── 4. Configure .env ─────────────────────────────────────────────────────
echo "  [4/6] Configuring environment..."
if [ ! -f ".env" ]; then
    # Copy template (skip .env.example permission issues — write directly)
    cat > .env << 'ENVEOF'
# ── NaughtRFP Production Environment ─────────────────────────────────────
# Edit LITELLM_API_KEY and LITELLM_BASE_URL before starting.

# Your LiteLLM / Anthropic API key
LITELLM_API_KEY=sk-REPLACE-WITH-YOUR-KEY

# LiteLLM proxy URL:
#   Inside Okta VPN:   https://llm.atko.ai
#   Direct Anthropic:  https://api.anthropic.com
LITELLM_BASE_URL=https://api.anthropic.com

# Flask secret key — change this to a random string
FLASK_SECRET_KEY=REPLACE-WITH-RANDOM-SECRET

# Okta OIDC auth (optional — disabled by default)
# OKTA_DOMAIN=https://your-org.okta.com
# OKTA_CLIENT_ID=your-client-id
# OKTA_REDIRECT_URI=https://rfp.naughtid.com/auth/callback
ENVEOF

    # Generate a random secret key
    if command -v openssl &>/dev/null; then
        SECRET=$(openssl rand -hex 32)
        sed -i "s/REPLACE-WITH-RANDOM-SECRET/$SECRET/" .env
    fi

    echo ""
    echo "  ⚠  ACTION REQUIRED: Edit .env before starting:"
    echo "     nano .env"
    echo "     → Set LITELLM_API_KEY=sk-your-key-here"
    echo "     → Set LITELLM_BASE_URL (https://api.anthropic.com for direct Anthropic)"
    echo ""
    read -p "  Press Enter after editing .env to continue..." _
fi

# ── 5. Build and start ────────────────────────────────────────────────────
echo "  [5/6] Building and starting NaughtRFP..."
# Use sg to apply docker group without requiring logout
sg docker -c "docker compose build --no-cache && docker compose up -d" 2>/dev/null \
    || docker compose build --no-cache && docker compose up -d

echo ""
echo "  ✓ NaughtRFP is starting up (allow 20-30s for first boot)."
echo ""

# Get public IP from EC2 metadata
EC2_IP=$(curl -sf --connect-timeout 3 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null \
          || hostname -I | awk '{print $1}')

echo "  Open http://${EC2_IP} in your browser."
echo ""

# ── 6. Set up HTTPS with Let's Encrypt (Certbot) ──────────────────────────
echo ""
read -p "  Set up HTTPS for rfp.naughtid.com? (y/N) " DO_HTTPS
if [[ "$DO_HTTPS" =~ ^[Yy]$ ]]; then
    echo "  [6/6] Installing Certbot and issuing TLS certificate..."

    DOMAIN="rfp.naughtid.com"
    EMAIL="claude.leroux@okta.com"

    # Install certbot
    if command -v apt-get &>/dev/null; then
        sudo apt-get install -y certbot python3-certbot-nginx
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y certbot python3-certbot-nginx
    fi

    # Stop nginx container so certbot can use port 80
    sg docker -c "docker compose stop nginx" 2>/dev/null || docker compose stop nginx

    # Issue certificate (standalone mode on port 80)
    sudo certbot certonly --standalone \
        --non-interactive \
        --agree-tos \
        --email "$EMAIL" \
        -d "$DOMAIN"

    # Create webroot dir for future renewals
    sudo mkdir -p /var/www/certbot

    # Restart full stack — nginx.conf now has SSL blocks
    sg docker -c "docker compose up -d" 2>/dev/null || docker compose up -d

    # Set up auto-renewal cron
    # Pre-hook stops nginx; post-hook restarts it after renewal
    COMPOSE_PATH="/home/$USER/rfp-responder"
    (sudo crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet --pre-hook 'docker compose -f ${COMPOSE_PATH}/docker-compose.yml stop nginx' --post-hook 'docker compose -f ${COMPOSE_PATH}/docker-compose.yml start nginx'") | sudo crontab -

    echo ""
    echo "  ✓ HTTPS configured for https://${DOMAIN}"
    echo "  ✓ Auto-renewal cron job installed (runs daily at 03:00)"
    echo ""
    echo "  Open https://${DOMAIN} in your browser."
fi

echo ""
echo "  First-time setup in the app:"
echo "    1. Go to Settings → verify API key → Test Connection"
echo "    2. Go to Knowledge Base → Seed Okta Knowledge"
echo "    3. Upload sample_rfp.csv from the Dashboard"
echo ""
echo "  Useful commands:"
echo "    docker compose logs -f app      # live app logs"
echo "    docker compose ps               # container status"
echo "    docker compose restart app      # restart after config change"
echo "    docker compose pull && docker compose up -d  # update to latest"
echo ""
