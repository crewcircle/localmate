-- 014_practitioners.sql
-- Practitioners table (Phase 2 — Clinical). First-class practitioner records so the
-- daily Rebook follow-up can reference the right clinician and honour per-practitioner
-- opt-outs. One row per (client, booking_system, external PMS practitioner id).
--
-- Adapters UPSERT rows here from appointment results (C5) so opt-outs and the
-- dashboard have records even before a follow-up is ever sent.

create table if not exists practitioners (
  id             uuid primary key default gen_random_uuid(),
  client_id      uuid references clients(id) not null,
  external_id    text not null,            -- PMS practitioner id
  booking_system text not null,            -- which PMS this id belongs to
  name           text,                     -- display name
  do_not_contact boolean default false,    -- suppress follow-ups routed to this practitioner
  active         boolean default true,
  created_at     timestamptz default now(),
  unique(client_id, booking_system, external_id)
);

alter table practitioners enable row level security;

drop policy if exists "service_role_all" on practitioners;
create policy "service_role_all" on practitioners
  using (auth.role() = 'service_role');

create index if not exists practitioners_client_idx on practitioners(client_id);
