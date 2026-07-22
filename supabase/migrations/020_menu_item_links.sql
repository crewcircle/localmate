-- 020_menu_item_links.sql
-- Cross-platform identity + loop guard. Stores the external_id and last_synced_hash
-- per (menu_item, platform). Sync to a platform is skipped when
-- last_synced_hash == content_hash, preventing echo-back loops.

create table menu_item_links (
  id                uuid primary key default gen_random_uuid(),
  menu_item_id      uuid references menu_items(id) not null,
  platform          text not null,               -- 'gbp'|'square'|'website'
  external_id       text,                         -- Square catalog object id / GBP menuItem name
  external_version  bigint,                       -- Square object version for optimistic Upsert
  last_synced_hash  text,                         -- content_hash last pushed/received for this platform
  last_synced_at    timestamptz,
  unique (menu_item_id, platform)
);

create index menu_item_links_platform_external_id_idx on menu_item_links (platform, external_id);

alter table menu_item_links enable row level security;

create policy "service_role_all" on menu_item_links
  using (auth.role() = 'service_role');
