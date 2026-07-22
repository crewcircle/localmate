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
