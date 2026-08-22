"""app.schemas.enums.NotificationType vs. the real database constraint.

FakeSupabaseClient (see tests/fakes.py) doesn't model Postgres CHECK
constraints at all — it would silently accept any string, including one
the real `notifications` table would reject. That gap let two real
production incidents through in one session: a value not in the CHECK
list crashed reject_disbursement, and (separately) a column that plain
didn't exist yet crashed approve_disbursement. This file can't reach the
live database either, so it does the next best thing: pins
NotificationType's members against a hardcoded mirror of the migration
list below. Whenever the real constraint changes
(supabase/migrations/*_notification*.sql — currently
20260823000000_selcom_checkout_reconciliation.sql has the
authoritative list), this test forces a deliberate edit to both the enum
and this mirror, rather than a code change quietly drifting from what the
database actually allows.

Process rule: before adding any new NotificationType member (or any other
enum-shaped string literal backed by a Postgres CHECK constraint), grep
the relevant migration file for its current `check (... in (...))` list,
extend it via a real migration applied to the database, and update this
kind of mirror test in the same change — not after production breaks.
"""

from app.schemas.enums import NotificationType

# Mirrors supabase/migrations/20260822171500_notifications_withdrawal_success_type.sql's
# `notifications_notification_type_check` constraint exactly. Update this
# set (and add a real migration) whenever NotificationType gains a member.
_CURRENT_DATABASE_CONSTRAINT_VALUES = {
    "fraud_alert",
    "document_request",
    "dispute_received",
    "refund_requested",
    "dispute_status_updated",
    "withdrawal_failed",
    "withdrawal_reversed",
    "withdrawal_info_requested",
    "withdrawal_rejected",
    "withdrawal_success",
    "payment_received",
}


def test_notification_type_enum_matches_database_constraint():
    enum_values = {member.value for member in NotificationType}
    assert enum_values == _CURRENT_DATABASE_CONSTRAINT_VALUES
