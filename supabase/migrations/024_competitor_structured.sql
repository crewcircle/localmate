-- 024_competitor_structured.sql
-- Phase 4: structured extraction for competitor snapshots + GBP provisioning-state
-- columns on clients + drafts.external_action_url (Yelp guided posting).
--
-- competitor_snapshots already has RLS + service_role_all from 005_competitors.sql;
-- these are ALTER TABLE ADD COLUMN so no new policy is needed.

-- Structured extraction for competitor snapshots.
alter table competitor_snapshots
  add column if not exists structured_data jsonb default '{}'::jsonb,  -- {prices, menu_items, schema_types, raw_jsonld}
  add column if not exists structured_diff jsonb;                      -- list of {kind, name, old, new} vs previous snapshot

-- GBP notification provisioning state on clients (D15-B full automation).
-- gbp_account_id lives on locations (C2); these columns track the provisioning
-- workflow outcome so the dashboard / ops can see status at a glance.
alter table clients
  add column if not exists provisioning_status text,           -- 'pending'|'active'|'failed'
  add column if not exists provisioning_error text,            -- last provisioning error (nullable)
  add column if not exists pubsub_topic text,                  -- shared pub/sub topic resource name
  add column if not exists notification_registered_at timestamptz;  -- when notificationSetting was registered

-- Yelp guided manual posting: store the external action URL (Yelp review deep link)
-- on the draft so the dashboard can show "copy reply + open Yelp".
alter table drafts
  add column if not exists external_action_url text;           -- e.g. Yelp review reply deep link
