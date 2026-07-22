# Deploy — localmate

Public repo: https://github.com/crewcircle/localmate
Target domain: **localmate.crewcircle.co** (dashboard) / **api.localmate.crewcircle.co** (backend)

---

## Architecture

| Layer | Host | Domain | Trigger |
|---|---|---|---|
| Next.js dashboard | **Vercel** | `localmate.crewcircle.co` | GitHub Actions `deploy.yml` on push to `main` |
| FastAPI (web) + arq worker + scheduler + Redis | **Docker Compose + Caddy** on shared DigitalOcean Sydney droplet (`170.64.183.45`) | `api.localmate.crewcircle.co` | `scripts/deploy_backend.sh` via Doppler |
| Postgres | **Supabase** | `*.supabase.co` | Pulumi provisioner |
| Secrets | **Doppler** `localmate/prd` (inherits `crewcircle-master/prod`) | — | Doppler CLI |
| DNS | **Cloudflare** | `crewcircle.co` zone | `scripts/finish_infra.sh` via Doppler |

The backend shares the same droplet as **TaxFlowAI** — Caddy routes `api.localmate.crewcircle.co` to the localmate backend container and `api.taxflow.crewcircle.com.au` to the taxflow backend container. No new droplet needed.

### Task queue containers (Phase 0)

The backend image runs in three roles, all from `deploy/docker-compose.yml`:

| Container | `WORKER_ROLE` | Command | Purpose |
|---|---|---|---|
| `localmate-backend` | `web` | `uvicorn main:app` | FastAPI API; enqueues jobs onto arq. Does **not** run APScheduler. |
| `localmate-worker` | `worker` | `arq worker.WorkerSettings` | Executes queued tasks (inbound webhook processing + durable outbound sends). Scale with `docker compose up -d --scale localmate-worker=N`. |
| `localmate-scheduler` | `scheduler` | `uvicorn main:app` | **Single-active** enqueue-only APScheduler (NOT HA). Each cron trigger pushes an arq job. Must remain a single instance so crons fire exactly once. |
| `localmate-redis` | — | `redis-server --appendonly yes --maxmemory 128mb --maxmemory-policy noeviction` | arq broker/result store. Persistent (AOF), non-evicting, memory-capped (128MB) on the shared 1GB droplet. Named volume `localmate-redis-data`. |

**Durability:** inbound webhooks (Stripe/GBP/menu) are persisted to `webhook_events` before enqueue; a reconciliation job (`reconcile_webhooks`, every 5 min) re-enqueues rows stuck `pending`. Exhausted retries (inbound and outbound) land in `dead_letter`. Redis is non-evicting so job state is never silently dropped.

### New Doppler vars (`localmate/prd`)

- `REDIS_URL` — `redis://localmate-redis:6379/0` (compose service DNS name). **Required.**
- `WORKER_ROLE` — set per-container in `docker-compose.yml` (`web`/`worker`/`scheduler`); no need to set in Doppler.
- `STRIPE_PORTAL_CONFIG_ID` — optional `bpc_...`; empty uses the Stripe dashboard default portal config. Used by the Phase 1 billing portal endpoint. Create the portal configuration in Stripe (enable subscription update to the localmate price, payment-method update, cancellation) — one-time dashboard/API step.
- `DASHBOARD_URL` — `https://localmate.crewcircle.co`; used as the Stripe portal `return_url` base.
- `SUPABASE_JWT_SECRET` — **Phase 1 (required for billing).** The Supabase project's JWT secret (Settings → API → JWT Settings in the Supabase dashboard). Used to verify dashboard bearer tokens and derive `client_id` from the authenticated user (tenant-auth binding, C8/D20). When unset, the legacy `require_auth` falls back to anonymous for old callers, but the strict `/billing/*` endpoints reject with 401 — so it must be set in prd.

### Migrations (Phase 0)

Apply `supabase/migrations/010_webhook_events.sql`, `011_dead_letter.sql`, `012_booking_credentials.sql` on top of `009`. Each new table has RLS enabled with a `service_role_all` policy (matches `001_clients.sql`). The sequence applies cleanly on top of `009` and is reversible (drop the two new tables / the added `clients` columns).

### Rollback (queue)

`docker compose stop localmate-worker localmate-scheduler localmate-redis` reverts to web-only. Inbound webhooks still persist to `webhook_events` as `pending` (nothing crashes); processing resumes when the worker + Redis come back and the reconciler re-enqueues the backlog.

### Phase 0 staged integration gate (C10 — MUST PASS before merge)

Unit tests mock Redis/Postgres, which cannot prove the durability behaviour. Before the Phase 0 PR merges to prod, run the executable gate — it spins up throwaway `postgres:15-alpine` + `redis:7-alpine` containers and **exits non-zero on any failed acceptance check** (nothing to eyeball):

```bash
bash scripts/phase0_staging_gate.sh
```

It asserts, and FAILS the build otherwise:

1. **Migrations** — Phase 0 migrations `010`/`011`/`012` apply cleanly on the reconstructed baseline; `webhook_events` + `dead_letter` exist with a `service_role_all` RLS policy; `012` added the five booking-credential columns on `clients`. (A pre-existing baseline-migration quirk already live in prod is a warning, not a Phase 0 failure.)
2. **Worker drain / restart** — an enqueued inbound job is drained by a real arq worker to `status='done'`.
3. **Retry + dead-letter** — a permanently-failing job is retried up to `MAX_TRIES` (real `arq.Retry` semantics) and then lands as exactly one `dead_letter` row.
4. **Reconciliation** — a stale `pending` row is re-enqueued and a stale `processing` lease is reset to `pending` and re-enqueued.
5. **Exactly-once / dedupe** — enqueuing the same event twice with the deterministic `_job_id` yields a single job (arq drops the duplicate).
6. **Redis durability (D9-A)** — the gate refuses to pass unless Redis is `noeviction` + AOF, so job state is never silently dropped.

Record the gate's `ALL PHASE 0 STAGING GATE CHECKS PASSED` output on the PR before merge.

### Phase 1 — billing visibility + tenant auth

**Migration:** apply `supabase/migrations/013_user_client_map.sql` on top of `012`. It creates `user_client_map (user_id text primary key, client_id uuid references clients(id))` with RLS + a `service_role_all` policy (matches `001_clients.sql`). One row per Supabase auth user → owned client; populate it at signup (or backfill existing users to their `clients` row by email). Until a user has a row, `/billing/*` returns 403.

**Tenant-auth binding (C8/D20):** `GET /billing/usage` and `POST /billing/portal` derive `client_id` from the authenticated identity via `user_client_map` (never from the request body/query), so a user can only reach their own tenant. `SUPABASE_JWT_SECRET` must be set in Doppler — with it empty these endpoints reject 401 (the legacy `require_auth` still falls back to anonymous for old non-client-scoped callers).

**One-time Stripe Billing Portal configuration:**
1. Stripe Dashboard → Settings → Billing → Customer portal → Add configuration (or via API: `stripe.billing_portal.Configuration.create(...)`).
2. Enable: subscription update (to the localmate price), payment-method update, subscription cancellation.
3. Copy the configuration id (`bpc_...`).
4. Set `STRIPE_PORTAL_CONFIG_ID` in Doppler (`localmate/prd`). Leave empty to use the Stripe dashboard default portal config.
5. `DASHBOARD_URL` controls where the user lands after leaving the portal (the `return_url`).

Portal-driven subscription changes (plan/card/cancel) flow back through the existing Stripe webhook handlers (`customer.subscription.updated` / `deleted`) which already update `clients.subscription_status` — no new reconciliation path.


---

## Phase A — You (one-time, ~10 min)

### 1. Populate `.env.local` at CrewCircle monorepo root

```bash
cd /path/to/grape-tin
cp packages/account-setup/.env.example .env.local
# Fill in all CC_* vars + cloud credentials
```

### 2. Provision infra (Pulumi one-shot)

```bash
./packages/infra/bin/newproject local-biz-au "Local Mate" "AU SMB automation suite" 19900
```

Creates: Supabase project, Doppler project `local-biz-au` (inherits `crewcircle-master/prod`), Stripe product+price ($199 AUD/mo + GST), Sentry project, Cloudflare DNS, `packages/infra/registry.json` entry.

### 3. Doppler — create `localmate` project inheriting master

```bash
doppler login
# Create project (or use the one Pulumi created):
doppler projects create localmate
# Create prd config that inherits crewcircle-master/prod:
doppler configs create prd --project localmate
# Add localmate-specific secrets (Supabase URL/keys from Pulumi output):
doppler secrets set SUPABASE_URL=... SUPABASE_ANON_KEY=... SUPABASE_SERVICE_ROLE_KEY=... --project localmate --config prd
```

---

## Phase B — CI/CD (already wired, green)

Three GitHub Actions workflows:
- **`ci.yml`** — pytest + dashboard build on every push/PR
- **`deploy.yml`** — Vercel dashboard auto-deploy on push to `main`
- **`docker.yml`** — backend Docker image → GHCR on push to `main`

GitHub secrets already set: `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`.

---

## Phase C — DNS records + Vercel domain (run this)

```bash
doppler run --project localmate --config prd -- bash scripts/finish_infra.sh
```

This creates two Cloudflare DNS records:
- `CNAME localmate → cname.vercel-dns.com` (dashboard)
- `A api.localmate → 170.64.183.45` (backend on shared droplet)

And attaches `localmate.crewcircle.co` to the Vercel project.

---

## Phase D — Backend deploy (run this)

```bash
doppler run --project localmate --config prd -- bash scripts/deploy_backend.sh
```

This script:
1. SSHs to `root@170.64.183.45`, installs Docker + swap + firewall (first run only)
2. Writes `/opt/localmate/.env` with all secrets (Doppler-injected)
3. rsyncs `backend/` + `deploy/` to `/opt/localmate/`
4. `docker compose up -d --build` — builds backend image, starts Caddy + backend containers
5. Verifies `https://api.localmate.crewcircle.co/health`

Caddy auto-provisions SSL via Let's Encrypt on first request.

---

## Phase E — Verify

```bash
curl -fsS https://api.localmate.crewcircle.co/health
# {"status":"ok","project":"local-biz-au"}

curl -fsI https://localmate.crewcircle.co | head -1
# HTTP/2 200
```

---

## Rollback

- **Dashboard (Vercel):** Vercel dashboard → Deployments → Instant Rollback
- **Backend:** `ssh root@170.64.183.45 'cd /opt/localmate/deploy && docker compose -f docker-compose.deployed.yml down'` then redeploy previous code

---

## SSL gotchas

- Caddy auto-manages Let's Encrypt certs for `api.localmate.crewcircle.co`
- DNS records must be **DNS-only** (not proxied) for Caddy's HTTP-01 challenge to work
- If Cloudflare proxy is enabled, set SSL mode to "Full (strict)"