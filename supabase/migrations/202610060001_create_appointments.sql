-- ClinicaFlow: initial appointment storage. Apply once using Supabase SQL Editor.
create extension if not exists pgcrypto;
create extension if not exists btree_gist;

create table public.appointments (
  id uuid primary key default gen_random_uuid(),
  patient_name text not null check (char_length(patient_name) between 1 and 100),
  contact text not null check (char_length(contact) between 1 and 120),
  service text not null check (char_length(service) between 1 and 100),
  professional text not null check (char_length(professional) between 1 and 100),
  starts_at timestamp not null,
  ends_at timestamp not null,
  status text not null default 'confirmada'
    check (status in ('confirmada', 'cancelada')),
  created_at timestamptz not null default now(),
  check (ends_at > starts_at)
);

create index appointments_starts_at_idx on public.appointments (starts_at);
create index appointments_professional_starts_at_idx
  on public.appointments (professional, starts_at);

alter table public.appointments
  add constraint appointments_no_overlapping_confirmed
  exclude using gist (
    professional with =,
    tsrange(starts_at, ends_at, '[)') with &&
  )
  where (status = 'confirmada');

alter table public.appointments enable row level security;
revoke all on table public.appointments from anon, authenticated;
grant all on table public.appointments to service_role;
