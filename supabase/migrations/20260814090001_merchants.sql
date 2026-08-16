-- merchants: the businesses (tenants) that use Infinity to accept payments
-- and send payouts. Every merchant-owned row elsewhere in the schema traces
-- back to merchants.id.

create table public.merchants (
  id uuid primary key default gen_random_uuid(),

  business_name text not null,
  legal_name text,
  country text not null default 'TZ' check (country ~ '^[A-Z]{2}$'),
  currency text not null default 'TZS' check (currency ~ '^[A-Z]{3}$'),

  contact_email text not null,
  contact_phone text,

  -- Overall account lifecycle, set by platform staff (super-admin "Merchants").
  status text not null default 'pending'
    check (status in ('pending', 'active', 'suspended', 'closed')),

  -- Compliance review outcome — tracked separately from `status` because a
  -- merchant can be `active` while a re-verification is `pending`.
  kyc_status text not null default 'unverified'
    check (kyc_status in ('unverified', 'pending', 'verified', 'rejected')),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.merchants is
  'Businesses (tenants) using Infinity to accept payments and send payouts.';
comment on column public.merchants.status is
  'Account lifecycle: pending (onboarding) -> active -> suspended/closed.';
comment on column public.merchants.kyc_status is
  'Compliance review outcome, independent of account `status`.';

create unique index merchants_contact_email_key on public.merchants (lower(contact_email));
create index merchants_status_idx on public.merchants (status);
create index merchants_kyc_status_idx on public.merchants (kyc_status);

create trigger merchants_set_updated_at
  before update on public.merchants
  for each row execute function public.set_updated_at();

alter table public.merchants enable row level security;

-- RLS placeholder: no policies yet, so anon/authenticated PostgREST clients
-- can read/write nothing until real policies land (service_role always
-- bypasses RLS — keep that key server-side only, never ship it to a client).
-- Planned shape, once merchant auth exists:
--   create policy "merchant staff can view their own merchant"
--     on public.merchants for select
--     using (id in (select merchant_id from public.merchant_users where user_id = auth.uid()));
