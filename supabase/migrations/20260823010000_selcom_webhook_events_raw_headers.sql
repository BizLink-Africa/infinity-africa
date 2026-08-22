-- Adds raw_headers to selcom_webhook_events: the exact header *names* (and,
-- for the Checkout callback signing headers specifically, their values —
-- Timestamp/Digest/Digest-Method/Signed-Fields are protocol metadata, not
-- secrets) received on a delivery. Added after the first real Selcom
-- Checkout webhook delivery on 2026-08-22 arrived with all four expected
-- signing headers completely absent, and there was no way to see what
-- Selcom *did* send instead — this closes that gap for the next delivery.
-- Never stores Authorization/Cookie if somehow present (filtered at the
-- application layer, not here).

alter table public.selcom_webhook_events
  add column raw_headers jsonb;

comment on column public.selcom_webhook_events.raw_headers is
  'Header names (and non-secret signing-related header values) from this delivery, for diagnosing an unexpected/rejected signature scheme. Never Authorization/Cookie.';
