-- selcom_webhook_events: raw log of INCOMING webhook deliveries from Selcom
-- to POST /v1/webhooks/selcom. Distinct from public.webhook_events (which is
-- Infinity's OUTBOUND notifications to a merchant's own webhook_url).
--
-- The unique (provider, event_id) constraint IS the idempotency mechanism:
-- a duplicate delivery fails to insert, and the endpoint catches that to
-- short-circuit as already-processed rather than reprocessing side effects.

create table public.selcom_webhook_events (
  id uuid primary key default gen_random_uuid(),

  provider text not null default 'selcom',
  event_id text not null,
  event_type text not null,

  raw_body text not null,
  signature text,
  signature_valid boolean not null default false,

  status text not null default 'received'
    check (status in ('received', 'processed', 'failed', 'duplicate')),
  processing_error text,

  received_at timestamptz not null default now(),
  processed_at timestamptz,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  unique (provider, event_id)
);

comment on table public.selcom_webhook_events is
  'Raw log of incoming Selcom webhook deliveries; (provider, event_id) uniqueness is the idempotency guard against duplicate delivery.';
comment on column public.selcom_webhook_events.event_id is
  'The provider''s own reference for this event (e.g. its provider_reference), used for dedup.';
comment on column public.selcom_webhook_events.raw_body is
  'Exact bytes received, kept for signature verification/audit.';

create index selcom_webhook_events_status_idx on public.selcom_webhook_events (status);
create index selcom_webhook_events_event_type_idx on public.selcom_webhook_events (event_type);

create trigger selcom_webhook_events_set_updated_at
  before update on public.selcom_webhook_events
  for each row execute function public.set_updated_at();

alter table public.selcom_webhook_events enable row level security;

-- No policies: platform-internal only, written and read exclusively by
-- apps/api via service_role — never queried directly by a client.
