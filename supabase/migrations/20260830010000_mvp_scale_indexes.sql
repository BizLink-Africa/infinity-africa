-- MVP scale readiness (30-100 active merchants): every table already has a
-- merchant_id/status index from its original migration, but the three
-- busiest tables — collections (one row per push/QR attempt, successful or
-- not), transactions, and ledger_entries — had no index at all on
-- created_at, the column every "recent activity"/date-range merchant
-- dashboard view sorts by. At a few hundred rows this doesn't matter; once
-- a single busy merchant accumulates thousands of rows it forces a
-- sequential-scan-then-sort on every dashboard load. Composite
-- (merchant_id, created_at desc) — matching the existing convention at
-- api_request_logs_merchant_id_idx (20260825030000_api_request_logs.sql) —
-- serves "this merchant's rows, newest first" directly from the index,
-- without also needing (and duplicating) the existing bare merchant_id
-- index, which stays as-is; this migration only adds indexes, never drops
-- one.
--
-- email_deliveries.email_type and api_keys.key_prefix are lower-volume,
-- lower-risk gaps (email_deliveries stays small — a handful of outbound
-- emails per merchant per day; api_keys is near-static, a handful of rows
-- per merchant total) but are cheap and safe to add now rather than
-- revisit later.

create index collections_merchant_id_created_at_idx
  on public.collections (merchant_id, created_at desc);

create index transactions_merchant_id_created_at_idx
  on public.transactions (merchant_id, created_at desc);

create index ledger_entries_ledger_account_id_created_at_idx
  on public.ledger_entries (ledger_account_id, created_at desc);

create index email_deliveries_email_type_idx
  on public.email_deliveries (email_type);

create index api_keys_key_prefix_idx
  on public.api_keys (key_prefix);
