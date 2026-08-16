-- Merchant document requests: when a fraud alert (or an admin, independent
-- of one) needs supporting evidence from a merchant for a specific
-- transaction. document_request_files is one row per uploaded file, mirroring
-- onboarding_documents' shape, since a single request can ask for several
-- document kinds (receipt, proof of delivery, ...).

create table public.merchant_document_requests (
  id uuid primary key default gen_random_uuid(),

  merchant_id uuid not null references public.merchants (id) on delete cascade,
  transaction_id uuid references public.transactions (id) on delete set null,
  alert_id uuid references public.fraud_alerts (id) on delete set null,

  requested_documents text[] not null default '{}',
  reason text not null,

  status text not null default 'PENDING'
    check (status in ('PENDING', 'SUBMITTED', 'APPROVED', 'REJECTED')),

  due_date date,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.merchant_document_requests is
  'A request for a merchant to submit supporting evidence for a specific transaction — raised from a fraud alert or directly by a super admin.';

create index merchant_document_requests_merchant_id_idx on public.merchant_document_requests (merchant_id);
create index merchant_document_requests_status_idx on public.merchant_document_requests (status);

create trigger merchant_document_requests_set_updated_at
  before update on public.merchant_document_requests
  for each row execute function public.set_updated_at();

alter table public.merchant_document_requests enable row level security;

create policy "merchant members can view their own document requests"
  on public.merchant_document_requests for select
  using (public.current_user_has_merchant_access(merchant_id));

create policy "super admins can view all document requests"
  on public.merchant_document_requests for select
  using ((select public.current_user_is_super_admin()));

-- No insert/update/delete policy: written via apps/api (service_role) only.

-- ----------------------------------------------------------------------------

create table public.document_request_files (
  id uuid primary key default gen_random_uuid(),
  request_id uuid not null references public.merchant_document_requests (id) on delete cascade,
  merchant_id uuid not null references public.merchants (id) on delete cascade,

  document_label text not null,
  file_path text not null,
  original_filename text not null,
  mime_type text not null,
  size_bytes bigint not null,

  uploaded_by uuid not null references auth.users (id),
  created_at timestamptz not null default now()
);

comment on table public.document_request_files is
  'Files a merchant submitted against a document request. file_path points into the private "document-requests" storage bucket — never a public URL. merchant_id is denormalized from the parent request for simple RLS.';

create index document_request_files_request_id_idx on public.document_request_files (request_id);

alter table public.document_request_files enable row level security;

create policy "merchant members can view their own document request files"
  on public.document_request_files for select
  using (public.current_user_has_merchant_access(merchant_id));

create policy "super admins can view all document request files"
  on public.document_request_files for select
  using ((select public.current_user_is_super_admin()));

-- No insert/update/delete policy: written via apps/api (service_role) only.

-- ----------------------------------------------------------------------------
-- Disputes: a customer/client-reported chargeback or product/service issue
-- against a merchant. merchant_id/transaction_id are nullable — a customer
-- reporting via the public form may not know (or may mistype) the exact
-- transaction reference; app/routers/public_disputes.py does a best-effort
-- lookup to backfill them without ever rejecting the report over it.

create table public.disputes (
  id uuid primary key default gen_random_uuid(),

  merchant_id uuid references public.merchants (id) on delete set null,
  transaction_id uuid references public.transactions (id) on delete set null,

  customer_name text not null,
  customer_phone text not null,
  customer_email text,

  transaction_reference text,
  amount numeric(14, 2),

  reason_category text not null check (reason_category in (
    'PRODUCT_NOT_RECEIVED', 'SERVICE_NOT_DELIVERED', 'WRONG_PRODUCT_OR_SERVICE',
    'DUPLICATE_PAYMENT', 'UNAUTHORIZED_PAYMENT', 'REFUND_REQUESTED', 'OTHER'
  )),
  description text not null,

  status text not null default 'SUBMITTED' check (status in (
    'SUBMITTED', 'MERCHANT_NOTIFIED', 'UNDER_REVIEW', 'REFUND_REQUESTED',
    'REFUNDED', 'REJECTED', 'CLOSED'
  )),

  evidence_files jsonb not null default '[]'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.disputes is
  'A customer-reported chargeback or product/service dispute, submitted via the public /report-transaction form (see app/routers/public_disputes.py) and reviewed by the merchant and/or a super admin.';
comment on column public.disputes.evidence_files is
  'Array of {file_path, original_filename} objects in the private "dispute-evidence" bucket — captured at submission time, since a public reporter has no session to resume an upload flow.';

create index disputes_merchant_id_idx on public.disputes (merchant_id);
create index disputes_status_idx on public.disputes (status);
create index disputes_transaction_reference_idx on public.disputes (transaction_reference);

create trigger disputes_set_updated_at
  before update on public.disputes
  for each row execute function public.set_updated_at();

alter table public.disputes enable row level security;

create policy "merchant members can view their own disputes"
  on public.disputes for select
  using (merchant_id is not null and public.current_user_has_merchant_access(merchant_id));

create policy "super admins can view all disputes"
  on public.disputes for select
  using ((select public.current_user_is_super_admin()));

-- No insert/update/delete policy: written via apps/api (service_role) only —
-- including the public report endpoint, which is unauthenticated but still
-- only ever writes through the backend's service_role client, never a
-- direct client-side insert.

-- ----------------------------------------------------------------------------

create table public.dispute_messages (
  id uuid primary key default gen_random_uuid(),
  dispute_id uuid not null references public.disputes (id) on delete cascade,
  merchant_id uuid references public.merchants (id) on delete cascade,

  sender_type text not null check (sender_type in ('merchant', 'admin', 'system')),
  sender_id uuid references auth.users (id) on delete set null,

  body text not null,
  attachment_files jsonb not null default '[]'::jsonb,

  created_at timestamptz not null default now()
  -- No updated_at: append-only conversation thread.
);

comment on table public.dispute_messages is
  'Append-only conversation thread on a dispute (merchant responses, admin requests, system status notes). merchant_id is denormalized from the parent dispute for simple RLS.';

create index dispute_messages_dispute_id_idx on public.dispute_messages (dispute_id);

create trigger dispute_messages_immutable
  before update or delete on public.dispute_messages
  for each row execute function public.forbid_mutation();

alter table public.dispute_messages enable row level security;

create policy "merchant members can view their own dispute messages"
  on public.dispute_messages for select
  using (merchant_id is not null and public.current_user_has_merchant_access(merchant_id));

create policy "super admins can view all dispute messages"
  on public.dispute_messages for select
  using ((select public.current_user_is_super_admin()));

-- No insert/update/delete policy: written via apps/api (service_role) only.

-- ----------------------------------------------------------------------------
-- Refunds: manual workflow (no live payment-provider refund API yet — see
-- app/services/disputes_service.py). Always references the original
-- transaction; reaching SUCCESS posts a real type='refund' ledger entry.

create table public.refunds (
  id uuid primary key default gen_random_uuid(),

  dispute_id uuid not null references public.disputes (id) on delete cascade,
  transaction_id uuid not null references public.transactions (id) on delete restrict,
  merchant_id uuid not null references public.merchants (id) on delete cascade,

  amount numeric(14, 2) not null check (amount > 0),
  currency text not null default 'TZS',

  status text not null default 'REQUESTED' check (status in (
    'REQUESTED', 'APPROVED', 'PROCESSING', 'SUCCESS', 'FAILED', 'CANCELLED'
  )),
  requested_by text not null check (requested_by in ('merchant', 'admin')),

  evidence_files jsonb not null default '[]'::jsonb,
  provider_reference text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.refunds is
  'A refund against an original transaction, initiated from a dispute (merchant acceptance or admin request). Manual workflow: PROCESSING -> SUCCESS/FAILED is an admin marking it based on provider/manual confirmation, not an automated provider call.';

create index refunds_dispute_id_idx on public.refunds (dispute_id);
create index refunds_merchant_id_idx on public.refunds (merchant_id);
create index refunds_status_idx on public.refunds (status);

create trigger refunds_set_updated_at
  before update on public.refunds
  for each row execute function public.set_updated_at();

alter table public.refunds enable row level security;

create policy "merchant members can view their own refunds"
  on public.refunds for select
  using (public.current_user_has_merchant_access(merchant_id));

create policy "super admins can view all refunds"
  on public.refunds for select
  using ((select public.current_user_is_super_admin()));

-- No insert/update/delete policy: written via apps/api (service_role) only.

-- ----------------------------------------------------------------------------
-- Private storage buckets — same default-deny shape as merchant-documents:
-- public: false, zero storage.objects policies, service_role (apps/api)
-- only, signed URLs generated on demand for review.

insert into storage.buckets (id, name, public)
values
  ('document-requests', 'document-requests', false),
  ('dispute-evidence', 'dispute-evidence', false)
on conflict (id) do nothing;
