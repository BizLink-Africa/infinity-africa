-- Audit improvement (merchant/admin Transactions display): a denormalized
-- copy of the merchant wallet's balance snapshot and posting direction for
-- this transaction, sourced from the authoritative ledger_entries row (see
-- 20260828010000/20260828020000) at write time — kept here purely so
-- listing transactions doesn't need an extra join per row.
--
-- Nullable, and NOT backfilled for existing rows: there is no verified,
-- deterministic backfill plan for historical transactions in this change,
-- per the "do not rewrite old financial history" constraint. Old rows show
-- NULL; the API/UI must render that as "Not available", never a computed
-- or guessed number.
--
-- These three columns are written once at posting time and again (updated,
-- not "corrected") only if a later posting legitimately happens against the
-- same transaction_id — e.g. a reversal — the same way transactions.status
-- already transitions from 'successful' to 'reversed'. They represent the
-- wallet state around the MOST RECENT posting for this transaction, not a
-- permanently frozen original value.

alter table public.transactions
  add column balance_before numeric(18, 2),
  add column balance_after numeric(18, 2),
  add column direction text check (direction in ('debit', 'credit'));

comment on column public.transactions.balance_before is
  'Merchant wallet balance immediately before this transaction''s most recent ledger posting. NULL if not captured (older rows, or transactions with no merchant-wallet leg).';
comment on column public.transactions.balance_after is
  'Merchant wallet balance immediately after this transaction''s most recent ledger posting. NULL if not captured.';
comment on column public.transactions.direction is
  'debit or credit against the merchant''s own wallet, from the most recent ledger posting. NULL if not captured or not wallet-affecting.';
