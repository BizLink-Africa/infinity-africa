-- Audit improvement: capture the affected ledger_account's balance
-- immediately before and after each posting, on the posting itself.
-- ledger_entries is already append-only/immutable (see
-- 20260814090013_ledger_entries.sql's forbid_mutation trigger) — these are
-- new nullable columns only ever set at INSERT time by
-- post_ledger_entries() (20260828020000), never updated afterward. Existing
-- rows stay NULL: there is no deterministic way to retroactively assign a
-- balance snapshot to historical postings without either trusting the
-- current, already-summed ledger_accounts.balance to unwind (fragile) or a
-- full replay, neither of which this migration attempts. The API/UI must
-- treat NULL as "not available", never compute or fake a number for it.

alter table public.ledger_entries
  add column balance_before numeric(18, 2),
  add column balance_after numeric(18, 2);

comment on column public.ledger_entries.balance_before is
  'The affected ledger_accounts.balance immediately before this posting. NULL for entries posted before this column existed.';
comment on column public.ledger_entries.balance_after is
  'The affected ledger_accounts.balance immediately after this posting. NULL for entries posted before this column existed.';
