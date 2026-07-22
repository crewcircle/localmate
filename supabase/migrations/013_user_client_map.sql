-- 013_user_client_map.sql
-- User -> client ownership binding for tenant authorization (C8/D20).
--
-- Maps a Supabase auth user (the JWT `sub` claim) to exactly one client/tenant
-- row so that client-scoped endpoints derive `client_id` from the authenticated
-- identity via this table — NEVER from a request body/query param. This is the
-- Phase 1 prerequisite (D20-A) that all later client-scoped endpoints reuse
-- (/billing/usage, /billing/portal, /locations, /practitioners, /rankings, …).
--
-- One client per user (1:1) today; a later phase may relax to many-if-needed.
-- RLS + service_role_all policy matches 001_clients.sql so the service-role
-- backend can read/write (the backend uses the Supabase service role key).

create table user_client_map (
  user_id     text primary key,                       -- Supabase auth user id (JWT `sub`)
  client_id   uuid not null references clients(id),   -- owned client/tenant
  created_at  timestamptz default now()
);

alter table user_client_map enable row level security;

create policy "service_role_all" on user_client_map
  using (auth.role() = 'service_role');
