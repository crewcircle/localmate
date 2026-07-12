#!/usr/bin/env bash
# Remaining infra steps that require interactive permission:
#  1. Create the two Cloudflare DNS records (idempotent - reports exists if already created)
#  2. Attach the dashboard domain to the Vercel project
# Backend deployment is separate: scripts/deploy_backend.sh (Docker Compose + Caddy).
#
# Run:  doppler run --project localmate --config prd -- bash scripts/finish_infra.sh

set -euo pipefail

DROPLET_IP="${DROPLET_IP:-170.64.183.45}"

if [ -z "${CLOUDFLARE_API_TOKEN:-}" ]; then
  echo "CLOUDFLARE_API_TOKEN not set. Run via:"
  echo "  doppler run --project localmate --config prd -- bash scripts/finish_infra.sh"
  exit 1
fi

if [ -z "${CLOUDFLARE_ZONE_ID:-}" ]; then
  echo "CLOUDFLARE_ZONE_ID not set. Ensure localmate Doppler project inherits from crewcircle-master/prod."
  exit 1
fi

echo "=== 1/2 Creating DNS records ==="
# CNAME: localmate.crewcircle.co → Vercel (dashboard)
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$CLOUDFLARE_ZONE_ID/dns_records" \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" -H "Content-Type: application/json" \
  --data '{"type":"CNAME","name":"localmate","content":"cname.vercel-dns.com","proxied":false}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('PASS: localmate CNAME' if d['success'] else f'exists/FAIL: {d[\"errors\"]}')"

# A record: api.localmate.crewcircle.co → shared droplet (backend)
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$CLOUDFLARE_ZONE_ID/dns_records" \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" -H "Content-Type: application/json" \
  --data "{\"type\":\"A\",\"name\":\"api.localmate\",\"content\":\"$DROPLET_IP\",\"proxied\":false,\"comment\":\"LocalMate backend droplet (shared with TaxFlowAI)\"}" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('PASS: api.localmate A record' if d['success'] else f'exists/FAIL: {d[\"errors\"]}')"

echo "=== 2/2 Attaching dashboard domain to Vercel ==="
# CLI v50 syntax: single argument, applies to the project linked in this directory
(cd "$(dirname "$0")/../dashboard" && vercel domains add localmate.crewcircle.co || true)

echo "=== Verification ==="
echo -n "api.localmate DNS (.com.au): " && dig +short A api.localmate.crewcircle.com.au
echo -n "localmate DNS (.com.au):     " && dig +short CNAME localmate.crewcircle.com.au
echo -n "dashboard (.com.au):         " && curl -s -o /dev/null -w "%{http_code}\n" --max-time 15 https://localmate.crewcircle.com.au || true
echo
echo "Next: deploy the backend with:"
echo "  doppler run --project localmate --config prd -- bash scripts/deploy_backend.sh"