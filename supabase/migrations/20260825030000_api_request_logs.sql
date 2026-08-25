-- api_request_logs: one row per API-key-authenticated HTTP request — the
-- request-level log the task brief asks for, distinct from audit_logs
-- (business actions like "collection.created") and from webhook_events
-- (outbound deliveries). Written by ApiRequestLogMiddleware
-- (app/middleware/api_request_log.py) after every request that resolved
-- an API key, success or failure alike (status_code captures both).

create table public.api_request_logs (
  id uuid primary key default gen_random_uuid(),

  merchant_id uuid not null references public.merchants (id) on delete cascade,
  api_key_id uuid references public.api_keys (id) on delete set null,

  environment text not null check (environment in ('sandbox', 'live')),
  method text not null,
  path text not null,
  status_code integer not null,
  ip_address text,
  duration_ms integer,

  created_at timestamptz not null default now()
);

comment on table public.api_request_logs is
  'One row per API-key-authenticated HTTP request — for the merchant/Super Admin "API Logs" views. Written best-effort by ApiRequestLogMiddleware; never blocks or fails the underlying request.';

create index api_request_logs_merchant_id_idx on public.api_request_logs (merchant_id, created_at desc);
create index api_request_logs_api_key_id_idx on public.api_request_logs (api_key_id);

alter table public.api_request_logs enable row level security;

alter table public.api_keys
  add column last_used_ip text;

comment on column public.api_keys.last_used_ip is
  'IP of the most recent successfully-authenticated request using this key — written by the same middleware that logs api_request_logs.';
