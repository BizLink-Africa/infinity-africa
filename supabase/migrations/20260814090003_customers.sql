-- customers: a merchant's own customers. Populated as people pay via
-- payment links/invoices; also referenceable up front (e.g. importing a list).

create table public.customers (
  id uuid primary key default gen_random_uuid(),

  merchant_id uuid not null references public.merchants (id) on delete cascade,

  full_name text,
  phone text,
  email text,
  external_reference text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint customers_has_contact check (phone is not null or email is not null)
);

comment on table public.customers is
  'A merchant''s own customers — scoped per-merchant, not shared across tenants.';
comment on column public.customers.external_reference is
  'Optional merchant-supplied identifier (e.g. their own CRM customer ID).';

create unique index customers_merchant_phone_key
  on public.customers (merchant_id, phone) where phone is not null;
create unique index customers_merchant_email_key
  on public.customers (merchant_id, lower(email)) where email is not null;
create index customers_merchant_id_idx on public.customers (merchant_id);

create trigger customers_set_updated_at
  before update on public.customers
  for each row execute function public.set_updated_at();

alter table public.customers enable row level security;

-- Planned shape:
--   create policy "merchant staff can manage their own customers"
--     on public.customers for all
--     using (merchant_id in (select merchant_id from public.merchant_users where user_id = auth.uid()));
