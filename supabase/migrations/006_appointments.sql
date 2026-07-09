-- 006_appointments.sql
-- Patient appointment records for follow-up automation in service-based businesses.

create table appointments (
  id uuid primary key default gen_random_uuid(),
  client_id uuid references clients(id) not null,
  patient_id text not null,
  patient_name text,
  patient_phone text,
  patient_email text,
  treatment_type text,
  appointment_date date not null,
  status text default 'completed',             -- 'completed'|'cancelled'|'noshow'
  has_future_booking boolean default false,
  followup_sent boolean default false,
  followup_channel text,                       -- 'sms'|'email'
  followup_sent_at timestamptz,
  do_not_contact boolean default false,
  created_at timestamptz default now()
);

alter table appointments enable row level security;

create policy "service_role_all" on appointments
  using (auth.role() = 'service_role');
