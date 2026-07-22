-- 003_reviews.sql
-- Draft review response table. Stores AI-generated draft replies pending human approval.

create table drafts (
  id          uuid primary key default gen_random_uuid(),
  client_id   uuid references clients(id) not null,
  job         text not null,          -- Which automation job created this draft: 'review_reply', 'seo_report', etc.
  source_id   text,                    -- External ID (e.g. Yelp review ID, Google review ID)
  source      text,                    -- Platform name: 'google', 'yelp', 'facebook', 'healthshare'
  draft_text  text not null,
  status      text default 'pending_approval',  -- 'pending_approval'|'approved'|'rejected'|'sent'
  metadata    jsonb,                   -- Arbitrary payload from the generating job
  created_at  timestamptz default now(),
  actioned_at timestamptz              -- When the draft was approved/rejected/sent
);

alter table drafts enable row level security;

create policy "service_role_all" on drafts
  using (auth.role() = 'service_role');

-- Trial users can create drafts but have read-only access to existing ones
create policy "trial_read_only_drafts" on drafts
  for insert
  with check (
    exists (select 1 from clients c where c.id = drafts.client_id
      and (c.subscription_status = 'active'
           or (c.trial_status = 'active' and c.trial_ends_at > now())))
  );
