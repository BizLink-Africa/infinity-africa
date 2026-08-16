-- ledger_entries: immutable double-entry postings against ledger_accounts.
-- Every row traces back to the transaction that caused it, and for any given
-- transaction the sum of its debits must equal the sum of its credits — that
-- is enforced below by a deferred constraint trigger, not just documented.

create table public.ledger_entries (
  id uuid primary key default gen_random_uuid(),

  transaction_id uuid not null references public.transactions (id) on delete restrict,
  ledger_account_id uuid not null references public.ledger_accounts (id) on delete restrict,

  direction text not null check (direction in ('debit', 'credit')),
  amount numeric(14, 2) not null check (amount > 0),
  currency text not null default 'TZS' check (currency ~ '^[A-Z]{3}$'),

  description text,

  created_at timestamptz not null default now()
  -- No updated_at: rows are append-only, see the immutability trigger below.
);

comment on table public.ledger_entries is
  'Immutable double-entry postings. Debits must equal credits per transaction_id (enforced by trigger).';

create index ledger_entries_transaction_id_idx on public.ledger_entries (transaction_id);
create index ledger_entries_ledger_account_id_idx on public.ledger_entries (ledger_account_id);

create trigger ledger_entries_immutable
  before update or delete on public.ledger_entries
  for each row execute function public.forbid_mutation();

create or replace function public.enforce_ledger_balance()
returns trigger
language plpgsql
as $$
declare
  v_transaction_id uuid;
  v_debits numeric(18, 2);
  v_credits numeric(18, 2);
begin
  v_transaction_id := new.transaction_id;

  select
    coalesce(sum(amount) filter (where direction = 'debit'), 0),
    coalesce(sum(amount) filter (where direction = 'credit'), 0)
  into v_debits, v_credits
  from public.ledger_entries
  where transaction_id = v_transaction_id;

  if v_debits <> v_credits then
    raise exception 'ledger_entries for transaction % are unbalanced: debits % <> credits %',
      v_transaction_id, v_debits, v_credits;
  end if;

  return null;
end;
$$;

comment on function public.enforce_ledger_balance() is
  'Deferred check that debits = credits per transaction_id once a SQL transaction commits.';

-- Deferred so a caller can insert several rows (e.g. one debit + one credit)
-- inside a single transaction and only have the balance checked at COMMIT.
-- Only needs to run AFTER INSERT: UPDATE/DELETE are already blocked above.
create constraint trigger ledger_entries_balanced
  after insert on public.ledger_entries
  deferrable initially deferred
  for each row execute function public.enforce_ledger_balance();

alter table public.ledger_entries enable row level security;

-- Planned shape: platform-internal only.
--   create policy "platform admins can view ledger entries"
--     on public.ledger_entries for select
--     using (auth.jwt() ->> 'role' = 'platform_admin');
