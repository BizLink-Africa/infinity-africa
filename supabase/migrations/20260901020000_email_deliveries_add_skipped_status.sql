-- Adds 'skipped' to email_deliveries.status — needed by the merchant
-- collection notification email's idempotency guard (feature brief Part 5
-- / Part 6): when a recipient already has a "sent" delivery row for the
-- same collection, the retry (webhook redelivery, manual "Refresh status",
-- reconciliation sweep) writes a 'skipped' row instead of sending again,
-- so Super Admin's delivery history shows the retry was correctly
-- suppressed rather than silently doing nothing. See
-- app/services/email.py::send_merchant_collection_notification_email.

alter table public.email_deliveries
  drop constraint email_deliveries_status_check;

alter table public.email_deliveries
  add constraint email_deliveries_status_check
  check (status in ('sent', 'failed', 'skipped'));
