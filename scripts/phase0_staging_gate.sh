#!/usr/bin/env bash
# Phase 0 staged integration gate (C10) — MUST PASS before the Phase 0 PR merges.
#
# Unit tests use mocks; this gate runs the durability machinery against REAL
# Postgres + Redis and FAILS (non-zero exit) on any acceptance-check regression:
#   1. migrations 001→012 apply cleanly on a scratch DB
#   2. an arq worker drains an enqueued inbound job to `done` (worker restart/drain)
#   3. retry to MAX_TRIES then dead-letter (real arq retry semantics)
#   4. reconciliation re-enqueues stuck `pending` + recovers stale `processing`
#   5. deterministic _job_id dedupes a duplicate enqueue (exactly-once processing)
#
# Usage (from repo root):
#   bash scripts/phase0_staging_gate.sh
#
# Requires: docker, and `uv` (backend deps: arq, asyncpg). Spins up throwaway
# postgres:15-alpine + redis:7-alpine containers and tears them down on exit.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PG_CONT="localmate-gate-pg-$$"
REDIS_CONT="localmate-gate-redis-$$"
PG_PORT="${GATE_PG_PORT:-55432}"
REDIS_PORT="${GATE_REDIS_PORT:-56379}"

cleanup() {
  docker rm -f "$PG_CONT" "$REDIS_CONT" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "=== Phase 0 staging gate: provisioning real Postgres + Redis ==="
docker run -d --name "$PG_CONT" -e POSTGRES_PASSWORD=gate -e POSTGRES_DB=gate \
  -p "${PG_PORT}:5432" postgres:15-alpine >/dev/null
# Redis MUST be non-evicting + persistent per D9-A (no silent job loss).
docker run -d --name "$REDIS_CONT" -p "${REDIS_PORT}:6379" redis:7-alpine \
  redis-server --appendonly yes --maxmemory-policy noeviction >/dev/null

echo "--- waiting for Postgres ---"
for i in $(seq 1 30); do
  if docker exec "$PG_CONT" pg_isready -U postgres >/dev/null 2>&1; then break; fi
  sleep 1
done
echo "--- waiting for Redis ---"
for i in $(seq 1 30); do
  if docker exec "$REDIS_CONT" redis-cli ping >/dev/null 2>&1; then break; fi
  sleep 1
done

# Confirm Redis eviction policy is non-evicting (D9-A acceptance check).
POLICY="$(docker exec "$REDIS_CONT" redis-cli config get maxmemory-policy | tail -1)"
if [ "$POLICY" != "noeviction" ]; then
  echo "GATE FAIL: Redis maxmemory-policy is '$POLICY', expected 'noeviction' (D9-A)" >&2
  exit 1
fi
echo "GATE OK: Redis is non-evicting (noeviction) + AOF persistent"

export GATE_PG_DSN="postgresql://postgres:gate@127.0.0.1:${PG_PORT}/gate"
export GATE_REDIS_URL="redis://127.0.0.1:${REDIS_PORT}/0"

# The gate imports backend modules (config.Settings) which require env vars.
# Only the DB/Redis URLs above are actually exercised; the rest are stubs so
# pydantic Settings validates. REDIS_URL points at the throwaway gate Redis.
export SUPABASE_URL="https://stub.supabase.co" SUPABASE_ANON_KEY=stub SUPABASE_SERVICE_ROLE_KEY=stub
export STRIPE_SECRET_KEY=sk_stub STRIPE_PRICE_ID=price_stub STRIPE_WEBHOOK_SECRET=whsec_stub STRIPE_GST_RATE_ID=stub
export ANTHROPIC_API_KEY=sk-ant-stub RESEND_API_KEY=re_stub
export TWILIO_ACCOUNT_SID=AC000 TWILIO_AUTH_TOKEN=stub TWILIO_AU_NUMBER=+61400000000
export DATAFORSEO_LOGIN=stub DATAFORSEO_PASSWORD=stub
export GBP_CLIENT_ID=stub GBP_CLIENT_SECRET=stub BASE_DOMAIN=crewcircle.com.au
export PROJECT_ID=localmate ENVIRONMENT=test ENCRYPTION_KEY= SUPABASE_JWT_SECRET=
export REDIS_URL="$GATE_REDIS_URL" WORKER_ROLE=worker

echo "=== running gate checks ==="
cd "$REPO_ROOT/backend"
uv run python "$REPO_ROOT/scripts/phase0_staging_gate.py"

echo ""
echo "=== Phase 0 staging gate PASSED — safe to merge ==="
