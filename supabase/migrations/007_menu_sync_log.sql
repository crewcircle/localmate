-- 007_menu_sync_log.sql
-- Audit log for menu item sync operations to third-party platforms.

create table menu_sync_log (
  id uuid primary key default gen_random_uuid(),
  client_id uuid references clients(id) not null,
  item_name text not null,
  price_cents integer,                -- Price in cents (AUD) at time of sync
  target text not null,               -- 'gbp'|'square'|'website'|'ubereats'|'doordash'|'lightspeed'
  status text not null,               -- 'synced'|'failed'
  error_message text,
  synced_at timestamptz default now()
);

alter table menu_sync_log enable row level security;

create policy "service_role_all" on menu_sync_log
  using (auth.role() = 'service_role');
