-- 017_locations.sql
-- Multi-location table: single source of truth for GBP account/location identity (C2),
-- per-venue Square location, menu sync targets, and place_id (moved from rankings per C6).
-- Backfills a default location for existing clients from clients.gbp_location_id /
-- clients.menu_sync_targets so current single-venue clients keep working.

create table locations (
  id                  uuid primary key default gen_random_uuid(),
  client_id           uuid references clients(id) not null,
  name                text not null,                  -- venue label e.g. "Prefecture 48 Surry Hills"
  suburb              text,
  state               text,
  gbp_account_id      text,                           -- per-venue GBP account id (was missing entirely — latent bug fix)
  gbp_location_id     text,                           -- per-venue GBP location id
  square_location_id  text,                           -- per-venue Square location id
  place_id            text,                           -- stable Google Maps place id (moved from rankings per C6)
  menu_sync_targets   text[] default '{}',            -- per-location sync targets (authoritative; clients.menu_sync_targets deprecated)
  is_default          boolean default false,          -- true for the backfilled single-venue row
  created_at          timestamptz default now(),
  deleted_at          timestamptz
);

create index locations_client_id_idx on locations (client_id);
create unique index locations_gbp_location_id_idx on locations (gbp_location_id) where gbp_location_id is not null;
create unique index locations_square_location_id_idx on locations (square_location_id) where square_location_id is not null;

alter table locations enable row level security;

create policy "service_role_all" on locations
  using (auth.role() = 'service_role');

-- Backfill: for each client with gbp_location_id or menu_sync_targets, insert one
-- is_default location carrying gbp_location_id + menu_sync_targets so existing
-- sync keeps working without manual location setup.
insert into locations (client_id, name, suburb, state, gbp_location_id, menu_sync_targets, is_default)
select
  c.id,
  c.business_name,
  c.suburb,
  c.state,
  c.gbp_location_id,
  coalesce(c.menu_sync_targets, '{}'::text[]),
  true
from clients c
where c.gbp_location_id is not null
   or (c.menu_sync_targets is not null and array_length(c.menu_sync_targets, 1) > 0);
