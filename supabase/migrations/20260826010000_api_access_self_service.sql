-- Business decision amendment: production API keys are now self-service —
-- a merchant creates their own `live` key the moment they're approved
-- (status='active'), KYC-verified, and have a resolvable pricing rule; no
-- per-merchant Super Admin "enable production" step is required anymore
-- (see app/services/api_access.py). merchants.api_production_enabled from
-- 20260825010000 is left in place but no longer consulted by that gate —
-- dropping a column is riskier than leaving an unused one, and some
-- deployments may still have historical rows worth keeping for audit.
--
-- The replacement lever a Super Admin keeps is the opposite direction:
-- suspending a merchant's API access outright (blocks BOTH sandbox and
-- live self-service, and existing keys stop authenticating — see
-- app/auth/dependencies.py::verify_api_key) — for abuse/fraud response,
-- not routine onboarding.

alter table public.merchants
  add column api_access_suspended boolean not null default false,
  add column api_access_suspended_at timestamptz,
  add column api_access_suspended_by uuid references auth.users (id) on delete set null;

comment on column public.merchants.api_access_suspended is
  'Super Admin kill switch: true blocks ALL API key authentication (sandbox and live) for this merchant, regardless of approval status.';
