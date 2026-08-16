-- Basic notifications: no notification mechanism existed before this. One
-- row per notification, written by app/services/notifications_service.py at
-- each trigger point (fraud alert opened, documents requested, dispute
-- received, refund requested, dispute status updated). merchant_id is set
-- only for recipient_type = 'merchant'; platform-wide (admin) notifications
-- have recipient_type = 'admin' and merchant_id null.

create table public.notifications (
  id uuid primary key default gen_random_uuid(),

  recipient_type text not null check (recipient_type in ('merchant', 'admin')),
  merchant_id uuid references public.merchants (id) on delete cascade,

  notification_type text not null check (notification_type in (
    'fraud_alert', 'document_request', 'dispute_received', 'refund_requested', 'dispute_status_updated'
  )),
  title text not null,
  body text not null,

  related_resource_type text,
  related_resource_id uuid,

  is_read boolean not null default false,

  created_at timestamptz not null default now()
);

comment on table public.notifications is
  'In-app notifications for merchants and super admins — see app/services/notifications_service.py for the write side and GET /v1/merchant/notifications, GET /v1/admin/notifications for reads.';
comment on column public.notifications.merchant_id is
  'Set only when recipient_type = merchant; null for platform-wide admin notifications.';

create index notifications_merchant_id_idx on public.notifications (merchant_id);
create index notifications_recipient_type_idx on public.notifications (recipient_type);
create index notifications_is_read_idx on public.notifications (is_read);
create index notifications_created_at_idx on public.notifications (created_at);

alter table public.notifications enable row level security;

create policy "merchant members can view their own notifications"
  on public.notifications for select
  using (merchant_id is not null and public.current_user_has_merchant_access(merchant_id));

create policy "super admins can view all notifications"
  on public.notifications for select
  using ((select public.current_user_is_super_admin()));

-- No insert/update/delete policy: written via apps/api (service_role) only.
