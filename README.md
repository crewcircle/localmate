# local-biz-au

Local Biz Automation — a multi-tenant SaaS for Australian small-and-medium
businesses. Five automation jobs run on APScheduler inside a FastAPI app;
a Next.js dashboard gives owners an approval queue, SEO/competitor reports,
client management, and per-tenant settings.

## Services (Jobs)

| # | Job | Schedule (AEST) | Price |
|---|-----|-----------------|-------|
| 1 | **Review Guard** — AI-drafted replies to Google Business Profile & Yelp reviews | Yelp poll every 24h; GBP via webhook | $149–$249/mo |
| 2 | **Rank Report** — weekly local SERP rank tracking + plain-English email brief | Monday 06:00 | $99–$199/mo |
| 3 | **Competitor Watch** — weekly website diff + Claude brief + threat level | Sunday 22:00 | $199–$299/mo |
| 4 | **Rebook** — lapsed-patient SMS/email follow-up with AU holiday gate | Daily 08:00 | $299–$499/mo |
| 5 | **Menu Sync** — Google Sheets → GBP + Square Catalog | Webhook-driven | $149/mo |

## Stack

- **Backend** — FastAPI (Python 3.11), APScheduler (no Celery/Redis until 500+ clients), Supabase (Postgres + RLS), Claude Haiku 4.5
- **Dashboard** — Next.js 15 App Router, Tailwind v4, TypeScript
- **Integrations** — Stripe (AUD recurring + GST), Twilio, Resend, DataForSEO, Google Business Profile, Cliniko/Square booking adapters
- **Infra** — Doppler secrets, Coolify on DigitalOcean Sydney droplet, Cloudflare DNS

## Repo layout

```
.
├── backend/          # FastAPI + APScheduler — see backend/pyproject.toml
├── dashboard/        # Next.js 15 dashboard
├── supabase/
│   └── migrations/   # 7 SQL migrations — apply in order
└── DEPLOY.md         # Coolify + Vercel deployment guide
```

## Quickstart (local)

```bash
# Backend
cd backend
cp .env.example .env.local   # fill in Doppler-sourced values
uv sync
uv run uvicorn main:app --reload --port 8001
# /health should return 200

# Dashboard
cd ../dashboard
cp .env.example .env.local
npm install
npm run dev
# http://localhost:3000 → redirects to /dashboard
```

## Trial system

14-day no-card trial. Caps: 100 review drafts, 2 SEO reports, 1 competitor brief,
50 follow-up messages. Card collected on day 12 via Stripe `SetupIntent`;
hard cutoff at day 14 + 23:59 AEST. Trial email sequence is APScheduler-driven.

## Deploy

See [`DEPLOY.md`](./DEPLOY.md) for Coolify (backend) and Vercel (dashboard)
deployment, plus Stripe webhook and Doppler token configuration.