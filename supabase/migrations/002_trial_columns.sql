-- 002_trial_columns.sql
-- Trial lifecycle columns on clients table for freemium onboarding.

alter table clients add column if not exists
  trial_started_at  timestamptz;   -- When the trial period began
alter table clients add column if not exists
  trial_ends_at     timestamptz;   -- When the trial expires (auto-convert or lock)
alter table clients add column if not exists
  trial_status      text default 'active';  -- 'active'|'expired'|'converted'|'cancelled'
alter table clients add column if not exists
  card_collected_at timestamptz;   -- When the user first provided payment method
alter table clients add column if not exists
  trial_usage       jsonb default '{}'::jsonb;  -- Per-job-type usage counter {reviews: 3, seo: 1}
