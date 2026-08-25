-- Production API access gate: a merchant must be explicitly enabled by a
-- Super Admin before they can create/rotate a `live` API key, on top of
-- already being an approved, verified merchant (status='active',
-- kyc_status='verified' — both already set together by
-- approve_onboarding_submission(), which also already lazily creates the
-- wallet and assigns pricing at that same moment). This is the fifth,
-- separate gate the task brief calls for: KYC approved + wallet created +
-- pricing assigned are already implied by status/kyc_status; this column is
-- the explicit "Super Admin enables production API access" step.

alter table public.merchants
  add column api_production_enabled boolean not null default false,
  add column api_production_enabled_at timestamptz,
  add column api_production_enabled_by uuid references auth.users (id) on delete set null;

comment on column public.merchants.api_production_enabled is
  'Explicit Super Admin gate: a merchant cannot create/rotate a live API key until this is true, even once fully KYC-approved.';
