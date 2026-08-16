-- api_keys: merchant-issued credentials for calling the Infinity API
-- directly. Only a hash of the secret is ever stored — the plaintext key is
-- shown once, at creation time, by the application layer and never persisted.

create table public.api_keys (
  id uuid primary key default gen_random_uuid(),

  merchant_id uuid not null references public.merchants (id) on delete cascade,

  name text not null,
  environment text not null default 'sandbox'
    check (environment in ('sandbox', 'live')),

  key_prefix text not null,   -- e.g. "ik_live_7f3a" — safe to display in the UI
  hashed_key text not null,   -- sha-256 (or similar) hash of the full secret

  status text not null default 'active'
    check (status in ('active', 'revoked')),
  last_used_at timestamptz,
  revoked_at timestamptz,

  created_by uuid references auth.users (id) on delete set null,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint api_keys_revoked_consistency
    check ((status = 'revoked') = (revoked_at is not null))
);

comment on table public.api_keys is
  'Merchant API credentials. Stores a hash only — never the plaintext secret.';
comment on column public.api_keys.hashed_key is
  'Hash of the secret key; the plaintext is shown once at creation and discarded.';
comment on column public.api_keys.key_prefix is
  'Short, non-secret prefix of the key, safe to show in the dashboard for identification.';

create unique index api_keys_hashed_key_key on public.api_keys (hashed_key);
create index api_keys_merchant_id_idx on public.api_keys (merchant_id);
create index api_keys_environment_idx on public.api_keys (environment);
create index api_keys_status_idx on public.api_keys (status);

create trigger api_keys_set_updated_at
  before update on public.api_keys
  for each row execute function public.set_updated_at();

alter table public.api_keys enable row level security;

-- Planned shape:
--   create policy "merchant owners/admins can manage their own api keys"
--     on public.api_keys for all
--     using (merchant_id in (
--       select merchant_id from public.merchant_users
--       where user_id = auth.uid() and role in ('owner', 'admin')
--     ));
