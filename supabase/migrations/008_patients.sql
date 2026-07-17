-- 008_patients.sql
-- Per-patient record spanning all booking systems.

create table patients (
    id                  uuid primary key default gen_random_uuid(),
    client_id           uuid references clients(id) not null,
    cliniko_id          text,
    square_id           text,
    patient_name        text,
    patient_phone       text,
    patient_email       text,
    last_treatment      text,
    last_appointment_date date,
    do_not_contact      boolean default false,
    created_at          timestamptz default now(),
    deleted_at          timestamptz,
    unique(client_id, cliniko_id),
    unique(client_id, square_id)
);

alter table patients enable row level security;

create policy "service_role_all" on patients using (auth.role() = 'service_role');

create index patients_client_idx on patients(client_id);

comment on table patients is 'Per-patient record spanning all booking systems — cliniko_id and square_id are external IDs';
