"""app.schemas.enums.WebhookEvent vs. the real database constraint.

Same gap and same fix pattern as test_notification_types.py: FakeSupabaseClient
doesn't enforce Postgres CHECK constraints, so a webhook event_name not in
the real constraint only fails against the live database. This already
happened once — app/services/collections.py called enqueue_webhook_event()
with event_name='collection.reversed' and 'collection.pending_review'
during the 2026-08-23 reversal-protection work, neither of which was in
the constraint at the time (fixed by
supabase/migrations/20260824010000_webhook_events_reversal_names.sql).
enqueue_webhook_event() has no error handling around its insert — for any
merchant with webhook_url configured, that crashed the whole request
instead of just failing to enqueue a notification.

Process rule: before adding any new WebhookEvent member, grep the current
`webhook_events_event_name_check` constraint (currently
20260824010000_webhook_events_reversal_names.sql has the authoritative
list), extend it via a real migration, and update this mirror in the same
change.
"""

from app.schemas.enums import WebhookEvent

# Mirrors supabase/migrations/20260824010000_webhook_events_reversal_names.sql's
# `webhook_events_event_name_check` constraint exactly.
_CURRENT_DATABASE_CONSTRAINT_VALUES = {
    "collection.pending",
    "collection.processing",
    "collection.success",
    "collection.failed",
    "collection.cancelled",
    "collection.reversed",
    "collection.pending_review",
    "disbursement.success",
    "disbursement.failed",
    "disbursement.reversed",
    "invoice.paid",
    "invoice.overdue",
    "payment_link.created",
    "payment_link.paid",
    "payment_link.expired",
    "payment_link.payment_reversed",
    "refund.succeeded",
    "refund.failed",
    "chargeback.opened",
    "chargeback.resolved",
}


def test_webhook_event_enum_matches_database_constraint():
    enum_values = {member.value for member in WebhookEvent}
    assert enum_values == _CURRENT_DATABASE_CONSTRAINT_VALUES
