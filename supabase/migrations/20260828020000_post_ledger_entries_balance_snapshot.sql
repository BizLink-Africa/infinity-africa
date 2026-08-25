-- Extends post_ledger_entries (20260814130002, 20260814140001) to also
-- write balance_before/balance_after on each inserted ledger_entries row
-- (20260828010000) — using the same v_balance (read under `for update`
-- lock, before the delta is applied) and v_new_balance (after) the function
-- already computes for the no-negative-balance check. No new locking, no
-- new query: the atomic, race-proof snapshot was already being computed
-- here, just not persisted per-row until now.
--
-- The account lookup/lock now happens BEFORE the insert (previously after),
-- since ledger_entries is immutable — an UPDATE to backfill the snapshot
-- after inserting would be rejected outright by its own forbid_mutation
-- trigger. Locking the account first and inserting the entry with its
-- snapshot already known keeps the operation order-equivalent otherwise:
-- the lock is still held for the same span, across the same insert.

create or replace function public.post_ledger_entries(p_entries jsonb)
returns setof public.ledger_entries
language plpgsql
security definer
set search_path = public
as $$
declare
  v_entry jsonb;
  v_row public.ledger_entries;
  v_account_id uuid;
  v_direction text;
  v_amount numeric(14, 2);
  v_account_type text;
  v_purpose text;
  v_balance numeric(18, 2);
  v_delta numeric(18, 2);
  v_new_balance numeric(18, 2);
begin
  for v_entry in select * from jsonb_array_elements(p_entries)
  loop
    v_account_id := (v_entry ->> 'ledger_account_id')::uuid;
    v_direction := v_entry ->> 'direction';
    v_amount := (v_entry ->> 'amount')::numeric;

    select account_type, purpose, balance into v_account_type, v_purpose, v_balance
    from public.ledger_accounts
    where id = v_account_id
    for update;

    -- Asset/expense accounts increase on debit, decrease on credit;
    -- liability/equity/revenue accounts increase on credit, decrease on debit.
    if v_account_type in ('asset', 'expense') then
      v_delta := case when v_direction = 'debit' then v_amount else -v_amount end;
    else
      v_delta := case when v_direction = 'credit' then v_amount else -v_amount end;
    end if;

    v_new_balance := v_balance + v_delta;

    if v_purpose = 'merchant_wallet' and v_new_balance < 0 then
      raise exception 'INSUFFICIENT_BALANCE: wallet % balance % cannot cover a % of % (would be %)',
        v_account_id, v_balance, v_direction, v_amount, v_new_balance;
    end if;

    insert into public.ledger_entries (
      transaction_id, ledger_account_id, direction, amount, currency, description,
      balance_before, balance_after
    ) values (
      (v_entry ->> 'transaction_id')::uuid,
      v_account_id,
      v_direction,
      v_amount,
      coalesce(v_entry ->> 'currency', 'TZS'),
      v_entry ->> 'description',
      v_balance,
      v_new_balance
    )
    returning * into v_row;

    update public.ledger_accounts
    set balance = v_new_balance
    where id = v_account_id;

    return next v_row;
  end loop;

  return;
end;
$$;

comment on function public.post_ledger_entries(jsonb) is
  'Atomically inserts a batch of ledger_entries (with a balance_before/after snapshot on each) and updates each ledger_accounts.balance in one transaction; rejects the whole batch if it would take a merchant_wallet balance negative.';

-- Money-moving; restrict to service_role (apps/api) only. CREATE OR REPLACE
-- preserves existing grants, but restated here so this migration is
-- self-contained.
revoke execute on function public.post_ledger_entries(jsonb) from public, anon, authenticated;
grant execute on function public.post_ledger_entries(jsonb) to service_role;
