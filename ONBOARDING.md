# First Client Onboarding Checklist

Walk through this checklist for every new LocalMate client. Each step links to the system that handles it.

## 1. Signup & Trial

- [ ] Client visits `https://localmate.crewcircle.co` (or `localmate-eta.vercel.app` until DNS lands)
- [ ] Navigates to **Clients → Add Client** in dashboard
- [ ] Fills: business name, type (dental/restaurant/gym/salon/physio/cafe/tradie), suburb, state, jobs
- [ ] Backend `POST /auth/signup` creates:
  - [ ] Stripe Customer with AU address metadata
  - [ ] Supabase `clients` row with `trial_started_at=now`, `trial_ends_at=now+14d`
  - [ ] Welcome email sent via Resend (Day 0)
- [ ] Trial banner shows **"Trial: 14 days remaining"** in dashboard

## 2. Connect Google Business Profile (Job 1 — Review Guard)

- [ ] Client clicks **Connect GBP** in dashboard → calls `GET /auth/gbp-oauth-url?client_id=...`
- [ ] Redirects to Google OAuth consent screen
- [ ] Google redirects back with `?code=...`
- [ ] Backend `exchange_code_for_tokens(code)` stores `gbp_access_token` + `gbp_refresh_token` + `gbp_location_id` on client row
- [ ] GBP webhook subscription configured for `inbound_review` events
- [ ] Test: simulate a GBP webhook → draft appears in approval queue in <10s

## 3. Stripe Subscription (Day 12 — Card Collection)

- [ ] Trial banner switches to **"⚠ Trial ends in 2 days — add card"**
- [ ] Client clicks **Add card** → Stripe Checkout / SetupIntent
- [ ] `POST /auth/billing/setup-complete` attaches payment method, creates Subscription:
  - [ ] `trial_end` = `clients.trial_ends_at`
  - [ ] `default_tax_rates = [STRIPE_GST_RATE_ID]` (GST)
  - [ ] `payment_settings = {payment_method_types: ['card', 'au_becs_debit']}`
- [ ] Client row updated: `trial_status='converted'`, `card_collected_at=now`

## 4. Configure Jobs

### Review Guard (Job 1)
- [ ] Voice sample recorded (3 sentences in owner's words) → Settings → Voice Sample
- [ ] Yelp Business ID set if client has Yelp listing (for polling)

### Rank Report (Job 2)
- [ ] Keywords added (up to 5) → Settings → SEO Keywords
- [ ] APScheduler runs Monday 6am AEST → DataForSEO SERP API
- [ ] Resend email arrives Monday 7am AEST with plain-English delta

### Competitor Watch (Job 3)
- [ ] Competitor URLs added (up to 3) → Settings → Competitor URLs
- [ ] APScheduler runs Sunday 10pm AEST → website snapshot + Claude brief
- [ ] Brief appears in dashboard → Reports → Competitor Watch tab

### Rebook (Job 4)
- [ ] Booking system selected (cliniko/nookal/mindbody/square/halaxy)
- [ ] Cliniko API key or Square credentials stored
- [ ] APScheduler runs daily 8am AEST (skips AU public holidays)
- [ ] Test SMS sent to test number (not real patient)

### Menu Sync (Job 5)
- [ ] Google Sheet source of truth configured
- [ ] Menu sync targets selected (gbp/square/website/ubereats/doordash/lightspeed)
- [ ] Webhook endpoint `POST /webhooks/menu-update/{client_id}` configured on Google Sheets
- [ ] Test sync writes to menu_sync_log table

## 5. Trial Expiry (Day 14)

- [ ] Day 13 email sent ("Trial expires tomorrow")
- [ ] At `trial_ends_at` (14d + 23:59 AEST):
  - [ ] `check_trial_expiries()` hourly job fires
  - [ ] Client `trial_status='expired'`, `subscription_status='trial_expired'`
  - [ ] Trial expired email sent
  - [ ] Dashboard enters read-only mode

## 6. Post-Trial (Day 14+)

- [ ] If card collected: Stripe activates subscription, `activate_client_by_subscription()` sets `subscription_status='active'`
- [ ] If no card: dashboard locked to read-only, access restored after card added
- [ ] All 5 jobs continue per APScheduler schedule

## 7. Verification

- [ ] `GET /health` returns `{"status":"ok","project":"local-biz-au"}`
- [ ] GBP webhook creates Claude draft in <10s
- [ ] SEO report runs for test client without errors
- [ ] Competitor snapshot detects known page change
- [ ] Lapsed patient SMS sends to test number
- [ ] Menu sync writes to Square sandbox catalog
- [ ] Trial banner shows correct state for trialing/expiring/expired clients
- [ ] All unit tests pass in CI

## Quick API Reference

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Health check |
| `/auth/signup` | POST | Create trial client |
| `/auth/gbp-oauth-url` | GET | Get GBP OAuth URL |
| `/auth/billing/setup-complete` | POST | Collect card + create subscription |
| `/webhooks/stripe` | POST | Stripe webhook |
| `/webhooks/inbound-review` | POST | GBP review webhook |
| `/webhooks/menu-update/{client_id}` | POST | Menu sync webhook |
| `/approve/review/{draft_id}` | POST | Approve + post review reply |
| `/approve/review/{draft_id}` | DELETE | Discard draft |
| `/drafts` | GET | List drafts by status |