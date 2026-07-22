-- 023_rankings_local_pack.sql
-- Add Google Maps / Local Pack rank alongside organic rank.
-- place_id lives on locations (per C6), not here — rankings keeps map_position only.
-- position (organic) stays as-is; unique(client_id, keyword, week_start) unchanged.

alter table rankings
  add column if not exists map_position integer;  -- null = not in local pack / not matched
