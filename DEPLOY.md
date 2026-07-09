# Deploy — localmate

Public repo: https://github.com/crewcircle/localmate
Target domain: **localmate.crewcircle.co** (dashboard) / **api.localmate.crewcircle.co** (backend)

---

## Architecture (chosen split)

| Layer | Host | Domain | Trigger |
|---|---|---|---|
| Next.js dashboard | **Vercel** | `localmate.crewcircle.co` | GitHub Actions `deploy.yml` on push to `main` |
| FastAPI + APScheduler | **Coolify** on DigitalOcean Sydney droplet | `api.localmate.crewcircle.co` | Coolify git webhook (polls repo directly) |
| Postgres | **Supabase** Singapore | `*.supabase.co` | Pulumi provisioner |
| Secrets | **Doppler** | `crewcircle-master/prod` inherited | Pulumi provisioner |
| DNS | **Cloudflare** | `crewcircle.co` zone | Manual record (see step 3) |

---

## Phase A — You (manual, one-time)

### 1. Provision infra (Pulumi one-shot)

Populate `.env.local` at the CrewCircle monorepo root with all `CC_*` vars (see `packages/account-setup/.env.example`), then run:

```bash
cd /path/to/grape-tin
./packages/infra/bin/newproject local-biz-au "Local Mate" "AU SMB automation suite" 19900
```

This creates:
- Supabase project (Singapore preferred; template default is `us-east-1` — patch `template/__main__.py` line for Singapore if needed)
- Doppler project `local-biz-au` with `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY` inherited from `crewcircle-master/prod`
- Stripe product + price ($199.00 AUD recurring monthly + GST)
- Sentry project
- `packages/infra/registry.json` entry recording the project

### 2. Spin up Coolify droplet

```bash
# Create DigitalOcean Sydney droplet (s-1vcpu-2gb, $12/mo) via dashboard.do.cloud.digitalocean.com
# SSH in and install Coolify:
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

Domain to assign in Coolify application: `api.localmate.crewcircle.co`.

### 3. Cloudflare DNS records

Add these two records to the `crewcircle.co` zone in Cloudflare dashboard:

| Type | Name | Target | Proxied | Purpose |
|---|---|---|---|---|
| `CNAME` | `localmate` | `cname.vercel-dns.com` | ✅ | `localmate.crewcircle.co` → Vercel |
| `A` | `api.localmate` | `<Coolify droplet public IP>` | ✅ | `api.localmate.crewcircle.co` → Coolify |

> Proxied records get Cloudflare's auto-SSL. Use DNS-only if you prefer Let's Encrypt on the host.

### 4. Vercel — verify the custom domain

In Vercel dashboard:
- Open your `localmate` Vercel project → Settings → Domains → Add `localmate.crewcircle.co`
- Vercel shows a "Verify DNS Configuration" panel. Cloudflare propagation typically 1-5 min.
- Once `Verified` lights up, Vercel issues the SSL cert and `https://localmate.crewcircle.co` serves the dashboard.

### 5. Get Vercel secrets for the GitHub Action

In Vercel dashboard → Team → Settings → Tokens → Create token, scope: Full Access → Copy.

Then visit `https://vercel.com/crewcircle` (Team ID at top of that page) and find `VERCEL_PROJECT_ID` from your Vercel project's Settings page.

Add three repo secrets at `https://github.com/crewcircle/localmate/settings/secrets/actions`:
- `VERCEL_TOKEN`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`

(If I already ran `vercel link` for the repo, `.vercel/project.json` will hold ORG_ID + PROJECT_ID — they're safe to copy-paste; only `VERCEL_TOKEN` is actually sensitive).

---

## Phase B — CI/CD (already wired up by Sisyphus)

The repo ships with two GitHub Actions workflows in `.github/workflows/`:

- **`ci.yml`** — runs on every push/PR to `main`. Two jobs in parallel:
  - `backend` — installs Python 3.11 via `uv`, syncs deps, smoke-imports `main.app`, runs `pytest`.
  - `dashboard` — installs Node 22, `npm ci`, lints (continue-on-error), `npm run build` against `NEXT_PUBLIC_API_URL=https://api.localmate.crewcircle.co`.
- **`deploy.yml`** — runs on push to `main` only (path-restricted to `dashboard/**`). Uses Vercel CLI to `pull → build → deploy --prod --prebuilt`. Outputs the production URL in the run log.

Backend deploys automatically once Coolify is wired to the GitHub repo — Coolify polls the `main` branch directly, no Actions job needed.

---

## Phase C — Backend deploy via Coolify

1. Coolify dashboard → Add New Resource → Public Git Repository (GitHub)
2. Paste the repo URL: `https://github.com/crewcircle/localmate`
3. Base directory: `backend`
4. Port: `8000` (matches `Dockerfile` `uvicorn` cmd)
5. Health check path: `/health`
6. Domains: `api.localmate.crewcircle.co`
7. Environment variables:
   - `DOPPLER_TOKEN` — from `doppler configs tokens create --project local-biz-au --config prod`
   - (Doppler injects `SUPABASE_URL`, `STRIPE_SECRET_KEY`, etc. at runtime — no need to duplicate them)
8. Deploy. Coolify reads `backend/Dockerfile` and builds automatically.

**Container monitors health:** set Coolify's Health Check endpoint to `GET /health` — expect `{"status":"ok","project":"local-biz-au"}`.

---

## Phase D — Dashboard deploy via Vercel (one-time `vercel link` already done)

Sisyphus already ran `vercel link` from this repo's `dashboard/` subdir to create the project. That wrote `.vercel/project.json` (committed — non-secret) which ties the local clone to the Vercel project.

After that initial link:
1. Push to `main` → GitHub Actions `deploy.yml` runs `vercel deploy --prod`.
2. First manual run: from the cloned repo, `cd dashboard && vercel --prod` (with `VERCEL_TOKEN` exported locally) triggers the same production build.
3. To attach the custom domain once DNS propagates: `vercel domains add localmate.crewcircle.co localmate` under the `crewcricle` team.

---

## Phase E — Optional: Cloudflare proxy verify

Test the chain end-to-end:

```bash
# Backend health
curl -fsS https://api.localmate.crewcircle.co/health
#   should return: {"status":"ok","project":"local-biz-au"}

# Dashboard landing
curl -fsI https://localmate.crewcircle.co | head -1
#   should return: HTTP/2 200
```

---

## Domain / SSL gotchas

- Vercel auto-renews SSL for `localmate.crewcircle.co` via Cloudflare's proxied CNAME (no Let's Encrypt needed for Vercel side).
- Coolify runs its own Let's Encrypt — ensure port 80 and 443 are open on the droplet's DO firewall, and that `api.localmate.crewcircle.co` resolves to the droplet before the first deploy, otherwise Coolify's cert challenge will fail.
- If you proxy `api.localmate` via Cloudflare orange-cloud, set Cloudflare's SSL mode to "Full" (strict) so Cloudflare trusts Coolify's Let's Encrypt cert.

---

## Rollback

- **Dashboard (Vercel):** Open Vercel dashboard → Deployments → find last-known-good → "Instant Rollback".
- **Backend (Coolify):** Coolify saves last-deployed image. Hit "Rollback" in the deployment detail.