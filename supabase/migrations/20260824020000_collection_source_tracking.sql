-- Payment source tracking: Super Admin needs to answer "which product
-- surface brought in this payment" (dashboard Request Collection,
-- Payment Links, Invoices, or one of the three API-key-authenticated
-- integration paths) independently of `method` (how the customer paid).
-- See app/schemas/enums.py::CollectionSource and
-- app/services/collection_source.py for how this is resolved server-side
-- — never trusted from client input.

alter table public.collections
  add column source text,
  add column api_key_id uuid references public.api_keys (id) on delete set null;

-- Backfill existing rows from what's already knowable about them, safely
-- and conservatively: a row with invoice_id set came via an invoice; one
-- with payment_link_id set came via a payment link; anything else
-- predates this column and is treated as a dashboard-initiated request
-- (the only other collection-creation path that existed historically).
update public.collections
  set source = case
    when invoice_id is not null then 'INVOICE'
    when payment_link_id is not null then 'PAYMENT_LINK'
    else 'DASHBOARD_REQUEST'
  end
  where source is null;

alter table public.collections
  alter column source set not null;

alter table public.collections
  add constraint collections_source_check check (source in (
    'DASHBOARD_REQUEST', 'PAYMENT_LINK', 'INVOICE',
    'API_PAYMENT_PAGE', 'API_WALLET_PUSH', 'API_SELCOM_PESA', 'API_TANQR'
  ));

create index collections_source_idx on public.collections (source);
create index collections_api_key_id_idx on public.collections (api_key_id);

comment on column public.collections.source is
  'Which product surface created this collection — see app/schemas/enums.py::CollectionSource. Independent of `method` (how the customer actually paid).';
comment on column public.collections.api_key_id is
  'The API key that created this collection, when created via an API-key-authenticated request. Null for dashboard/customer-facing-page-initiated collections.';

-- payment_links needs the same "which surface created this" distinction
-- — Merchant Portal's "Request Collection" and the public Payment Links
-- feature both create a payment_links row via the same backend endpoint
-- (POST /v1/merchant/payment-links), and POST /v1/collections (the
-- external developer API's "Infinity Payment Page" flow) creates one
-- too. A collection resolved against a payment_links row inherits its
-- created_via/api_key_id to decide the collection's own `source` (see
-- app/services/collection_source.py).
alter table public.payment_links
  add column created_via text not null default 'payment_link' check (created_via in ('payment_link', 'request_collection', 'api')),
  add column api_key_id uuid references public.api_keys (id) on delete set null;

create index payment_links_api_key_id_idx on public.payment_links (api_key_id);

comment on column public.payment_links.created_via is
  '''payment_link'' = merchant portal Payment Links page; ''request_collection'' = merchant portal Request Collection page (same underlying resource, different form); ''api'' = POST /v1/collections (external developer API).';
comment on column public.payment_links.api_key_id is
  'The API key that created this payment link, when created via POST /v1/collections. Null otherwise.';
