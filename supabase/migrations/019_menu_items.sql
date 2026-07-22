-- 019_menu_items.sql
-- Canonical menu item store. Every edit (Sheets, Square inbound) upserts here first;
-- the syncer reconciles platform state from canonical. content_hash drives loop
-- prevention (menu_item_links.last_synced_hash).

create table menu_items (
  id             uuid primary key default gen_random_uuid(),
  client_id      uuid references clients(id) not null,
  location_id    uuid references locations(id) not null,
  name           text not null,
  description    text default '',
  price_cents    integer not null,
  category       text default '',
  active         boolean default true,
  content_hash   text not null,                 -- sha256(name|price_cents|description|category|active)
  origin         text default 'sheets',         -- 'sheets'|'square'|'gbp'|'manual'
  sheet_row_key  text,                           -- stable key from Sheets for matching
  created_at     timestamptz default now(),
  updated_at     timestamptz default now(),
  deleted_at     timestamptz
);

create index menu_items_location_id_idx on menu_items (location_id);
create unique index menu_items_location_sheet_row_key_idx on menu_items (location_id, sheet_row_key) where sheet_row_key is not null;

alter table menu_items enable row level security;

create policy "service_role_all" on menu_items
  using (auth.role() = 'service_role');
