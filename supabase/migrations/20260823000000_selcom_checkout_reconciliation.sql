-- Selcom Checkout webhook/order-status reconciliation (Push STK/USSD,
-- create-order-minimal -> wallet-payment). Adds fields resolve_collection()
-- already knows how to consume once mapped to a CollectionResult, plus
-- audit columns Selcom's real payload/response carry that
-- app/services/wallet_push.py's earlier columns didn't yet need:
--
--   channel                 -- Selcom's own reported channel (e.g. telco/PSP)
--   provider_payment_status -- Selcom's own payment_status string
--                              (PENDING/COMPLETED/CANCELLED/USERCANCELLED/
--                              REJECTED/INPROGRESS) — distinct from this
--                              app's own aggregate `status`, kept verbatim
--                              for audit/support.

alter table public.collections
  add column channel text,
  add column provider_payment_status text;

comment on column public.collections.channel is
  'Selcom''s own reported channel for this attempt (from the webhook/order-status response) — distinct from method, which is this app''s own label.';
comment on column public.collections.provider_payment_status is
  'Selcom''s own payment_status verbatim (PENDING/COMPLETED/CANCELLED/USERCANCELLED/REJECTED/INPROGRESS) — the authoritative completion signal per the credit rule, kept alongside the mapped internal status for audit.';

-- notify_merchant()'s new "payment_received" notification (a completed
-- Selcom Checkout collection) needs a matching CHECK constraint entry,
-- same pattern as every prior notification-type addition this project —
-- see app/schemas/enums.py::NotificationType's docstring for why this is
-- always a real migration, never a bare string literal.
alter table public.notifications
  drop constraint notifications_notification_type_check;

alter table public.notifications
  add constraint notifications_notification_type_check check (notification_type in (
    'fraud_alert', 'document_request', 'dispute_received', 'refund_requested', 'dispute_status_updated',
    'withdrawal_failed', 'withdrawal_reversed', 'withdrawal_info_requested', 'withdrawal_rejected',
    'withdrawal_success', 'payment_received'
  ));
