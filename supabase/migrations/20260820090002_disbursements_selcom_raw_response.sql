-- Persist the full raw Selcom Business Disbursement API response body
-- alongside the already-parsed selcom_trans_id/selcom_receipt/selcom_status
-- columns (20260820090001_disbursements_pricing_and_status.sql) — needed
-- for support/reconciliation debugging when the parsed fields alone don't
-- explain an outcome. Additive ALTER, same convention as the prior
-- migration; never editing it in place.

alter table public.disbursements
  add column selcom_raw_response jsonb;

comment on column public.disbursements.selcom_raw_response is
  'Full raw JSON response body from the Selcom Business Disbursement API''s transaction/process or transaction/query call that last updated this row (see app.services.selcom_business.parsing). Null until a real (non-mock) provider call resolves — the mock client never populates it.';
