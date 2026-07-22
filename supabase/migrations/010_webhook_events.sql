-- 010_webhook_events.sql
-- Durable inbound-webhook log. Every inbound webhook (Stripe / GBP / menu) is
-- persisted here before processing so nothing is silently dropped. Processing
-- happens asynchronously via arq; the reconciler re-enqueues stuck `pending`
-- rows. Dedupe by (provider, idempotency_key).

create table webhook_events (
  id               uuid primary key default gen_random_uuid(),
  provider         text not null,                    -- 'stripe' | 'gbp' | 'menu'
  idempotency_key  text not null,                    -- provider event id / synthetic hash
  event_type       text,                             -- e.g. 'customer.subscription.updated'
  payload          jsonb not null,
  status           text not null default 'pending',  -- pending|processing|done|failed
  attempts         int  not null default 0,
  last_error       text,
  created_at       timestamptz default now(),
  processed_at     timestamptz,
  unique (provider, idempotency_key)                 -- dedupe
);

create index webhook_events_status_created_idx on webhook_events (status, created_at);

alter table webhook_events enable row level security;

create policy "service_role_all" on webhook_events
  using (auth.role() = 'service_role');
