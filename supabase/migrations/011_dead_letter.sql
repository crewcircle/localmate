-- 011_dead_letter.sql
-- Dead-letter store for exhausted retries — both inbound webhook processing and
-- outbound integration calls (Twilio / Resend / GBP / Square / DataForSEO). An
-- operator replays these via a CLI/script (D18-A); `replayed_at` marks handled.

create table dead_letter (
  id            uuid primary key default gen_random_uuid(),
  kind          text not null,     -- 'stripe'|'gbp'|'menu'|'twilio'|'resend'|'gbp_out'|'square'|'dataforseo'
  ref_id        text,              -- webhook_events.id or outbound target id
  payload       jsonb not null,
  error         text,
  attempts      int not null default 0,
  created_at    timestamptz default now(),
  replayed_at   timestamptz
);

create index dead_letter_kind_created_idx on dead_letter (kind, created_at);

alter table dead_letter enable row level security;

create policy "service_role_all" on dead_letter
  using (auth.role() = 'service_role');
