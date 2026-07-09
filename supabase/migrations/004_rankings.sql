-- 004_rankings.sql
-- Weekly SEO ranking snapshots per keyword per location.

create table rankings (
  id uuid primary key default gen_random_uuid(),
  client_id uuid references clients(id),
  keyword text not null,        -- The search term tracked
  location text not null,        -- Geographic qualifier (e.g. 'Sydney NSW', 'Melbourne VIC')
  position integer,              -- Search result position; null = not found in top 30
  week_start date not null,      -- Monday of the tracked week (ISO week start)
  captured_at timestamptz default now(),
  unique(client_id, keyword, week_start)
);

alter table rankings enable row level security;

create policy "service_role_all" on rankings
  using (auth.role() = 'service_role');
