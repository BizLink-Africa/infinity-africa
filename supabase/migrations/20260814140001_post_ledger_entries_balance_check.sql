-- Extends post_ledger_entries (see 20260814130002) with the atomic,
-- race-proof half of disbursement balance safety: if any entry in the
-- batch would take a merchant_wallet account's balance negative, the whole
-- batch is rejected (the exception rolls back the entire function call,
-- since it's one Postgres transaction — nothing partially applied).
--
-- This is deliberately narrow to ledger_accounts.purpose = 'merchant_wallet'
-- — it's the merchant's *available balance*, which must never go negative;
-- other account types (settlement_clearing, platform_revenue, ...) have no
-- such constraint.
--
-- This is the backstop, not the only check: app/services/disbursements.py
-- also validates available balance up front (before even creating a
-- disbursement row) for a fast, friendly rejection — this function is what
-- makes that safe under concurrent requests, since the read-then-write
-- there isn't otherwise atomic.

create or replace function public.post_ledger_entries(p_entries jsonb)
returns setof public.ledger_entries
language plpgsql
security definer
set search_path = public
as $$
declare
  v_entry jsonb;
  v_row public.ledger_entries;
  v_account_type text;
  v_purpose text;
  v_balance numeric(18, 2);
  v_delta numeric(18, 2);
  v_new_balance numeric(18, 2);
begin
  for v_entry in select * from jsonb_array_elements(p_entries)
  loop
    insert into public.ledger_entries (
      transaction_id, ledger_account_id, direction, amount, currency, description
    ) values (
      (v_entry ->> 'transaction_id')::uuid,
      (v_entry ->> 'ledger_account_id')::uuid,
      v_entry ->> 'direction',
      (v_entry ->> 'amount')::numeric,
      coalesce(v_entry ->> 'currency', 'TZS'),
      v_entry ->> 'description'
    )
    returning * into v_row;

    select account_type, purpose, balance into v_account_type, v_purpose, v_balance
    from public.ledger_accounts
    where id = v_row.ledger_account_id
    for update;

    -- Asset/expense accounts increase on debit, decrease on credit;
    -- liability/equity/revenue accounts increase on credit, decrease on debit.
    if v_account_type in ('asset', 'expense') then
      v_delta := case when v_row.direction = 'debit' then v_row.amount else -v_row.amount end;
    else
      v_delta := case when v_row.direction = 'credit' then v_row.amount else -v_row.amount end;
    end if;

    v_new_balance := v_balance + v_delta;

    if v_purpose = 'merchant_wallet' and v_new_balance < 0 then
      raise exception 'INSUFFICIENT_BALANCE: wallet % balance % cannot cover a % of % (would be %)',
        v_row.ledger_account_id, v_balance, v_row.direction, v_row.amount, v_new_balance;
    end if;

    update public.ledger_accounts
    set balance = v_new_balance
    where id = v_row.ledger_account_id;

    return next v_row;
  end loop;

  return;
end;
$$;

comment on function public.post_ledger_entries(jsonb) is
  'Atomically inserts a batch of ledger_entries and updates each ledger_accounts.balance in one transaction; rejects the whole batch if it would take a merchant_wallet balance negative.';

-- Money-moving; restrict to service_role (apps/api) only. CREATE OR REPLACE
-- preserves existing grants, but restated here so this migration is
-- self-contained.
revoke execute on function public.post_ledger_entries(jsonb) from public, anon, authenticated;
grant execute on function public.post_ledger_entries(jsonb) to service_role;
