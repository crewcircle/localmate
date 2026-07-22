-- 016_appointment_claim.sql
-- Claim metadata + follow-up bookkeeping columns on `appointments` (Phase 2 — Clinical).
--
-- Includes the C6 latent-bug fix: the daily Rebook job already writes
-- `followup_error` / `followup_message` / `followup_sid` but the columns never
-- existed, so every follow-up insert silently failed (or relied on the caller
-- never reading them). They are added here with `add column if not exists` so the
-- job's insert succeeds.
--
-- `practitioner_id` / `practitioner_name` are folded in here (the appointments
-- column migration) because the rewritten job writes the practitioner context per
-- follow-up row; without them the insert would reference non-existent columns.

alter table appointments add column if not exists practitioner_id   text;
alter table appointments add column if not exists practitioner_name text;

alter table appointments add column if not exists claim_type       text;    -- 'bulk_billed'|'gap'|'private_health'|'unknown'
alter table appointments add column if not exists claim_fund       text;
alter table appointments add column if not exists claim_gap_amount numeric(10,2);

alter table appointments add column if not exists followup_error   text;
alter table appointments add column if not exists followup_message text;
alter table appointments add column if not exists followup_sid     text;

comment on column appointments.claim_type is 'Best-effort Medicare/health-fund claim type from PMS billing (D3-A: kept out of SMS copy)';
