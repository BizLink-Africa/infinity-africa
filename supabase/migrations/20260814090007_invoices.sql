-- invoices: itemized bills a merchant sends a customer, optionally payable
-- through a linked payment_links row ("Pay Now"). Line items live in
-- invoice_items.

create table public.invoices (
  id uuid primary key default gen_random_uuid(),

  merchant_id uuid not null references public.merchants (id) on delete cascade,
  customer_id uuid references public.customers (id) on delete set null,

  invoice_number text not null,

  customer_name text,
  customer_email text,
  customer_phone text,

  due_date date not null,
  currency text not null default 'TZS' check (currency ~ '^[A-Z]{3}$'),

  subtotal numeric(14, 2) not null check (subtotal >= 0),
  tax_amount numeric(14, 2) not null default 0 check (tax_amount >= 0),
  discount_amount numeric(14, 2) not null default 0 check (discount_amount >= 0),
  total_amount numeric(14, 2) not null check (total_amount >= 0),
  amount_paid numeric(14, 2) not null default 0 check (amount_paid >= 0),

  status text not null default 'DRAFT'
    check (status in ('DRAFT', 'SENT', 'PAID', 'PARTIALLY_PAID', 'OVERDUE', 'CANCELLED')),

  payment_link_id uuid references public.payment_links (id) on delete set null,

  notes text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  unique (merchant_id, invoice_number),
  constraint invoices_total_consistent
    check (total_amount = subtotal + tax_amount - discount_amount)
);

comment on table public.invoices is
  'Itemized bills sent to a customer; line items live in invoice_items.';
comment on column public.invoices.invoice_number is
  'Merchant-facing invoice number, unique per merchant (not globally).';
comment on column public.invoices.payment_link_id is
  'The "Pay Now" payment link generated for this invoice, if any.';
comment on column public.invoices.amount_paid is
  'Running total collected against this invoice; kept in sync by the application layer.';

create index invoices_merchant_id_idx on public.invoices (merchant_id);
create index invoices_customer_id_idx on public.invoices (customer_id);
create index invoices_status_idx on public.invoices (status);
create index invoices_due_date_idx on public.invoices (due_date);
create index invoices_payment_link_id_idx on public.invoices (payment_link_id);

create trigger invoices_set_updated_at
  before update on public.invoices
  for each row execute function public.set_updated_at();

alter table public.invoices enable row level security;

-- Planned shape:
--   create policy "merchant staff can manage their own invoices"
--     on public.invoices for all
--     using (merchant_id in (select merchant_id from public.merchant_users where user_id = auth.uid()));
