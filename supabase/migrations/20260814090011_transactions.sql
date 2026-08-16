-- transactions: the unified ledger of money movement — collections,
-- disbursements, fees, refunds, reversals, and manual adjustments each land
-- here as one row, which is what powers the merchant/admin "Transactions"
-- views and reconciliation.

create table public.transactions (
  id uuid primary key default gen_random_uuid(),

  merchant_id uuid not null references public.merchants (id) on delete cascade,

  reference text not null,
  provider_reference text,

  type text not null
    check (type in ('collection', 'disbursement', 'fee', 'refund', 'reversal', 'adjustment')),
  method text not null,

  collection_id uuid references public.collections (id) on delete set null,
  disbursement_id uuid references public.disbursements (id) on delete set null,

  gross_amount numeric(14, 2) not null check (gross_amount >= 0),
  fee_amount numeric(14, 2) not null default 0 check (fee_amount >= 0),
  net_amount numeric(14, 2) not null check (net_amount >= 0),
  currency text not null default 'TZS' check (currency ~ '^[A-Z]{3}$'),

  status text not null default 'pending'
    check (status in ('pending', 'processing', 'successful', 'failed', 'reversed', 'cancelled')),

  metadata jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint transactions_net_amount_consistent
    check (net_amount = gross_amount - fee_amount),
  constraint transactions_single_source
    check (collection_id is null or disbursement_id is null),
  constraint transactions_method_matches_type check (
    (type = 'collection'
      and method in ('USSD_PUSH', 'STK_PUSH', 'SELCOM_PESA_PUSH', 'DYNAMIC_QR')
      and collection_id is not null)
    or (type = 'disbursement'
      and method in ('SELCOM_PESA', 'MOBILE_MONEY', 'BANK_ACCOUNT')
      and disbursement_id is not null)
    or (type in ('fee', 'refund', 'reversal', 'adjustment')
      and method in (
        'USSD_PUSH', 'STK_PUSH', 'SELCOM_PESA_PUSH', 'DYNAMIC_QR',
        'SELCOM_PESA', 'MOBILE_MONEY', 'BANK_ACCOUNT', 'INTERNAL'
      ))
  )
);

comment on table public.transactions is
  'Unified ledger of every money movement: collections, disbursements, fees, refunds, reversals, adjustments.';
comment on column public.transactions.reference is
  'Infinity''s own canonical reference, shown to merchants (e.g. "TXN-2026-000123").';
comment on column public.transactions.provider_reference is
  'The upstream provider''s transaction reference, when the row traces back to one.';
comment on column public.transactions.method is
  'A collection or disbursement method, or ''INTERNAL'' for fee/refund/adjustment rows not tied to a payment rail.';
comment on column public.transactions.collection_id is
  'Set when type = ''collection''; the collection attempt this transaction settles.';
comment on column public.transactions.disbursement_id is
  'Set when type = ''disbursement''; the payout this transaction settles.';

create unique index transactions_reference_key on public.transactions (reference);
create unique index transactions_provider_reference_key
  on public.transactions (provider_reference) where provider_reference is not null;
create index transactions_merchant_id_idx on public.transactions (merchant_id);
create index transactions_type_idx on public.transactions (type);
create index transactions_status_idx on public.transactions (status);
create index transactions_collection_id_idx on public.transactions (collection_id);
create index transactions_disbursement_id_idx on public.transactions (disbursement_id);

create trigger transactions_set_updated_at
  before update on public.transactions
  for each row execute function public.set_updated_at();

alter table public.transactions enable row level security;

-- Planned shape:
--   create policy "merchant staff can view their own transactions"
--     on public.transactions for select
--     using (merchant_id in (select merchant_id from public.merchant_users where user_id = auth.uid()));
