-- Bugfix: collections_single_source (20260814090009_collections.sql)
-- required payment_link_id and invoice_id to never both be set — correct
-- back when a collection was either paid directly against a payment link
-- OR directly against an invoice, never both.
--
-- That stopped being true once invoices started generating their own
-- "Pay Now" payment_links row (generate_or_reuse_invoice_payment_link) and
-- every push-collection call site (wallet_push.py, dynamic_qr.py,
-- hosted_checkout.py, selcompesa_push.py) started deliberately setting
-- BOTH fields when paying via an invoice's link — payment_link_id as the
-- direct origination, invoice_id (via
-- app/services/collection_source.py::resolve_invoice_id_for_payment_link)
-- as a derived cross-reference so the collection is a reliable ownership/
-- reporting join back to its invoice. See that function's own docstring:
-- "must carry that invoice's id ... matching every other collection-
-- creation call site" — this has been the deliberate, intended shape for
-- a while; the constraint was simply never updated to match, so every
-- single payment against an invoice's Pay Now link has been 500ing
-- outright (Postgres check constraint violation on insert), invisible to
-- `pytest` because the in-memory FakeSupabaseClient doesn't enforce CHECK
-- constraints at all.
--
-- invoice_id is always *derived from* payment_link_id in every call site
-- that sets both (never two independently-chosen, conflicting sources),
-- so there is no real invariant left for this constraint to protect —
-- dropped outright rather than replaced.

alter table public.collections
  drop constraint collections_single_source;
