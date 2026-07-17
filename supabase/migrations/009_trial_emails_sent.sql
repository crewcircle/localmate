-- 009_trial_emails_sent.sql
-- Idempotency table for trial milestone emails (day1, day7, day13, expired).
-- Prevents duplicate sends when the scheduler runs more than once per day.

create table if not exists trial_emails_sent (
  id         uuid primary key default gen_random_uuid(),
  client_id  uuid not null references clients(id) on delete cascade,
  day_number int  not null,
  sent_at    timestamptz default now(),
  unique(client_id, day_number)
);

comment on table trial_emails_sent is 'Tracks which trial milestone emails have been sent per client to prevent duplicates.';
