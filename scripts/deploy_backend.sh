#!/usr/bin/env bash
# Deploy the LocalMate backend to the shared CrewCircle droplet with Docker Compose + Caddy.
# Idempotent: first run installs Docker and swap; later runs just redeploy.
#
# Run from the repo root, with secrets injected by Doppler:
#   doppler run --project localmate --config prd -- bash scripts/deploy_backend.sh
#
# Requires: SSH key access to root@$DROPLET_IP (the key registered at droplet creation).
# Shares the same droplet as TaxFlowAI (170.64.183.45) — localmate runs on port 8000
# behind its own Caddy block, TaxFlowAI has its own Caddy block on the same Caddy instance.

set -euo pipefail

DROPLET_IP="${DROPLET_IP:-170.64.183.45}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

REQUIRED_VARS=(SUPABASE_URL SUPABASE_ANON_KEY SUPABASE_SERVICE_ROLE_KEY
               STRIPE_SECRET_KEY STRIPE_PRICE_ID STRIPE_WEBHOOK_SECRET STRIPE_GST_RATE_ID
               ANTHROPIC_API_KEY RESEND_API_KEY
               TWILIO_ACCOUNT_SID TWILIO_AUTH_TOKEN TWILIO_AU_NUMBER
               DATAFORSEO_LOGIN DATAFORSEO_PASSWORD
               GBP_CLIENT_ID GBP_CLIENT_SECRET
               BASE_DOMAIN PROJECT_ID)
for var in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!var:-}" ]; then
    echo "Missing $var - run via: doppler run --project localmate --config prd -- bash scripts/deploy_backend.sh"
    exit 1
  fi
done

echo "=== 1/4 First-run server setup (Docker, swap, firewall) ==="
ssh -o StrictHostKeyChecking=accept-new "root@$DROPLET_IP" bash -s << 'REMOTE'
set -e
if ! command -v docker >/dev/null; then
  apt-get update -qq
  curl -fsSL https://get.docker.com | sh
fi
# 1GB swap protects Docker builds on the 1GB droplet
if ! swapon --show | grep -q swapfile; then
  fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  grep -q swapfile /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
# Basic firewall: SSH + HTTP/HTTPS only
if command -v ufw >/dev/null; then
  ufw allow OpenSSH >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null
  ufw --force enable >/dev/null
fi
mkdir -p /opt/localmate
echo "server ready"
REMOTE

echo "=== 2/4 Writing production env file ==="
ssh "root@$DROPLET_IP" "cat > /opt/localmate/.env && chmod 600 /opt/localmate/.env" << ENVEOF
SUPABASE_URL=$SUPABASE_URL
SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY=$SUPABASE_SERVICE_ROLE_KEY
STRIPE_SECRET_KEY=$STRIPE_SECRET_KEY
STRIPE_PRICE_ID=$STRIPE_PRICE_ID
STRIPE_WEBHOOK_SECRET=$STRIPE_WEBHOOK_SECRET
STRIPE_GST_RATE_ID=$STRIPE_GST_RATE_ID
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY
RESEND_API_KEY=$RESEND_API_KEY
TWILIO_ACCOUNT_SID=$TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN=$TWILIO_AUTH_TOKEN
TWILIO_AU_NUMBER=$TWILIO_AU_NUMBER
DATAFORSEO_LOGIN=$DATAFORSEO_LOGIN
DATAFORSEO_PASSWORD=$DATAFORSEO_PASSWORD
GBP_CLIENT_ID=$GBP_CLIENT_ID
GBP_CLIENT_SECRET=$GBP_CLIENT_SECRET
BASE_DOMAIN=$BASE_DOMAIN
PROJECT_ID=$PROJECT_ID
ENVIRONMENT=production
ENVEOF

echo "=== 3/4 Syncing code ==="
rsync -az --delete \
  --exclude '.venv' --exclude '__pycache__' --exclude '.pytest_cache' \
  --exclude 'tests' --exclude '.env' \
  "$REPO_ROOT/backend/" "root@$DROPLET_IP:/opt/localmate/backend/"
rsync -az "$REPO_ROOT/deploy/" "root@$DROPLET_IP:/opt/localmate/deploy/"

echo "=== 4/4 Building and starting containers ==="
ssh "root@$DROPLET_IP" bash -s << 'REMOTE'
set -e
cd /opt/localmate/deploy
# compose context expects ../backend relative to deploy/; point it at the synced path
sed 's|context: ../backend|context: ../backend|' docker-compose.yml > docker-compose.deployed.yml
docker compose -f docker-compose.deployed.yml up -d --build
sleep 10
docker compose -f docker-compose.deployed.yml ps
REMOTE

echo "=== Verification ==="
sleep 5
echo -n "https://api.localmate.crewcircle.co/health -> "
curl -s --max-time 20 https://api.localmate.crewcircle.co/health || echo "(cert may take ~60s on first run - retry shortly)"
echo