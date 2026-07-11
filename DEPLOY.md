# Deploy — localmate

Public repo: https://github.com/crewcircle/localmate
Target domain: **localmate.crewcircle.co** (dashboard) / **api.localmate.crewcircle.co** (backend)

---

## Architecture

| Layer | Host | Domain | Trigger |
|---|---|---|---|
| Next.js dashboard | **Vercel** | `localmate.crewcircle.co` | GitHub Actions `deploy.yml` on push to `main` |
| FastAPI + APScheduler | **Docker Compose + Caddy** on shared DigitalOcean Sydney droplet (`170.64.183.45`) | `api.localmate.crewcircle.co` | `scripts/deploy_backend.sh` via Doppler |
| Postgres | **Supabase** | `*.supabase.co` | Pulumi provisioner |
| Secrets | **Doppler** `localmate/prd` (inherits `crewcircle-master/prod`) | — | Doppler CLI |
| DNS | **Cloudflare** | `crewcircle.co` zone | `scripts/finish_infra.sh` via Doppler |

The backend shares the same droplet as **TaxFlowAI** — Caddy routes `api.localmate.crewcircle.co` to the localmate backend container and `api.taxflow.crewcircle.com.au` to the taxflow backend container. No new droplet needed.

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