-- 021_menu_images.sql
-- Menu image store + column additions for C2 (drafts.location_id) and C6
-- (menu_sync_log.location_id). Images live in a Supabase storage bucket
-- `menu-images` (public read); this table records the storage path, public URL,
-- and platform-specific image ids once propagated.
--
-- The `menu-images` storage bucket must be provisioned once in the Supabase
-- dashboard (public read). Migration-level bucket creation is project-specific;
-- document as a one-time Supabase setup step if not automated.

create table menu_images (
  id                uuid primary key default gen_random_uuid(),
  menu_item_id      uuid references menu_items(id) not null,
  storage_path      text not null,               -- path in Supabase bucket 'menu-images'
  public_url        text not null,               -- used by GBP Media.Create sourceUrl
  square_image_id   text,                         -- Square CatalogImage id once uploaded
  gbp_media_name    text,                         -- GBP media resource name once uploaded
  is_primary        boolean default true,
  synced_at         timestamptz,
  created_at        timestamptz default now()
);

create index menu_images_menu_item_id_idx on menu_images (menu_item_id);

alter table menu_images enable row level security;

create policy "service_role_all" on menu_images
  using (auth.role() = 'service_role');

-- C2: drafts store the originating location_id; routers/approve.py posts using
-- the draft's location's gbp_location_id.
alter table drafts add column if not exists location_id uuid references locations(id);

-- C6: menu_sync_log records which location each sync targeted.
alter table menu_sync_log add column if not exists location_id uuid references locations(id);
