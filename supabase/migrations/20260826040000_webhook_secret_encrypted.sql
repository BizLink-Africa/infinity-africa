-- Replaces plaintext merchants.webhook_secret (20260814110001) with a
-- reversibly-encrypted column (see app/core/secret_box.py) — outbound
-- webhook signing needs the raw secret, so it can't be hash-only like an
-- API key secret, but it must not sit in the database as plaintext either.
-- The old webhook_secret column is left in place, unused by new code, so
-- no destructive drop is needed; any merchant with a secret configured
-- under the old column simply needs to regenerate one (POST
-- /v1/merchant/webhook-config with regenerate_secret=true) to get an
-- encrypted value under the new column.

alter table public.merchants
  add column webhook_secret_encrypted text;

comment on column public.merchants.webhook_secret_encrypted is
  'Fernet-encrypted webhook signing secret (see app/core/secret_box.py). Superseded plaintext webhook_secret — that column is no longer written by the application.';
