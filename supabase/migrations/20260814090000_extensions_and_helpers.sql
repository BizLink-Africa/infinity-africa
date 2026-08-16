-- Extensions and shared helper functions used by every later migration.

-- gen_random_uuid() ships in Supabase's "extensions" schema by default; this
-- is a defensive no-op if it's already installed (true on every Supabase
-- project, and on a local `supabase start` Postgres image).
create extension if not exists "pgcrypto" with schema "extensions";

-- Generic "touch updated_at" trigger, attached to every mutable table below.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

comment on function public.set_updated_at() is
  'Sets updated_at = now() on every UPDATE. Attached as a BEFORE UPDATE trigger.';

-- Blocks UPDATE/DELETE outright. Attached to append-only accounting tables
-- (ledger_entries, audit_logs) so history can never be rewritten in place.
create or replace function public.forbid_mutation()
returns trigger
language plpgsql
as $$
begin
  raise exception 'rows in "%" are append-only and cannot be updated or deleted', tg_table_name;
end;
$$;

comment on function public.forbid_mutation() is
  'Raises on UPDATE/DELETE. Attached to append-only tables to enforce immutability.';
