-- 015_patient_external_ids.sql
-- Per-PMS patient id columns on `patients` (Phase 2 — Clinical). Lets the daily
-- Rebook follow-up look up `do_not_contact` via `adapter.ID_COLUMN` for the new
-- booking systems (cliniko_id / square_id already exist in 008). All nullable — a
-- patient only carries the id for the booking system they were seen under.

alter table patients add column if not exists nookal_id      text;
alter table patients add column if not exists halaxy_id      text;
alter table patients add column if not exists hotdoc_id      text;
alter table patients add column if not exists jane_id        text;
alter table patients add column if not exists practicepal_id text;

comment on column patients.nookal_id      is 'External Nookal patient id (do_not_contact lookup)';
comment on column patients.halaxy_id      is 'External Halaxy (FHIR Patient) id';
comment on column patients.hotdoc_id      is 'External HotDoc patient id (partner-gated)';
comment on column patients.jane_id        is 'External Jane.app patient id (partner-gated)';
comment on column patients.practicepal_id is 'External PracticePal patient id (partner-gated)';

-- Partial unique indexes: one patient per (client, external_id) per PMS.
-- Nullable columns excluded from the index so NULLs never conflict.
create unique index patients_client_nookal_idx      on patients(client_id, nookal_id)      where nookal_id is not null;
create unique index patients_client_halaxy_idx      on patients(client_id, halaxy_id)      where halaxy_id is not null;
create unique index patients_client_hotdoc_idx      on patients(client_id, hotdoc_id)      where hotdoc_id is not null;
create unique index patients_client_jane_idx        on patients(client_id, jane_id)        where jane_id is not null;
create unique index patients_client_practicepal_idx on patients(client_id, practicepal_id) where practicepal_id is not null;
