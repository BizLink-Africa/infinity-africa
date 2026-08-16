-- API keys need scopes (collections:write, payment_links:read, etc.) so a
-- merchant can issue narrowly-permissioned credentials instead of one
-- all-access key per environment. Empty array means the key can't call any
-- scope-gated endpoint until scopes are assigned.
alter table public.api_keys
  add column scopes text[] not null default '{}';

comment on column public.api_keys.scopes is
  'Permission scopes this key was granted, e.g. collections:write, invoices:read. Checked by require_api_key_scope() for API-key callers only — dashboard JWT sessions are unaffected.';

-- Merchants can optionally narrow which webhook_events event_names actually
-- get enqueued for them. Null/empty means "all events" — the same behavior
-- enqueue_webhook_event already has today, so existing merchants see no
-- change until they explicitly opt into filtering.
alter table public.merchants
  add column webhook_subscribed_events text[];

comment on column public.merchants.webhook_subscribed_events is
  'Event names this merchant wants delivered to webhook_url. Null/empty = all events (default, matches pre-existing behavior).';
