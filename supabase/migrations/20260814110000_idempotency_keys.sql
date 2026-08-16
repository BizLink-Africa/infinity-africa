-- idempotency_keys: backs the Idempotency-Key header on money-moving
-- endpoints (initiating a collection or disbursement) so a retried request
-- — same merchant, same key, same endpoint — replays the original response
-- instead of double-processing. Written and read only by apps/api via
-- service_role; there is no client-facing use for this table.

create table public.idempotency_keys (
  id uuid primary key default gen_random_uuid(),

  merchant_id uuid not null references public.merchants (id) on delete cascade,
  key text not null,
  endpoint text not null,

  -- Hash of the normalized request body. If the same (merchant_id, key,
  -- endpoint) is replayed with a *different* body, that's a client bug
  -- (key reuse), not a legitimate retry — callers should reject it.
  request_hash text not null,

  status text not null default 'in_progress' check (status in ('in_progress', 'completed')),
  response_status int,
  response_body jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  unique (merchant_id, key, endpoint)
);

comment on table public.idempotency_keys is
  'Request/response cache keyed by (merchant_id, Idempotency-Key header, endpoint), so retried money-moving requests replay rather than double-process.';

create index idempotency_keys_merchant_id_idx on public.idempotency_keys (merchant_id);

create trigger idempotency_keys_set_updated_at
  before update on public.idempotency_keys
  for each row execute function public.set_updated_at();

alter table public.idempotency_keys enable row level security;

-- No policies: this table is backend-internal bookkeeping, never queried
-- directly by a client (dashboard or otherwise).
