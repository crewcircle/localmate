# Local Biz Automation — Coolify Deployment Guide

> Read this alongside the spec at `files/AGENT.md` (Phase 9) and `files/local-business-automation-plan.md`.

## Overview

- **Backend** → Coolify on a DigitalOcean Sydney droplet.
- **Frontend (dashboard)** → Vercel.
- **Secrets** → Doppler (no `.env` files in containers).
- **DNS** → Cloudflare (provisioned by `packages/infra/bin/newproject`).

## 1. Backend — Coolify

### 1.1 Provision a DigitalOcean droplet

1. Create a droplet in the **Sydney (syd1)** region.
2. Image: Ubuntu 22.04 LTS, plan: **Basic $12/mo (1 GB RAM, 1 vCPU)** is sufficient at launch. Scale up at 50+ clients.
3. Attach SSH key.
4. SSH into the droplet and install Coolify:
   ```bash
   ssh root@<droplet-ip>
   curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
   ```
   The installer exposes the Coolify dashboard at `http://<droplet-ip>:8000`.

### 1.2 Create the backend application in Coolify

1. Coolify dashboard → **+ New Application** → **GitHub Repository**.
2. Authorize Coolify's GitHub App to read the `crewcircle/local-biz-au` repo (the one provisioned by `packages/infra/bin/newproject`).
3. Select the repo → **Production** environment.
4. **Root Directory:** `apps/local-biz-au/backend`
5. **Build Pack:** Dockerfile (Coolify detects `Dockerfile` automatically).
6. **Port:** 8000
7. **Domain:** `api-localbiz.crewcircle.com.au`
   - Coolify issues a Let's Encrypt cert automatically.
   - Cloudflare DNS for this hostname was provisioned by Pulumi (`packages/infra/template/__main__.py`).

### 1.3 Inject secrets via Doppler

Coolify surfaces Docker runtime env vars via its own UI, but we use Doppler as the source of truth so that secret rotation is one command.

1. Create a Doppler service token:
   ```bash
   doppler configs tokens create --project local-biz-au --config prod --name coolify-backend
   ```
   Copy the resulting `dp.st.prod.…` token.

2. In Coolify's application settings → **Environment Variables** add:
   ```
   DOPPLER_TOKEN=<paste-token-here>
   ```

3. Modify the Dockerfile CMD (override in Coolify's **Command** field, do NOT edit the Dockerfile) to run Doppler:
   ```
   CMD:  doppler run -- cmd uv run uvicorn main:app --host 0.0.0.0 --port 8000
   ```
   Add a `doppler` install step to the Dockerfile OR install the Doppler CLI in the Coolify base image.
   - Recommended: install Doppler in the Dockerfile `RUN` step:
     ```dockerfile
     RUN curl -Ls https://cli.doppler.com/install.sh | sh && \
         doppler --version
     ```
     (Note: this requires editing the Dockerfile; do this when wiring up deploy.)

4. Coolify's health check uses the `/health` endpoint defined in the Dockerfile `HEALTHCHECK` directive.

### 1.4 Deploy

Click **Deploy** in Coolify. First build takes ~3-5 minutes. Subsequent builds <1 minute (uv + Docker layer cache).

### 1.5 Verify

```bash
curl https://api-localbiz.crewcircle.com.au/health
# {"status":"ok","project":"local-biz-au"}
```

If this fails:
- Check Coolify build logs for compile errors.
- Check runtime logs for `init_db()` failures (Supabase URL/key missing in Doppler).
- Check Cloudflare DNS propagation (`dig api-localbiz.crewcircle.com.au`).

## 2. Frontend — Vercel

### 2.1 Link the dashboard to Vercel

From the monorepo root:
```bash
cd apps/local-biz-au/dashboard
vercel link
# When prompted, select the crewcircle team and "local-biz-au" project.
# If the project doesn't exist yet, vercel will create it.
```

### 2.2 Configure environment

In the Vercel dashboard (or `vercel env add`):

```
NEXT_PUBLIC_API_URL=https://api-localbiz.crewcircle.com.au
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=<from Doppler STRIPE_PUBLISHABLE_KEY>
```

Set these in **Production** environment.

### 2.3 Custom domain

In Vercel → Project → Settings → Domains → add `localbiz.crewcircle.com.au`.
Cloudflare DNS was provisioned by Pulumi. Vercel issues the SSL cert.

### 2.4 Deploy

```bash
cd apps/local-biz-au/dashboard && vercel --prod
```

### 2.5 Verify

Visit `https://localbiz.crewcircle.com.au`. Should redirect to `/dashboard` and show the approval queue with stub data.

## 3. Stripe webhook

In the Stripe dashboard → Developers → Webhooks → add endpoint:
- URL: `https://api-localbiz.crewcircle.com.au/webhooks/stripe`
- Events: `customer.subscription.trial_will_end`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`

Stripe signs each event with `STRIPE_WEBHOOK_SECRET` — this is provisioned by Pulumi (`packages/infra/template/__main__.py`) and surfaced into Doppler.

## 4. Sentry project

Pulumi creates a Sentry project named `local-biz-au`. The `SENTRY_DSN` env var is provisioned in Doppler. The FastAPI app initializes Sentry in `main.py` (will be added when Phase 2 wires up error handling).

## 5. Rollback

Coolify keeps last 5 deployments. Rollback via Coolify UI → Deployments → rollback.

Vercel keeps every deployment. `vercel rollback <deployment-url>` from CLI.

## 6. Costs at 50 clients

- DigitalOcean droplet (Sydney, 2 GB): $12/mo
- Supabase Pro: $25/mo
- Resend (10k emails free, then $20/mo for 50k): $0-20
- Twilio SMS: $0.0085 × ~5000/mo = ~$21
- DataForSEO: $0.60/mo
- Claude (Haiku 4.5): ~$5/mo
- Vercel: $0 (Free plan sufficient for dashboard)
- Cloudflare DNS: $0
- **Total: ~$70/mo vs ~$9,950/mo revenue → ~99% net margin**