-- checkout_orders: the order "shell" created by Selcom Checkout's
-- Create Order - Minimal endpoint (POST /v1/checkout/create-order-minimal,
-- https://developers.selcommobile.com/#create-order-minimal) — Step 1 for
-- STK/USSD/wallet push, payment-link checkout, and dynamic QR/token
-- display. Deliberately distinct from public.collections: a collection is
-- one attempt to actually pull money via a specific method (method is
-- NOT NULL there); an order created here doesn't commit to a method yet
-- — it just returns a payment_token/qr/gateway URL a later step (not
-- implemented yet — see app/services/selcom_checkout/client.py's module
-- docstring) uses to actually collect payment.

create table public.checkout_orders (
  id uuid primary key default gen_random_uuid(),

  merchant_id uuid not null references public.merchants (id) on delete cascade,
  payment_link_id uuid references public.payment_links (id) on delete set null,

  -- Server-generated (generate_reference("ORD")), never client-supplied —
  -- see app/services/checkout_orders.py — this is what Selcom's own
  -- "order_id" field receives, distinct from merchant_reference below.
  order_id text not null,
  merchant_reference text,

  buyer_email text not null,
  buyer_name text not null,
  buyer_phone text not null,
  amount numeric(14, 2) not null check (amount > 0),
  currency text not null default 'TZS' check (currency ~ '^[A-Z]{3}$'),
  buyer_remarks text,
  merchant_remarks text,
  no_of_items integer not null check (no_of_items > 0),

  status text not null default 'created'
    check (status in ('created', 'completed', 'failed', 'cancelled', 'expired')),

  provider text not null default 'selcom',
  provider_reference text,
  gateway_buyer_uuid text,
  payment_token text,
  qr text,
  payment_gateway_url text,

  provider_result_code text,
  provider_result text,
  provider_message text,

  raw_response jsonb not null default '{}'::jsonb,

  initiated_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.checkout_orders is
  'An order shell created via Selcom Checkout''s Create Order - Minimal endpoint — precedes an actual payment attempt, does not itself move money.';
comment on column public.checkout_orders.order_id is
  'Server-generated reference sent to Selcom as "order_id" — guaranteed unique, never client-supplied.';
comment on column public.checkout_orders.payment_gateway_url is
  'Decoded (not base64) for direct use — Selcom''s own response has this base64-encoded, per developers.selcommobile.com: "All URLs in the request and response are base64 encoded."';
comment on column public.checkout_orders.raw_response is
  'The complete, unmodified Selcom response body, kept for support/reconciliation debugging even when the parsed fields alone don''t explain what happened.';

create index checkout_orders_merchant_id_idx on public.checkout_orders (merchant_id);
create index checkout_orders_payment_link_id_idx on public.checkout_orders (payment_link_id);
create index checkout_orders_status_idx on public.checkout_orders (status);
create unique index checkout_orders_merchant_order_id_key
  on public.checkout_orders (merchant_id, order_id);
create unique index checkout_orders_provider_reference_key
  on public.checkout_orders (provider_reference) where provider_reference is not null;

create trigger checkout_orders_set_updated_at
  before update on public.checkout_orders
  for each row execute function public.set_updated_at();

alter table public.checkout_orders enable row level security;

-- Planned shape (same convention as public.collections):
--   create policy "merchant staff can view their own checkout orders"
--     on public.checkout_orders for select
--     using (merchant_id in (select merchant_id from public.merchant_users where user_id = auth.uid()));
