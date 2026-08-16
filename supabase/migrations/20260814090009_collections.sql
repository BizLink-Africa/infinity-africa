-- collections: an attempt to pull money from a customer (a USSD/STK/Selcom
-- Pesa push, or a dynamic QR scan). One collection produces at most one
-- ledger transaction (see transactions.collection_id).

create table public.collections (
  id uuid primary key default gen_random_uuid(),

  merchant_id uuid not null references public.merchants (id) on delete cascade,
  customer_id uuid references public.customers (id) on delete set null,
  payment_link_id uuid references public.payment_links (id) on delete set null,
  invoice_id uuid references public.invoices (id) on delete set null,

  method text not null
    check (method in ('USSD_PUSH', 'STK_PUSH', 'SELCOM_PESA_PUSH', 'DYNAMIC_QR')),

  amount numeric(14, 2) not null check (amount > 0),
  currency text not null default 'TZS' check (currency ~ '^[A-Z]{3}$'),

  customer_phone text,

  status text not null default 'pending'
    check (status in ('pending', 'processing', 'successful', 'failed', 'reversed', 'cancelled')),

  provider text,
  provider_reference text,

  initiated_at timestamptz not null default now(),
  completed_at timestamptz,

  metadata jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint collections_single_source check (payment_link_id is null or invoice_id is null)
);

comment on table public.collections is
  'A single attempt to collect money from a customer via mobile money push or QR.';
comment on column public.collections.provider is
  'The processing network, e.g. ''selcom'', ''mpesa'', ''tigopesa'', ''airtelmoney''.';
comment on column public.collections.provider_reference is
  'The provider''s own transaction reference, once available.';
comment on column public.collections.customer_phone is
  'Phone number the push was sent to; not applicable to DYNAMIC_QR.';

create index collections_merchant_id_idx on public.collections (merchant_id);
create index collections_customer_id_idx on public.collections (customer_id);
create index collections_payment_link_id_idx on public.collections (payment_link_id);
create index collections_invoice_id_idx on public.collections (invoice_id);
create index collections_status_idx on public.collections (status);
create unique index collections_provider_reference_key
  on public.collections (provider_reference) where provider_reference is not null;

create trigger collections_set_updated_at
  before update on public.collections
  for each row execute function public.set_updated_at();

alter table public.collections enable row level security;

-- Planned shape:
--   create policy "merchant staff can view their own collections"
--     on public.collections for select
--     using (merchant_id in (select merchant_id from public.merchant_users where user_id = auth.uid()));
