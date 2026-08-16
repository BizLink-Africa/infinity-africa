-- Rename webhook_events.event_name values to match the renamed WebhookEvent
-- enum in packages/shared/src/webhook-events.ts / apps/api/app/schemas/enums.py:
-- payment.succeeded/failed/pending -> collection.success/failed/pending,
-- disbursement.succeeded -> disbursement.success, plus a new payment_link.paid.

alter table public.webhook_events
  drop constraint webhook_events_event_name_check;

alter table public.webhook_events
  add constraint webhook_events_event_name_check check (event_name in (
    'collection.pending', 'collection.success', 'collection.failed',
    'disbursement.success', 'disbursement.failed',
    'invoice.paid', 'invoice.overdue',
    'payment_link.created', 'payment_link.paid', 'payment_link.expired',
    'refund.succeeded', 'refund.failed',
    'chargeback.opened', 'chargeback.resolved'
  ));
