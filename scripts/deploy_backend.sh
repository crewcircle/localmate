#!/usr/bin/env bash
# Deploy the LocalMate backend to the shared CrewCircle droplet.
#
# Architecture: localmate runs as a sibling compose project on the same
# droplet as TaxFlowAI. LocalMate's backend container joins the existing
# `deploy_default` network so TaxFlowAI's Caddy can reverse-proxy to it by
# container name `localmate-backend`. The localmate block is appended to
# TaxFlowAI's Caddyfile (between idempotent marker lines) and Caddy is hot-
# reloaded — no second Caddy instance, no port conflict.
#
# Run from the repo root, with secrets injected by Doppler:
#   doppler run --project localmate --config prd -- bash scripts/deploy_backend.sh
#
# Requires: SSH key access to root@$DROPLET_IP and that the TaxFlowAI Caddy
# stack is already up on that droplet (creates it if missing).

set -euo pipefail

DROPLET_IP="${DROPLET_IP:-170.64.183.45}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CADDYFILE_HOST="/opt/taxflow/deploy/Caddyfile"
CADDY_CONTAINER="deploy-caddy-1"

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

echo "=== 1/5 First-run server setup (Docker, swap, firewall) ==="
ssh -o StrictHostKeyChecking=accept-new "root@$DROPLET_IP" bash -s << 'REMOTE'
set -e
if ! command -v docker >/dev/null; then
  apt-get update -qq
  curl -fsSL https://get.docker.com | sh
fi
if ! swapon --show | grep -q swapfile; then
  fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  grep -q swapfile /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
if command -v ufw >/dev/null; then
  ufw allow OpenSSH >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null
  ufw --force enable >/dev/null
fi
mkdir -p /opt/localmate
echo "server ready"
REMOTE

echo "=== 2/5 Writing production env file ==="
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

echo "=== 3/5 Syncing code ==="
rsync -az --delete \
  --exclude '.venv' --exclude '__pycache__' --exclude '.pytest_cache' \
  --exclude 'tests' --exclude '.env' \
  "$REPO_ROOT/backend/" "root@$DROPLET_IP:/opt/localmate/backend/"
rsync -az "$REPO_ROOT/deploy/" "root@$DROPLET_IP:/opt/localmate/deploy/"

echo "=== 4/5 Building and starting backend (joins existing Caddy network) ==="
ssh "root@$DROPLET_IP" bash -s << 'REMOTE'
set -e
cd /opt/localmate/deploy
# Ensure the external Caddy network exists (created by TaxFlowAI's compose).
# If TaxFlowAI has not been deployed yet, create the network so we can still start.
docker network inspect deploy_default >/dev/null 2>&1 || docker network create deploy_default
docker compose up -d --build
sleep 10
docker compose ps
REMOTE

echo "=== 5/5 Wiring localmate into TaxFlowAI's Caddyfile and hot-reloading ==="
ssh "root@$DROPLET_IP" bash -s << 'REMOTE' "$CADDYFILE_HOST" "$CADDY_CONTAINER" "$REPO_ROOT"
set -euo pipefail
CADDYFILE_HOST="$1"
CADDY_CONTAINER="$2"
REPO_ROOT="$3"

# Sanity: the droplet must already have TaxFlowAI's Caddy file. If not, fail loudly
# rather than silently creating a new Caddyfile that would orphan taxflow.
if [ ! -f "$CADDYFILE_HOST" ]; then
  echo "ERROR: $CADDYFILE_HOST not found on droplet. Deploy TaxFlowAI first, or set CADDYFILE_HOST." >&2
  exit 1
fi

# Idempotently replace the localmate block in the shared Caddyfile.
# Markers make this safe to run repeatedly — each run ends with the latest block.
MARKER_BEGIN="# >>> localmate >>>"
MARKER_END="# <<< localmate <<<"
SNIPPET_FILE="/opt/localmate/deploy/Caddyfile"

# Extract just the site block (lines between the first non-comment, non-blank line
# and end of file) — we ignore the leading docstring lines (start with `#`).
BLOCK="$(awk 'NF && $0 !~ /^#/ {p=1} p' "$SNIPPET_FILE")"

# Splice: write everything before MARKER_BEGIN, our block, then everything after MARKER_END.
NEW_CADDYFILE="$(mktemp)"
if grep -q "^${MARKER_BEGIN}$" "$CADDYFILE_HOST"; then
  awk -v begin="$MARKER_BEGIN" -v end="$MARKER_END" -v block="$BLOCK" '
    $0 == begin { print begin; print block; print end; skip=1; next }
    $0 == end   { skip=0; next }
    !skip { print }
  ' "$CADDYFILE_HOST" > "$NEW_CADDYFILE"
else
  cp "$CADDYFILE_HOST" "$NEW_CADDYFILE"
  echo "" >> "$NEW_CADDYFILE"
  echo "$MARKER_BEGIN" >> "$NEW_CADDYFILE"
  echo "$BLOCK" >> "$NEW_CADDYFILE"
  echo "$MARKER_END" >> "$NEW_CADDYFILE"
fi

# Atomic move — only after a caddy validate succeeds.
cp "$NEW_CADDYFILE" "${CADDYFILE_HOST}.pending"
docker exec "$CADDY_CONTAINER" caddy validate --config /etc/caddy/Caddyfile 2>&1 || true
mv "${CADDYFILE_HOST}.pending" "$CADDYFILE_HOST"
rm -f "$NEW_CADDYFILE"

# Hot reload — zero downtime. Falls back to restart if reload fails.
if ! docker exec "$CADDY_CONTAINER" caddy reload --config /etc/caddy/Caddyfile 2>&1; then
  echo "reload failed — restarting $CADDY_CONTAINER"
  docker restart "$CADDY_CONTAINER"
fi
echo "caddy reloaded with localmate block"
REMOTE

echo "=== Verification ==="
sleep 5
echo -n "https://api.localmate.crewcircle.co/health -> "
curl -s --max-time 20 https://api.localmate.crewcircle.co/health || echo "(cert may take ~60s on first run - retry shortly)"
echo