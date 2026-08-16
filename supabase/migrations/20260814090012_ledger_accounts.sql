-- ledger_accounts: the chart of accounts for Infinity's internal double-entry
-- bookkeeping. merchant_id is null for platform-level accounts (e.g. fee
-- revenue) and set for per-merchant accounts (e.g. a merchant's wallet).

create table public.ledger_accounts (
  id uuid primary key default gen_random_uuid(),

  merchant_id uuid references public.merchants (id) on delete cascade,

  name text not null,
  account_type text not null
    check (account_type in ('asset', 'liability', 'equity', 'revenue', 'expense')),
  purpose text not null
    check (purpose in (
      'merchant_wallet', 'platform_revenue', 'settlement_clearing',
      'fee_receivable', 'disbursement_payable'
    )),
  currency text not null default 'TZS' check (currency ~ '^[A-Z]{3}$'),

  -- Cached running balance for fast reads. Source of truth is
  -- sum(ledger_entries.amount) for this account; kept in sync by the
  -- application/service layer, not by a trigger, at this stage.
  balance numeric(18, 2) not null default 0,

  is_active boolean not null default true,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.ledger_accounts is
  'Chart of accounts for internal double-entry bookkeeping.';
comment on column public.ledger_accounts.merchant_id is
  'Null for platform-level accounts (e.g. fee revenue); set for a merchant''s own accounts (e.g. their wallet).';
comment on column public.ledger_accounts.balance is
  'Cached balance; must reconcile to sum(ledger_entries) for this account.';

-- One account per (purpose, currency): partial unique indexes because a
-- plain UNIQUE constraint treats every null merchant_id as distinct.
create unique index ledger_accounts_merchant_purpose_key
  on public.ledger_accounts (merchant_id, purpose, currency) where merchant_id is not null;
create unique index ledger_accounts_platform_purpose_key
  on public.ledger_accounts (purpose, currency) where merchant_id is null;

create index ledger_accounts_merchant_id_idx on public.ledger_accounts (merchant_id);
create index ledger_accounts_purpose_idx on public.ledger_accounts (purpose);

create trigger ledger_accounts_set_updated_at
  before update on public.ledger_accounts
  for each row execute function public.set_updated_at();

alter table public.ledger_accounts enable row level security;

-- Planned shape: platform-internal by default; a merchant may eventually get
-- read-only access to their own wallet account.
--   create policy "platform admins can manage ledger accounts"
--     on public.ledger_accounts for all
--     using (auth.jwt() ->> 'role' = 'platform_admin');
