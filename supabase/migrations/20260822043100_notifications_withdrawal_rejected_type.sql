-- notify_merchant's new "withdrawal_rejected" notification (Super Admin
-- rejects a withdrawal — see app/services/disbursements.py::reject_disbursement)
-- needs a matching CHECK constraint entry, same pattern as
-- 20260818090000/20260820090001's additions.
alter table public.notifications
  drop constraint notifications_notification_type_check;

alter table public.notifications
  add constraint notifications_notification_type_check check (notification_type in (
    'fraud_alert', 'document_request', 'dispute_received', 'refund_requested', 'dispute_status_updated',
    'withdrawal_failed', 'withdrawal_reversed', 'withdrawal_info_requested', 'withdrawal_rejected'
  ));
