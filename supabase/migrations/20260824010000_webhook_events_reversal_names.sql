-- Bug fix: app/services/collections.py already calls enqueue_webhook_event()
-- with event_name='collection.reversed' (reverse_successful_collection()),
-- event_name='collection.pending_review' (resolve_collection()'s
-- self-payment hold), and event_name='payment_link.payment_reversed'
-- (_apply_collection_reversal()) — all added in the 2026-08-23
-- reversal-protection work — but none of the three were ever added to
-- this constraint. enqueue_webhook_event() has no error handling around
-- its insert_row() call, so for any merchant with webhook_url configured,
-- hitting any of these paths would raise an unhandled CHECK-constraint
-- violation and crash the request instead of completing the reversal/
-- hold. Same class of bug as 20260818090000_withdrawal_reversal_events.sql
-- fixed for disbursements — the in-memory test fake doesn't enforce CHECK
-- constraints, so this only ever surfaces against the real database.
--
-- Also adds 'collection.processing' and 'collection.cancelled', requested
-- as part of the merchant developer-docs webhook event list — 'cancelled'
-- has no application code path emitting it yet (collections.status has
-- 'cancelled' as a valid value but nothing sets it today), kept reserved
-- for symmetry with the other terminal states, same convention already
-- used for 'invoice.overdue'/'payment_link.expired'/'refund.*'/'chargeback.*'.

alter table public.webhook_events
  drop constraint webhook_events_event_name_check;

alter table public.webhook_events
  add constraint webhook_events_event_name_check check (event_name in (
    'collection.pending', 'collection.processing', 'collection.success', 'collection.failed',
    'collection.cancelled', 'collection.reversed', 'collection.pending_review',
    'disbursement.success', 'disbursement.failed', 'disbursement.reversed',
    'invoice.paid', 'invoice.overdue',
    'payment_link.created', 'payment_link.paid', 'payment_link.expired', 'payment_link.payment_reversed',
    'refund.succeeded', 'refund.failed',
    'chargeback.opened', 'chargeback.resolved'
  ));
