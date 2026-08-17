-- Withdrawal fee snapshot + expanded Super Admin approval status vocabulary.
-- Additive ALTER on the existing disbursements table (never editing
-- 20260814090010_disbursements.sql in place) plus a status-vocabulary
-- change, following 20260814140000_disbursement_status.sql's exact
-- backfill-then-swap-constraint shape.
--
-- Business rule change: every withdrawal now requires Super Admin approval
-- (no more amount-based auto-processing), and each merchant has its own
-- negotiated fee (see merchant_pricing_rules, previous migration). The fee
-- actually charged is calculated once, at request time, and frozen onto
-- this row (total_charges/total_reserved_amount/pricing_snapshot_json) so a
-- later pricing-rule edit never rewrites an already-submitted withdrawal.

alter table public.disbursements
  add column processor_charge numeric(14, 2) not null default 0,
  add column infinity_fee numeric(14, 2) not null default 0,
  add column percentage_fee_component numeric(14, 2) not null default 0,
  add column flat_fee_component numeric(14, 2) not null default 0,
  add column total_charges numeric(14, 2) not null default 0,
  add column total_reserved_amount numeric(14, 2),
  add column recipient_net_amount numeric(14, 2),
  add column pricing_rule_id uuid references public.merchant_pricing_rules (id) on delete set null,
  add column pricing_snapshot_json jsonb not null default '{}'::jsonb,
  add column destination_code text,
  add column rejected_by uuid references auth.users (id) on delete set null,
  add column rejected_at timestamptz,
  add column rejection_reason text,
  add column admin_status_reason text,
  add column selcom_trans_id text,
  add column selcom_receipt text,
  add column selcom_status text;

comment on column public.disbursements.total_reserved_amount is
  'Amount actually debited from the merchant wallet: withdrawal amount + total_charges. Backfilled to amount for pre-existing rows (no fee charged before this migration).';
comment on column public.disbursements.recipient_net_amount is
  'What the recipient actually receives — equal to amount; kept as its own column so the response/snapshot never has to re-derive it.';
comment on column public.disbursements.pricing_snapshot_json is
  'The full fee breakdown (see FeeBreakdown) as calculated at request time — the source of truth for what was actually charged, independent of any later merchant_pricing_rules edit.';
comment on column public.disbursements.rejection_reason is
  'Required by app/services/disbursements.py::reject_disbursement — a Super Admin must state why.';
comment on column public.disbursements.admin_status_reason is
  'Free-text note attached by a Super Admin action that is not a terminal approve/reject, e.g. a "request more information" message the merchant sees.';
comment on column public.disbursements.selcom_trans_id is
  'Selcom''s own transaction identifier for this payout, distinct from provider_reference (Infinity Africa''s idempotency reference sent to Selcom) — populated once Super Admin approval calls Selcom.';

update public.disbursements set total_reserved_amount = amount where total_reserved_amount is null;
update public.disbursements set recipient_net_amount = amount where recipient_net_amount is null;

-- Status vocabulary: PENDING -> PENDING_ADMIN_APPROVAL (every withdrawal
-- now sits here, not only ones above a threshold); REJECTED introduced as
-- distinct from FAILED (an admin's deliberate rejection vs. a provider
-- failure); new post-approval outcomes for Selcom's async/ambiguous/
-- IP-whitelist responses.
update public.disbursements set status = 'PENDING_ADMIN_APPROVAL' where status = 'PENDING';

alter table public.disbursements
  alter column status drop default;

alter table public.disbursements
  drop constraint disbursements_status_check;

alter table public.disbursements
  add constraint disbursements_status_check
  check (status in (
    'PENDING_ADMIN_APPROVAL', 'INFO_REQUESTED', 'PROCESSING', 'SUCCESS',
    'FAILED', 'REJECTED', 'NEEDS_ADMIN_ATTENTION', 'NEEDS_RECONCILIATION',
    'BLOCKED_IP_WHITELIST', 'REVERSED'
  ));

alter table public.disbursements
  alter column status set default 'PENDING_ADMIN_APPROVAL';

-- notify_merchant's new "withdrawal_info_requested" notification (Super
-- Admin requests more information before approving) needs a matching
-- CHECK constraint entry, same pattern as 20260818090000's additions.
alter table public.notifications
  drop constraint notifications_notification_type_check;

alter table public.notifications
  add constraint notifications_notification_type_check check (notification_type in (
    'fraud_alert', 'document_request', 'dispute_received', 'refund_requested', 'dispute_status_updated',
    'withdrawal_failed', 'withdrawal_reversed', 'withdrawal_info_requested'
  ));
