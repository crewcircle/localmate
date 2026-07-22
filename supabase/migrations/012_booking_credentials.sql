-- 012_booking_credentials.sql
-- Shared booking-system credential columns on `clients`. Moved to Phase 0 (C1) so
-- the clinical (Phase 2) and menu (Phase 3) phases are order-independent and neither
-- re-adds `square_access_token`. Phase 3's 018 adds only the remaining Square OAuth
-- columns (refresh token, merchant id, expiry) and MUST NOT re-add square_access_token.
--
-- These are secrets; per D4 they may later be Fernet-encrypted-at-rest with a
-- backfill. Stored as text here to match the existing plaintext credential columns.

alter table clients add column if not exists cliniko_api_key       text;   -- Cliniko PMS API key
alter table clients add column if not exists square_access_token   text;   -- Square OAuth access token (shared by menu + appointments)
alter table clients add column if not exists nookal_api_key        text;   -- Nookal PMS API key
alter table clients add column if not exists halaxy_client_id      text;   -- Halaxy OAuth2 client_credentials id
alter table clients add column if not exists halaxy_client_secret  text;   -- Halaxy OAuth2 client_credentials secret
