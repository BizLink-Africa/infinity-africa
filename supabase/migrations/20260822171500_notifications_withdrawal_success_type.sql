-- The successful-disbursement path (app/services/disbursements.py, both
-- the synchronous and the refresh-status-resolves-PROCESSING branches)
-- never called notify_merchant() at all — only failed/reversed/
-- info-requested/rejected withdrawals notified the merchant, so a
-- merchant's notification bell never showed a completed withdrawal.
-- Found while auditing the first real production pilot withdrawal.
alter table public.notifications
  drop constraint notifications_notification_type_check;

alter table public.notifications
  add constraint notifications_notification_type_check check (notification_type in (
    'fraud_alert', 'document_request', 'dispute_received', 'refund_requested', 'dispute_status_updated',
    'withdrawal_failed', 'withdrawal_reversed', 'withdrawal_info_requested', 'withdrawal_rejected',
    'withdrawal_success'
  ));
