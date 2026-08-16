-- payment_links: a reusable or one-off "pay me" link a merchant shares with a
-- customer. Powers the public checkout at /pay/[public_slug].

create table public.payment_links (
  id uuid primary key default gen_random_uuid(),

  merchant_id uuid not null references public.merchants (id) on delete cascade,
  customer_id uuid references public.customers (id) on delete set null,

  amount numeric(14, 2) not null check (amount > 0),
  currency text not null default 'TZS' check (currency ~ '^[A-Z]{3}$'),

  customer_name text,
  customer_phone text,
  description text,

  -- Subset of collection methods the customer may pay with (see collections.method).
  allowed_payment_methods text[] not null
    default array['USSD_PUSH', 'STK_PUSH', 'SELCOM_PESA_PUSH', 'DYNAMIC_QR'],

  expires_at timestamptz,
  status text not null default 'ACTIVE'
    check (status in ('ACTIVE', 'PAID', 'EXPIRED', 'CANCELLED')),

  public_slug text not null,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint payment_links_methods_valid check (
    allowed_payment_methods <@ array['USSD_PUSH', 'STK_PUSH', 'SELCOM_PESA_PUSH', 'DYNAMIC_QR']::text[]
    and cardinality(allowed_payment_methods) > 0
  )
);

comment on table public.payment_links is
  'A shareable checkout link for collecting a specific amount from a customer.';
comment on column public.payment_links.public_slug is
  'Short public identifier used in the /pay/[public_slug] URL — not the row id.';
comment on column public.payment_links.allowed_payment_methods is
  'Collection methods the customer can choose from (subset of collections.method).';

create unique index payment_links_public_slug_key on public.payment_links (public_slug);
create index payment_links_merchant_id_idx on public.payment_links (merchant_id);
create index payment_links_customer_id_idx on public.payment_links (customer_id);
create index payment_links_status_idx on public.payment_links (status);
create index payment_links_expires_at_idx on public.payment_links (expires_at) where expires_at is not null;

create trigger payment_links_set_updated_at
  before update on public.payment_links
  for each row execute function public.set_updated_at();

alter table public.payment_links enable row level security;

-- Planned shape:
--   create policy "merchant staff can manage their own payment links"
--     on public.payment_links for all
--     using (merchant_id in (select merchant_id from public.merchant_users where user_id = auth.uid()));
--   create policy "anyone can view an active payment link"
--     on public.payment_links for select
--     using (status = 'ACTIVE');
