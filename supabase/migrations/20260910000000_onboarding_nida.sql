-- Combined merchant signup: NIDA (Tanzania National ID) number is now a
-- mandatory field collected on the single signup page, alongside the
-- business details. Two optional fields land here too — a TIN number and
-- an expected monthly transaction volume. All three live on
-- onboarding_submissions (not on merchants) because they belong to the
-- onboarding review record, same as every other business-details field.
--
-- Identity data — never exposed publicly:
--   * onboarding_submissions already has RLS: SELECT is limited to the
--     merchant's own active members and super admins (see
--     20260815090000_onboarding.sql). No insert/update policy — written by
--     apps/api (service_role) only.
--   * The API response model (OnboardingSubmissionResponse) exposes only a
--     masked `nida_last4`, never the full number.
--   * app/core/nida.py normalises to digits-only; the full value is never
--     logged.

alter table public.onboarding_submissions
  add column if not exists nida_number text,
  add column if not exists tin_number text,
  add column if not exists expected_monthly_volume text;

comment on column public.onboarding_submissions.nida_number is
  'Tanzania NIDA (National ID) number, digits only. Mandatory at signup. Identity data — RLS-restricted, only ever surfaced to the Super Admin UI masked (last 4 digits).';
comment on column public.onboarding_submissions.tin_number is
  'Optional Tax Identification Number provided at signup.';
comment on column public.onboarding_submissions.expected_monthly_volume is
  'Optional free-text expected monthly transaction volume provided at signup.';
