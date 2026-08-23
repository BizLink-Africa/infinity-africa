-- Fix for a live incident (2026-08-23): a wallet-push collection was
-- credited to the merchant wallet as "successful", then Selcom actually
-- reversed the underlying M-Pesa payment ("Payment unsuccessful. You are
-- trying to pay into your own till") — but nothing in this codebase could
-- ever act on that later signal, because resolve_collection() treats any
-- collection whose status isn't still 'processing' as already resolved
-- and no-ops. See app/services/collections.py::reverse_successful_collection()
-- (new) and app/services/checkout_reconciliation.py's updated
-- complete_checkout_collection_once() for the fix this migration supports.
--
-- Two smallest-safe additions:
--   1. collections.status gains 'pending_review' — a pre-credit hold used
--      when a collection would otherwise be marked successful but the
--      payer phone matches the merchant's own phone (self-payment/
--      "own till" risk, app/services/fraud_monitoring_service.py's new
--      SELF_PAYMENT_OWN_TILL rule). 'reversed' already existed in this
--      constraint (it was simply never reachable from application code
--      until now) and needs no migration.
--   2. notifications.notification_type gains 'collection_reversed' and
--      'collection_pending_review' — same pattern as every prior
--      notification-type addition (see app/schemas/enums.py::
--      NotificationType's docstring).

alter table public.collections
  drop constraint collections_status_check;

alter table public.collections
  add constraint collections_status_check
  check (status in ('pending', 'processing', 'successful', 'failed', 'reversed', 'cancelled', 'pending_review'));

alter table public.notifications
  drop constraint notifications_notification_type_check;

alter table public.notifications
  add constraint notifications_notification_type_check check (notification_type in (
    'fraud_alert', 'document_request', 'dispute_received', 'refund_requested', 'dispute_status_updated',
    'withdrawal_failed', 'withdrawal_reversed', 'withdrawal_info_requested', 'withdrawal_rejected',
    'withdrawal_success', 'payment_received', 'collection_reversed', 'collection_pending_review'
  ));

-- New fraud rule: flags (never silently blocks) a collection whose payer
-- phone matches the merchant's own contact_phone — exactly the "trying to
-- pay into your own till" pattern from the live incident. Data-only
-- addition, same convention as the six rules seeded in
-- 20260817090000_fraud_monitoring.sql; rule_code has no CHECK constraint.
insert into public.fraud_rules (rule_code, label, description, config) values
  ('SELF_PAYMENT_OWN_TILL', 'Self-payment / own-till risk',
   'The customer phone number for this collection matches the merchant''s own registered contact phone — a self-payment pattern Selcom itself may reject or reverse after the fact. Held for review before funds become available.',
   '{}'::jsonb);
