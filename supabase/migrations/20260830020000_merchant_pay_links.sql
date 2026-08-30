-- Pay by Link: a permanent, merchant-chosen public checkout URL
-- (https://infinityafrica.net/pay/{merchant_slug}), distinct from the
-- existing payment_links table's short-lived generated/shareable links
-- (random public_slug, fixed amount set by the merchant). This table
-- only holds the permanent page's own identity (slug, display name,
-- active/disabled) — a customer submission against it creates an
-- ordinary payment_links row (see app/services/pay_by_link.py), so every
-- existing collection/reconciliation/receipt safety guarantee applies
-- unchanged; nothing here ever touches money.

create table public.merchant_pay_links (
  id uuid primary key default gen_random_uuid(),

  -- One permanent Pay by Link page per merchant (Part 4 of the feature
  -- brief: "create ... if they do not have one" / "view their permanent
  -- Pay by Link", both singular). Revisit with a real multi-page design
  -- if merchants ever need more than one.
  merchant_id uuid not null unique references public.merchants (id) on delete cascade,

  slug text not null,
  display_name text not null,
  description text,
  is_active boolean not null default true,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid references auth.users (id) on delete set null,
  last_used_at timestamptz,

  constraint merchant_pay_links_slug_format check (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' and length(slug) between 3 and 60)
);

comment on table public.merchant_pay_links is
  'A merchant''s permanent public "Pay by Link" page (/pay/{slug}) — a standing storefront-style checkout URL, distinct from payment_links'' one-off generated/shareable links. A customer submission here creates a fresh payment_links row (app/services/pay_by_link.py) and reuses every existing collection/reconciliation/receipt path unchanged.';
comment on column public.merchant_pay_links.slug is
  'The public URL segment: /pay/{slug}. Lowercase letters, digits, and single hyphens only; reserved words (admin, api, ...) are rejected in application code (app/services/pay_by_link.py::RESERVED_SLUGS), not here, since that list may grow. Uniqueness against both this table and payment_links.public_slug is enforced in application code at create/update time (see is_slug_available) — a unique index alone can''t span two tables.';
comment on column public.merchant_pay_links.is_active is
  'Merchant-controlled kill switch for this one page — a disabled page''s public URL shows "unavailable" instead of the checkout form. Independent of app.core.feature_flags.ENABLE_COLLECTIONS (the platform-wide switch).';
comment on column public.merchant_pay_links.last_used_at is
  'Set each time a customer successfully submits the checkout form on this page (not on a successful payment specifically — see execute_pay_by_link_checkout) — lets a merchant/Super Admin see whether a page is actually getting used.';

create unique index merchant_pay_links_slug_key on public.merchant_pay_links (lower(slug));
create index merchant_pay_links_is_active_idx on public.merchant_pay_links (is_active);

create trigger merchant_pay_links_set_updated_at
  before update on public.merchant_pay_links
  for each row execute function public.set_updated_at();

alter table public.merchant_pay_links enable row level security;

-- Planned shape (see payment_links' own RLS comment above for why this is
-- documented rather than active yet — every access today goes through
-- the service-role backend, which enforces the same scoping in
-- application code):
--   create policy "merchant staff can manage their own pay-by-link page"
--     on public.merchant_pay_links for all
--     using (merchant_id in (select merchant_id from public.merchant_users where user_id = auth.uid()));
--   create policy "anyone can view an active pay-by-link page"
--     on public.merchant_pay_links for select
--     using (is_active = true);

-- A payment_links row created from a Pay by Link checkout submission is
-- otherwise an entirely ordinary payment link (fixed amount, customer
-- details, the usual "Choose how you want to pay" flow) — created_via
-- just needs a new label so app/services/collection_source.py can
-- resolve the eventual collection's source to PAY_BY_LINK instead of
-- falling through to the generic PAYMENT_LINK value.
alter table public.payment_links
  drop constraint payment_links_created_via_check;
alter table public.payment_links
  add constraint payment_links_created_via_check
    check (created_via in ('payment_link', 'request_collection', 'api', 'pay_by_link'));

alter table public.collections
  drop constraint collections_source_check;
alter table public.collections
  add constraint collections_source_check check (source in (
    'DASHBOARD_REQUEST', 'PAYMENT_LINK', 'INVOICE',
    'API_PAYMENT_PAGE', 'API_WALLET_PUSH', 'API_SELCOM_PESA', 'API_TANQR',
    'PAY_BY_LINK'
  ));
