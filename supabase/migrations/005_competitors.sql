-- 005_competitors.sql
-- Captured competitor website snapshots with AI-generated briefs after diff analysis.

create table competitor_snapshots (
  id uuid primary key default gen_random_uuid(),
  client_id uuid references clients(id) not null,
  competitor_url text not null,
  content_hash text not null,    -- SHA256 of fetched HTML for change detection
  content_text text,             -- Raw text content scraped from competitor page
  brief_text text,               -- Claude-generated brief summarising what changed since last snapshot
  threat_level text,             -- 'LOW'|'MEDIUM'|'HIGH' — estimated competitive threat
  captured_at timestamptz default now()
);

alter table competitor_snapshots enable row level security;

create policy "service_role_all" on competitor_snapshots
  using (auth.role() = 'service_role');
