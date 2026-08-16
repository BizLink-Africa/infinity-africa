-- Payment link flow completion: fields the checkout/merchant-portal flow
-- needs that the original payment_links table didn't carry, plus a
-- failure_reason column on collections (which already serves as the
-- "payment link attempts" table via collections.payment_link_id — no new
-- table needed for that).

alter table public.payment_links
  add column customer_email text,
  add column merchant_reference text,
  add column success_redirect_url text,
  add column failure_redirect_url text,
  add column paid_at timestamptz;

comment on column public.payment_links.merchant_reference is
  'The merchant''s own internal reference for this link (e.g. an order ID) — display-only, never used to look anything up.';
comment on column public.payment_links.success_redirect_url is
  'Where the customer''s browser is sent after a successful payment, if the merchant configured one.';
comment on column public.payment_links.failure_redirect_url is
  'Where the customer''s browser is sent after a failed payment attempt, if the merchant configured one.';
comment on column public.payment_links.paid_at is
  'Set once, when status transitions to PAID — distinct from updated_at, which changes on every write.';

alter table public.collections
  add column failure_reason text;

comment on column public.collections.failure_reason is
  'Set when status = ''failed'' — the provider-reported (or internal) reason, same text already sent in the outbound collection.failed webhook payload.';
