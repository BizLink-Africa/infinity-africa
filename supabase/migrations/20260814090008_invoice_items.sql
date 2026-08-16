-- invoice_items: line items belonging to an invoice. invoices.subtotal is
-- expected to equal the sum of line_total across its items — kept in sync by
-- the application layer, not enforced in SQL, to avoid cross-table triggers
-- at this stage.

create table public.invoice_items (
  id uuid primary key default gen_random_uuid(),

  invoice_id uuid not null references public.invoices (id) on delete cascade,

  description text not null,
  quantity numeric(12, 2) not null default 1 check (quantity > 0),
  unit_price numeric(14, 2) not null check (unit_price >= 0),
  line_total numeric(14, 2) generated always as (quantity * unit_price) stored,

  sort_order int not null default 0,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.invoice_items is
  'Line items for an invoice. line_total is derived — never set it directly.';

create index invoice_items_invoice_id_idx on public.invoice_items (invoice_id);

create trigger invoice_items_set_updated_at
  before update on public.invoice_items
  for each row execute function public.set_updated_at();

alter table public.invoice_items enable row level security;

-- Planned shape:
--   create policy "merchant staff can manage items on their own invoices"
--     on public.invoice_items for all
--     using (invoice_id in (
--       select id from public.invoices where merchant_id in (
--         select merchant_id from public.merchant_users where user_id = auth.uid()
--       )
--     ));
