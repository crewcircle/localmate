-- 022_square_sync_state.sql
-- Reconcile watermark for Square catalog inbound. On each catalog.version.updated
-- webhook, SearchCatalogObjects is called with begin_time = stored latest_time;
-- the response's latest_time becomes the new watermark (persisted after apply).

create table square_sync_state (
  client_id     uuid primary key references clients(id),
  latest_time   text,                             -- last SearchCatalogObjects latest_time watermark
  updated_at    timestamptz default now()
);

alter table square_sync_state enable row level security;

create policy "service_role_all" on square_sync_state
  using (auth.role() = 'service_role');
