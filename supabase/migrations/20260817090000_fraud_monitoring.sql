-- Fraud/risk monitoring: configurable rules, the alerts they raise, an
-- append-only event trail per alert (status changes, notes), and a cheap
-- "is this transaction currently flagged" lookup (transaction_reviews)
-- separate from the possibly-many fraud_alerts rows a transaction can
-- accumulate over time. See app/services/fraud_monitoring_service.py for
-- the rule implementations and app/routers/admin_risk.py /
-- app/routers/merchant_portal.py for how alerts are reviewed.

create table public.fraud_rules (
  id uuid primary key default gen_random_uuid(),

  rule_code text not null unique,
  label text not null,
  description text,
  enabled boolean not null default true,
  config jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.fraud_rules is
  'Configurable thresholds for each fraud rule (e.g. HIGH_VALUE_TRANSACTION.config.threshold_amount) — tuning a rule is a data change, not a redeploy.';

create trigger fraud_rules_set_updated_at
  before update on public.fraud_rules
  for each row execute function public.set_updated_at();

alter table public.fraud_rules enable row level security;

create policy "super admins can view fraud rules"
  on public.fraud_rules for select
  using ((select public.current_user_is_super_admin()));

-- No insert/update/delete policy: managed via apps/api (service_role) only.

insert into public.fraud_rules (rule_code, label, description, config) values
  ('SAME_PHONE_SAME_AMOUNT_SECONDS', 'Same phone, same amount, within seconds',
   'Same customer phone pays the same amount multiple times within a short window.',
   '{"window_seconds": 30}'::jsonb),
  ('SAME_PHONE_TOO_MANY_ATTEMPTS', 'Too many attempts from one phone',
   'Same customer phone makes an unusually high number of payment attempts in a short window.',
   '{"window_minutes": 10, "max_attempts": 5}'::jsonb),
  ('DUPLICATE_REFERENCE', 'Duplicate reference',
   'A merchant or provider reference was reused across separate collections.',
   '{}'::jsonb),
  ('PAYMENT_AFTER_LINK_EXPIRY', 'Payment attempted after link expiry',
   'A collection against a payment link resolved after that link had already expired.',
   '{}'::jsonb),
  ('HIGH_VALUE_TRANSACTION', 'High-value transaction',
   'A single transaction exceeded the configured platform threshold.',
   '{"threshold_amount": 5000000}'::jsonb),
  ('HIGH_CHARGEBACK_MERCHANT', 'Merchant with high dispute rate',
   'A merchant has an unusually high rate of disputes/chargebacks relative to their successful collections.',
   '{"window_days": 30, "max_dispute_count": 3, "max_dispute_ratio": 0.05}'::jsonb);

-- ----------------------------------------------------------------------------

create table public.fraud_alerts (
  id uuid primary key default gen_random_uuid(),

  merchant_id uuid not null references public.merchants (id) on delete cascade,
  transaction_id uuid references public.transactions (id) on delete set null,

  customer_phone text,
  rule_code text not null,
  risk_level text not null check (risk_level in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
  reason text not null,

  status text not null default 'OPEN'
    check (status in ('OPEN', 'UNDER_REVIEW', 'DOCUMENTS_REQUESTED', 'CLEARED', 'ESCALATED', 'CLOSED')),

  metadata jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.fraud_alerts is
  'A single suspicious-activity finding raised by the fraud rules engine, tracked through merchant/admin review. Wording shown to merchants is deliberately neutral ("suspicious activity detected", "requires review") — see app/services/fraud_monitoring_service.py.';

create index fraud_alerts_merchant_id_idx on public.fraud_alerts (merchant_id);
create index fraud_alerts_transaction_id_idx on public.fraud_alerts (transaction_id);
create index fraud_alerts_status_idx on public.fraud_alerts (status);
create index fraud_alerts_customer_phone_idx on public.fraud_alerts (customer_phone);

create trigger fraud_alerts_set_updated_at
  before update on public.fraud_alerts
  for each row execute function public.set_updated_at();

alter table public.fraud_alerts enable row level security;

create policy "merchant members can view their own fraud alerts"
  on public.fraud_alerts for select
  using (public.current_user_has_merchant_access(merchant_id));

create policy "super admins can view all fraud alerts"
  on public.fraud_alerts for select
  using ((select public.current_user_is_super_admin()));

-- No insert/update/delete policy: written via apps/api (service_role) only.

-- ----------------------------------------------------------------------------

create table public.fraud_alert_events (
  id uuid primary key default gen_random_uuid(),
  alert_id uuid not null references public.fraud_alerts (id) on delete cascade,

  actor_id uuid references auth.users (id) on delete set null,
  actor_type text not null default 'system' check (actor_type in ('system', 'user')),

  action text not null,
  from_status text,
  to_status text,
  note text,

  created_at timestamptz not null default now()
  -- No updated_at: append-only, same as audit_logs.
);

comment on table public.fraud_alert_events is
  'Append-only history of status changes and notes on a fraud alert. actor_id null = system-generated (the rule that raised it).';

create index fraud_alert_events_alert_id_idx on public.fraud_alert_events (alert_id);

create trigger fraud_alert_events_immutable
  before update or delete on public.fraud_alert_events
  for each row execute function public.forbid_mutation();

alter table public.fraud_alert_events enable row level security;

create policy "super admins can view fraud alert events"
  on public.fraud_alert_events for select
  using ((select public.current_user_is_super_admin()));

-- No insert/update/delete policy: written via apps/api (service_role) only.

-- ----------------------------------------------------------------------------

create table public.transaction_reviews (
  id uuid primary key default gen_random_uuid(),
  transaction_id uuid not null unique references public.transactions (id) on delete cascade,
  merchant_id uuid not null references public.merchants (id) on delete cascade,

  status text not null default 'UNDER_REVIEW' check (status in ('UNDER_REVIEW', 'CLEARED')),
  latest_alert_id uuid references public.fraud_alerts (id) on delete set null,

  opened_at timestamptz not null default now(),
  cleared_at timestamptz,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.transaction_reviews is
  'One row per flagged transaction — a cheap "is this transaction under review" lookup (used for the Merchant Portal transaction banner) without joining every fraud_alerts row.';

create index transaction_reviews_merchant_id_idx on public.transaction_reviews (merchant_id);
create index transaction_reviews_status_idx on public.transaction_reviews (status);

create trigger transaction_reviews_set_updated_at
  before update on public.transaction_reviews
  for each row execute function public.set_updated_at();

alter table public.transaction_reviews enable row level security;

create policy "merchant members can view their own transaction reviews"
  on public.transaction_reviews for select
  using (public.current_user_has_merchant_access(merchant_id));

create policy "super admins can view all transaction reviews"
  on public.transaction_reviews for select
  using ((select public.current_user_is_super_admin()));

-- No insert/update/delete policy: written via apps/api (service_role) only.
