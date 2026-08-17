-- merchant_pricing_rules: dynamic, per-merchant withdrawal fee configuration.
-- Replaces the single global settings.disbursement_approval_threshold-style
-- "one rate for everyone" model with negotiated rules per merchant, with an
-- optional channel/destination-specific override and a platform-wide
-- fallback (merchant_id null) for merchants with no rule of their own yet.
-- See app/services/withdrawals/fee_calculator.py for the precedence lookup
-- and docs/withdrawal-pricing-and-approval.md for the full model.
--
-- Deliberately no fee_type/rule_type discriminator column: percentage_fee,
-- flat_fee, minimum_fee, and maximum_fee already compose (a rule can carry
-- any combination) without needing a type tag.

create table public.merchant_pricing_rules (
  id uuid primary key default gen_random_uuid(),

  -- null = platform fallback rule, applies when no merchant-specific rule matches.
  merchant_id uuid references public.merchants (id) on delete cascade,

  -- null = applies to every channel (a merchant-default or platform-wide rule).
  channel text check (channel in ('SELCOM_PESA', 'MOBILE_MONEY', 'BANK_ACCOUNT')),

  -- null = applies to every destination within `channel` (or every
  -- destination outright, if channel is also null).
  destination_code text check (destination_code in (
    'SELCOM', 'MPESA', 'AIRTELMONEY', 'HALOPESA', 'MIXXBYYAS', 'TTCLPESA',
    'CRDB', 'NMB', 'NBC', 'ABSA', 'BOA', 'DTB', 'EQUITY', 'EXIM', 'KCB',
    'STANBIC', 'SCB', 'TCB'
  )),

  percentage_fee numeric(6, 3) not null default 0 check (percentage_fee >= 0),
  flat_fee numeric(14, 2) not null default 0 check (flat_fee >= 0),
  minimum_fee numeric(14, 2) check (minimum_fee >= 0),
  maximum_fee numeric(14, 2) check (maximum_fee >= 0),

  -- A flat, admin-configured pass-through amount — Selcom's integration in
  -- this codebase never returns a live processor fee to quote against (see
  -- app/services/selcom/schemas.py's DisbursementResult), so this is set by
  -- whoever negotiates the merchant's rate, not fetched at request time.
  processor_fee_flat numeric(14, 2) not null default 0 check (processor_fee_flat >= 0),
  processor_fee_pass_through boolean not null default false,

  effective_from timestamptz not null default now(),
  effective_to timestamptz,
  is_active boolean not null default true,

  label text,

  created_by uuid references auth.users (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint merchant_pricing_rules_fee_range
    check (maximum_fee is null or minimum_fee is null or maximum_fee >= minimum_fee),
  constraint merchant_pricing_rules_effective_range
    check (effective_to is null or effective_to > effective_from)
);

comment on table public.merchant_pricing_rules is
  'Dynamic withdrawal fee rules. merchant_id null = platform fallback. Precedence (most to least specific): merchant+destination -> merchant+channel -> merchant default -> platform fallback. See app/services/withdrawals/fee_calculator.py.';
comment on column public.merchant_pricing_rules.processor_fee_flat is
  'Admin-configured pass-through processor charge amount, added to total_charges only when processor_fee_pass_through is true.';
comment on column public.merchant_pricing_rules.minimum_fee is
  'Infinity fee (percentage_fee + flat_fee) is clamped to this floor when set.';
comment on column public.merchant_pricing_rules.maximum_fee is
  'Infinity fee (percentage_fee + flat_fee) is clamped to this ceiling when set.';

create index merchant_pricing_rules_merchant_id_idx on public.merchant_pricing_rules (merchant_id);
create index merchant_pricing_rules_channel_idx on public.merchant_pricing_rules (channel);
create index merchant_pricing_rules_destination_code_idx on public.merchant_pricing_rules (destination_code);
create index merchant_pricing_rules_is_active_idx on public.merchant_pricing_rules (is_active) where is_active;

create trigger merchant_pricing_rules_set_updated_at
  before update on public.merchant_pricing_rules
  for each row execute function public.set_updated_at();

alter table public.merchant_pricing_rules enable row level security;

create policy "merchant members can view their own pricing rules"
  on public.merchant_pricing_rules for select
  using (merchant_id is not null and public.current_user_has_merchant_access(merchant_id));

create policy "super admins can view all pricing rules"
  on public.merchant_pricing_rules for select
  using ((select public.current_user_is_super_admin()));

-- No insert/update/delete policy: created/edited/deactivated via apps/api
-- (service_role) only, same convention as merchants/onboarding_submissions.
