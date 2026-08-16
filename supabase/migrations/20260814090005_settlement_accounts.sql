-- settlement_accounts: Infinity's own bank/provider accounts that collections
-- settle into and disbursements are paid out from. Platform-level, not
-- per-merchant — see super-admin "Settlement Accounts".

create table public.settlement_accounts (
  id uuid primary key default gen_random_uuid(),

  provider text not null,   -- e.g. 'selcom', 'crdb', 'nmb'
  account_type text not null
    check (account_type in ('mobile_money', 'bank')),
  account_name text not null,
  account_number text not null,
  currency text not null default 'TZS' check (currency ~ '^[A-Z]{3}$'),

  is_active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  unique (provider, account_number)
);

comment on table public.settlement_accounts is
  'Infinity''s own provider/bank accounts used to receive settlements and fund payouts.';

create index settlement_accounts_provider_idx on public.settlement_accounts (provider);
create index settlement_accounts_is_active_idx on public.settlement_accounts (is_active);

create trigger settlement_accounts_set_updated_at
  before update on public.settlement_accounts
  for each row execute function public.set_updated_at();

alter table public.settlement_accounts enable row level security;

-- Planned shape: platform-internal only — no merchant should ever read this table.
--   create policy "platform admins can manage settlement accounts"
--     on public.settlement_accounts for all
--     using (auth.jwt() ->> 'role' = 'platform_admin');
