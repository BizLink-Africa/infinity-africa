-- merchant_collection_pricing_rules: dynamic, per-merchant COLLECTION fee
-- configuration — the collection-side counterpart to merchant_pricing_rules
-- (which, as of the 2026-08-31 "fees apply to collections only" policy
-- change, no longer charges anything; see docs/collection-and-withdrawal-pricing.md).
-- A deliberately separate table, not a repurposing of merchant_pricing_rules:
-- that table's `channel`/`destination_code` columns are typed around
-- DisbursementMethod/DestinationCode (withdrawal payout channels/banks),
-- which don't apply to collections at all — collections have no
-- "destination", and their `channel` concept is CollectionMethod (how the
-- customer paid), a different vocabulary entirely. See
-- app/services/collections/pricing.py for the precedence lookup and
-- docs/collection-and-withdrawal-pricing.md for the full model.
--
-- Same shape/precedence convention as merchant_pricing_rules
-- (supabase/migrations/20260820090000_merchant_pricing_rules.sql) minus
-- destination_code (no destination concept for collections) and
-- processor_fee_flat/processor_fee_pass_through (no processor-charge-
-- pass-through concept requested for collections) — plus a free-text
-- `notes` column for a commercial-agreement reference, which collection
-- pricing asked for and withdrawal pricing never had.

create table public.merchant_collection_pricing_rules (
  id uuid primary key default gen_random_uuid(),

  -- null = platform fallback rule, applies when no merchant-specific rule matches.
  merchant_id uuid references public.merchants (id) on delete cascade,

  -- null = applies to every collection method (a merchant-default or
  -- platform-wide rule). Values mirror app/schemas/enums.py::CollectionMethod
  -- — the actual "how the customer paid" column (collections.method), not
  -- CollectionSource ("which product surface initiated it": Payment
  -- Links/Pay by Link/Invoices/API collections already all funnel through
  -- the same HOSTED_CHECKOUT method today, so they naturally share one
  -- rate unless a merchant is given a HOSTED_CHECKOUT-specific override).
  channel text check (channel in (
    'USSD_PUSH', 'STK_PUSH', 'SELCOM_PESA_PUSH', 'DYNAMIC_QR', 'HOSTED_CHECKOUT'
  )),

  percentage_fee numeric(6, 3) not null default 0 check (percentage_fee >= 0 and percentage_fee <= 100),
  flat_fee numeric(14, 2) not null default 0 check (flat_fee >= 0),
  minimum_fee numeric(14, 2) check (minimum_fee >= 0),
  maximum_fee numeric(14, 2) check (maximum_fee >= 0),

  effective_from timestamptz not null default now(),
  effective_to timestamptz,
  is_active boolean not null default true,

  label text,
  -- Free-text commercial-agreement reference ("negotiated separately with
  -- each merchant/customer") — e.g. a contract ID or a one-line summary of
  -- the negotiated terms. Never shown to the merchant; Super Admin only.
  notes text,

  created_by uuid references auth.users (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint merchant_collection_pricing_rules_fee_range
    check (maximum_fee is null or minimum_fee is null or maximum_fee >= minimum_fee),
  constraint merchant_collection_pricing_rules_effective_range
    check (effective_to is null or effective_to > effective_from)
);

comment on table public.merchant_collection_pricing_rules is
  'Dynamic COLLECTION fee rules (2026-08-31 policy: fees apply to collections only). merchant_id null = platform fallback. Precedence (most to least specific): merchant+channel -> merchant default -> platform+channel -> platform default -> settings.platform_fee_percentage (ultimate flat fallback, unchanged pre-existing behavior). See app/services/collections/pricing.py.';
comment on column public.merchant_collection_pricing_rules.minimum_fee is
  'Fee (percentage_fee applied + flat_fee) is clamped to this floor when set.';
comment on column public.merchant_collection_pricing_rules.maximum_fee is
  'Fee (percentage_fee applied + flat_fee) is clamped to this ceiling when set.';
comment on column public.merchant_collection_pricing_rules.notes is
  'Free-text commercial-agreement reference — Super Admin only, never shown to the merchant.';

create index merchant_collection_pricing_rules_merchant_id_idx on public.merchant_collection_pricing_rules (merchant_id);
create index merchant_collection_pricing_rules_channel_idx on public.merchant_collection_pricing_rules (channel);
create index merchant_collection_pricing_rules_is_active_idx on public.merchant_collection_pricing_rules (is_active) where is_active;

create trigger merchant_collection_pricing_rules_set_updated_at
  before update on public.merchant_collection_pricing_rules
  for each row execute function public.set_updated_at();

alter table public.merchant_collection_pricing_rules enable row level security;

create policy "merchant members can view their own collection pricing rules"
  on public.merchant_collection_pricing_rules for select
  using (merchant_id is not null and public.current_user_has_merchant_access(merchant_id));

create policy "super admins can view all collection pricing rules"
  on public.merchant_collection_pricing_rules for select
  using ((select public.current_user_is_super_admin()));

-- No insert/update/delete policy: created/edited/deactivated via apps/api
-- (service_role) only, same convention as merchant_pricing_rules.
