-- collections needs a slot for the merchant's own reference/order ID
-- (distinct from transactions.reference, which is Infinity's own canonical
-- reference) — the /v1/collections/{method} initiation endpoints accept and
-- validate this as an optional field.

alter table public.collections
  add column merchant_reference text;

comment on column public.collections.merchant_reference is
  'The merchant''s own reference for this collection (e.g. their order ID) — optional, set by the caller.';

create index collections_merchant_reference_idx
  on public.collections (merchant_id, merchant_reference) where merchant_reference is not null;
