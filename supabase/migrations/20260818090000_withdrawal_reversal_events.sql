-- Selcom withdrawal integration: two additive CHECK constraint extensions
-- needed by app/services/disbursements.py::reverse_successful_disbursement_from_callback
-- and its notify_merchant()/enqueue_webhook_event() calls. Both constraints
-- previously rejected these values (the in-memory test fake doesn't
-- enforce CHECK constraints, so this only surfaces against the real DB).

alter table public.notifications
  drop constraint notifications_notification_type_check;

alter table public.notifications
  add constraint notifications_notification_type_check check (notification_type in (
    'fraud_alert', 'document_request', 'dispute_received', 'refund_requested', 'dispute_status_updated',
    'withdrawal_failed', 'withdrawal_reversed'
  ));

alter table public.webhook_events
  drop constraint webhook_events_event_name_check;

alter table public.webhook_events
  add constraint webhook_events_event_name_check check (event_name in (
    'collection.pending', 'collection.success', 'collection.failed',
    'disbursement.success', 'disbursement.failed', 'disbursement.reversed',
    'invoice.paid', 'invoice.overdue',
    'payment_link.created', 'payment_link.paid', 'payment_link.expired',
    'refund.succeeded', 'refund.failed',
    'chargeback.opened', 'chargeback.resolved'
  ));
