-- 001_clients.sql
-- Primary client/tenant table. One row per local business onboarded into the system.

create table clients (
  id                    uuid primary key default gen_random_uuid(),
  business_name         text not null,                        -- Display name of the business
  business_type         text not null,                        -- e.g. 'dental', 'physio', 'restaurant'
  email                 text unique not null,                 -- Primary contact email (login identifier)
  suburb                text not null,                        -- Business suburb for local SEO targeting
  state                 text not null,                        -- Australian state (NSW, VIC, QLD, etc.)
  postcode              text,                                  -- Australian postcode
  abn                   text,                                  -- Australian Business Number for invoicing
  voice_sample          text,                                  -- Path/URL to recorded voice sample for AI voice
  active_jobs           text[] default '{}',                   -- Array of active job types e.g. {'reviews','seo'}
  menu_sync_targets     text[] default '{}',                   -- Platforms to sync menu to (gbp, square, website…)
  booking_system        text,                                  -- Third-party booking system (e.g. 'halaxy', 'square')
  stripe_customer_id    text,                                  -- Stripe customer reference
  stripe_subscription_id text,                                 -- Stripe subscription reference
  subscription_status   text default 'trialing',               -- 'trialing'|'active'|'past_due'|'canceled'
  gbp_access_token      text,                                  -- Google Business Profile OAuth access token
  gbp_refresh_token     text,                                  -- Google Business Profile OAuth refresh token
  gbp_location_id       text,                                  -- Google Business Profile location ID
  yelp_business_id      text,                                  -- Yelp business ID for review polling
  keywords              text[] default '{}',                   -- SEO keywords to track in rankings
  competitor_urls       text[] default '{}',                   -- URLs of competitor websites to monitor
  do_not_contact        boolean default false,                 -- Suppress all outbound communication
  created_at            timestamptz default now(),
  deleted_at            timestamptz                            -- Soft-delete timestamp
);

alter table clients enable row level security;

create policy "service_role_all" on clients
  using (auth.role() = 'service_role');
