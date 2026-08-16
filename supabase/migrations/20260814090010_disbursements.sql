-- disbursements: a payout from a merchant's Infinity balance to a mobile
-- money number or bank account they control.

create table public.disbursements (
  id uuid primary key default gen_random_uuid(),

  merchant_id uuid not null references public.merchants (id) on delete cascade,
  settlement_account_id uuid references public.settlement_accounts (id) on delete set null,

  method text not null
    check (method in ('SELCOM_PESA', 'MOBILE_MONEY', 'BANK_ACCOUNT')),

  amount numeric(14, 2) not null check (amount > 0),
  currency text not null default 'TZS' check (currency ~ '^[A-Z]{3}$'),

  destination_name text not null,
  destination_identifier text not null,  -- phone number or bank account number
  bank_name text,

  status text not null default 'pending'
    check (status in ('pending', 'processing', 'successful', 'failed', 'reversed', 'cancelled')),

  requires_approval boolean not null default false,
  approved_by uuid references auth.users (id) on delete set null,
  approved_at timestamptz,

  provider_reference text,

  initiated_at timestamptz not null default now(),
  completed_at timestamptz,

  metadata jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint disbursements_bank_name_required
    check (method <> 'BANK_ACCOUNT' or bank_name is not null),
  constraint disbursements_approval_consistency
    check (approved_at is null or approved_by is not null)
);

comment on table public.disbursements is
  'A payout from a merchant''s balance to a mobile money number or bank account.';
comment on column public.disbursements.requires_approval is
  'True for high-value payouts routed through the platform approval queue.';
comment on column public.disbursements.settlement_account_id is
  'The Infinity settlement account the payout is drawn from, for reconciliation.';

create index disbursements_merchant_id_idx on public.disbursements (merchant_id);
create index disbursements_settlement_account_id_idx on public.disbursements (settlement_account_id);
create index disbursements_status_idx on public.disbursements (status);
create index disbursements_requires_approval_idx
  on public.disbursements (requires_approval) where requires_approval;

create trigger disbursements_set_updated_at
  before update on public.disbursements
  for each row execute function public.set_updated_at();

alter table public.disbursements enable row level security;

-- Planned shape:
--   create policy "merchant staff can view their own disbursements"
--     on public.disbursements for select
--     using (merchant_id in (select merchant_id from public.merchant_users where user_id = auth.uid()));
