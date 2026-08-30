-- merchant_notification_settings: where a merchant wants collection
-- transaction notifications emailed (feature brief "Add merchant
-- collection notification email settings"). One row per merchant
-- (merchant_id unique) — the Merchant Portal Notification Settings card
-- and the Super Admin Notification Details view both read/write this
-- same row. See app/services/merchant_notifications.py.
--
-- Deliberately the fixed two-column shape from the brief (primary/
-- secondary), not a normalized recipient table: the brief explicitly
-- offered either, and MVP only ever needs "up to 2 emails" — a third
-- column would need a real schema change anyway, so there's no
-- flexibility lost by not building a list-shaped table now.
--
-- Distinct from a customer's payment receipt (payment_links.customer_email
-- / invoices.customer_email / collections.metadata.customer_email, sent by
-- send_payment_receipt_email) — this is who the MERCHANT wants notified
-- when a collection is credited, sent by
-- send_merchant_collection_notification_email.

create table public.merchant_notification_settings (
  id uuid primary key default gen_random_uuid(),

  merchant_id uuid not null unique references public.merchants (id) on delete cascade,

  primary_notification_email text,
  secondary_notification_email text,
  collection_notifications_enabled boolean not null default true,

  updated_by uuid references auth.users (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  -- Defense in depth alongside the app-layer validation in
  -- app/services/merchant_notifications.py (which owns the actual user-
  -- facing error messages) — a direct duplicate insert should never be
  -- possible even if some future call site forgets to validate first.
  constraint merchant_notification_settings_no_duplicate_emails
    check (
      primary_notification_email is null
      or secondary_notification_email is null
      or lower(primary_notification_email) <> lower(secondary_notification_email)
    )
);

comment on table public.merchant_notification_settings is
  'Up to 2 email addresses a merchant wants notified when a collection is successfully confirmed and credited. Distinct from the customer-facing payment receipt email — see app/services/email.py::send_merchant_collection_notification_email.';
comment on column public.merchant_notification_settings.collection_notifications_enabled is
  'When false, no collection notification email is sent regardless of whether an email is configured. Emails may be left in place while disabled.';

create trigger merchant_notification_settings_set_updated_at
  before update on public.merchant_notification_settings
  for each row execute function public.set_updated_at();

alter table public.merchant_notification_settings enable row level security;

create policy "merchant members can view their own notification settings"
  on public.merchant_notification_settings for select
  using (public.current_user_has_merchant_access(merchant_id));

create policy "super admins can view all notification settings"
  on public.merchant_notification_settings for select
  using ((select public.current_user_is_super_admin()));

-- No insert/update/delete policy: written via apps/api (service_role) only
-- — both the merchant's own PUT /v1/merchant/notification-settings and
-- Super Admin's PUT /v1/admin/merchants/{id}/notification-settings enforce
-- their own authorization in Python, same convention as
-- merchant_collection_pricing_rules and api_ip_allowlist.
