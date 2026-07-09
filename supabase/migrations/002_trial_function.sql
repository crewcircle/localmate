-- 002_trial_function.sql
-- Increments the per-job-type usage counter inside the trial_usage JSONB column atomically.

create or replace function increment_trial_usage(
  p_client_id uuid,
  p_job_type  text
) returns void language plpgsql as $$
begin
  update clients
  set trial_usage = jsonb_set(
    coalesce(trial_usage, '{}'::jsonb),
    array[p_job_type],
    to_jsonb(coalesce((trial_usage ->> p_job_type)::int, 0) + 1)
  )
  where id = p_client_id;
end;
$$;
