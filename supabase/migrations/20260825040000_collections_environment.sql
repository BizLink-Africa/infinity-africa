-- Sandbox/live separation for API-created collections. Every existing
-- collection-creation path (dashboard, payment link, invoice) is real
-- merchant money and defaults to 'live'; only the three direct
-- server-to-server API endpoints
-- (POST /v1/collections/{wallet-push,selcom-pesa,qr}) branch on the
-- calling API key's own environment — see
-- app/services/sandbox_collections.py. A sandbox collection is created
-- with its final status set directly and NO linked transactions row, so
-- it structurally can never reach resolve_collection()'s ledger-posting
-- path — sandbox activity cannot touch a real wallet balance by
-- construction, not by a runtime check that could be bypassed.

alter table public.collections
  add column environment text not null default 'live' check (environment in ('sandbox', 'live'));

create index collections_environment_idx on public.collections (environment);

comment on column public.collections.environment is
  'sandbox collections are simulated — created with a final status directly, never touch Selcom or the ledger. live is real money, same as before this column existed.';
