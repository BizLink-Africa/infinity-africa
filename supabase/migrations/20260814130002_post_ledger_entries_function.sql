-- post_ledger_entries: the only way ledger_entries + ledger_accounts.balance
-- are ever written together. supabase-py/PostgREST cannot wrap multiple
-- .insert()/.update() calls in one client-side transaction, so without this
-- function each entry would commit separately — the deferred
-- ledger_entries_balanced trigger (debits = credits per transaction_id,
-- checked at COMMIT) would then fail on the first, unbalanced entry alone.
-- Looping over the whole batch inside one PL/pgSQL function body makes the
-- entire post — every entry's insert plus every account's balance update —
-- a single Postgres transaction.
--
-- p_entries shape: a jsonb array of
--   {transaction_id, ledger_account_id, direction, amount, currency, description?}
-- matching the columns of public.ledger_entries.

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
  v_delta numeric(18, 2);
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

    select account_type into v_account_type
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

    update public.ledger_accounts
    set balance = balance + v_delta
    where id = v_row.ledger_account_id;

    return next v_row;
  end loop;

  return;
end;
$$;

comment on function public.post_ledger_entries(jsonb) is
  'Atomically inserts a batch of ledger_entries and updates each ledger_accounts.balance in one transaction, so the deferred debits=credits trigger sees the whole batch at once.';

-- Money-moving; restrict to service_role (apps/api) only.
revoke execute on function public.post_ledger_entries(jsonb) from public, anon, authenticated;
grant execute on function public.post_ledger_entries(jsonb) to service_role;
