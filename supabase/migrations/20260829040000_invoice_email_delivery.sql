-- Invoice email delivery (Resend): an invoice is only ever marked SENT
-- once the customer's payment-request email has actually gone out — see
-- app/routers/merchant_portal.py::send_my_invoice and
-- app/routers/invoices.py's equivalent. sent_at records exactly when that
-- happened (distinct from created_at/updated_at).
--
-- email_deliveries is intentionally generic (email_type, not an
-- invoice-specific table) — this is the first wired-up sender, but the
-- same log is meant to record every future transactional email (staff
-- invites, password resets, receipts, welcome emails) once those are
-- built, all from a single audit trail Super Admin can query.

alter table public.invoices
  add column sent_at timestamptz;

comment on column public.invoices.sent_at is
  'When the payment-request email actually went out — set only on a successful Resend delivery, never on a bare status change.';

create table public.email_deliveries (
  id uuid primary key default gen_random_uuid(),

  merchant_id uuid references public.merchants (id) on delete set null,

  -- e.g. 'invoice_payment_request' today; 'staff_invite', 'password_reset',
  -- 'payment_receipt', 'welcome', 'inquiry_notification' once those exist.
  email_type text not null,
  related_resource_type text,
  related_resource_id uuid,

  recipient_email text not null,
  sender_email text not null,
  subject text not null,

  provider text not null default 'resend',
  provider_message_id text,

  status text not null check (status in ('sent', 'failed')),
  error_message text,

  created_at timestamptz not null default now()
);

comment on table public.email_deliveries is
  'Audit log of every transactional email attempt (success or failure) — never stores the email body, only metadata safe for Super Admin review.';
comment on column public.email_deliveries.provider_message_id is
  'Resend''s own email id for a successful send — useful for support lookups, never a secret.';

create index email_deliveries_merchant_id_idx on public.email_deliveries (merchant_id);
create index email_deliveries_related_resource_idx on public.email_deliveries (related_resource_type, related_resource_id);
create index email_deliveries_status_idx on public.email_deliveries (status);

alter table public.email_deliveries enable row level security;

create policy "super admins can view all email deliveries"
  on public.email_deliveries for select
  using ((select public.current_user_is_super_admin()));

-- No insert/update/delete policy: written by apps/api (service_role) only.
