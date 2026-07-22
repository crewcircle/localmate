-- 018_clients_square_oauth.sql
-- Remaining Square OAuth columns on `clients`. Per C1, `square_access_token` was
-- already added in 012 (Phase 0); this migration adds only the refresh token,
-- merchant id, and token expiry. Do NOT re-add square_access_token.

alter table clients add column if not exists square_refresh_token     text;   -- Fernet-encrypted
alter table clients add column if not exists square_merchant_id       text;
alter table clients add column if not exists square_token_expires_at  timestamptz;

-- RLS already enabled on clients table (001_clients.sql).
