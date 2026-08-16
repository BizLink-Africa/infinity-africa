-- merchants needs somewhere to record where webhook_events.target_url comes
-- from — add the merchant's own webhook endpoint + signing secret. Nullable:
-- a merchant with no webhook_url configured simply has no events enqueued
-- for them yet.

alter table public.merchants
  add column webhook_url text,
  add column webhook_secret text;

comment on column public.merchants.webhook_url is
  'Merchant-configured endpoint that webhook_events are delivered to. Null if not yet configured.';
comment on column public.merchants.webhook_secret is
  'Shared secret used to HMAC-sign outbound webhook payloads so the merchant can verify authenticity.';
