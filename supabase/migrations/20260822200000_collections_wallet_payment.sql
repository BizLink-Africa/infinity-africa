-- Wallet-push collections (Selcom Checkout's two-step
-- create-order-minimal -> wallet-payment flow, POST
-- /v1/checkout/wallet-payment) link back to the order shell that
-- preceded them, and carry their own provider result fields distinct
-- from the order-creation call's — mirrors the disbursements table's
-- selcom_trans_id/selcom_receipt/selcom_status/selcom_raw_response
-- convention (never guess at what happened; store the full real
-- response).

alter table public.collections
  add column checkout_order_id uuid references public.checkout_orders (id) on delete set null,
  add column provider_transid text,
  add column provider_resultcode text,
  add column provider_result text,
  add column provider_message text,
  add column raw_response jsonb not null default '{}'::jsonb;

comment on column public.collections.checkout_order_id is
  'The checkout_orders row (create-order-minimal) this wallet-push attempt was made against, when applicable.';
comment on column public.collections.provider_transid is
  'The transid this backend generated and sent to Selcom''s wallet-payment call — distinct from provider_reference, which Selcom assigns back.';
comment on column public.collections.raw_response is
  'The complete, unmodified Selcom wallet-payment response body, kept for support/reconciliation debugging even when the parsed fields alone don''t explain what happened.';

create index collections_checkout_order_id_idx on public.collections (checkout_order_id);
