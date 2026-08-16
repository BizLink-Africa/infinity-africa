-- Merchant self-service onboarding: the review workflow a merchant goes
-- through after signing up (business details + compliance documents) before
-- a super admin verifies them. Deliberately a NEW table, not an overload of
-- merchants.status/kyc_status: those already have their own, different
-- vocabulary (pending/active/suspended/closed, unverified/pending/verified/
-- rejected) used by the existing super-admin Merchants and Compliance/KYC
-- pages. onboarding_submissions.review_status is its own lifecycle
-- (PENDING_VERIFICATION/VERIFIED/REJECTED/INFO_REQUESTED); approving a
-- submission also promotes merchants.status/kyc_status in the same backend
-- call (see app/services/onboarding.py) so the two stay in sync without
-- merging them into one column.

create table public.onboarding_submissions (
  id uuid primary key default gen_random_uuid(),
  merchant_id uuid not null unique references public.merchants (id) on delete cascade,

  nature_of_business text not null,
  business_category text not null,
  physical_address text not null,
  region_city text not null,
  website_url text,
  services_needed text[] not null default '{}',

  accepted_terms boolean not null default false,
  accepted_privacy boolean not null default false,
  accepted_at timestamptz,

  review_status text not null default 'PENDING_VERIFICATION'
    check (review_status in ('PENDING_VERIFICATION', 'VERIFIED', 'REJECTED', 'INFO_REQUESTED')),
  review_note text,
  reviewed_by uuid references auth.users (id) on delete set null,
  reviewed_at timestamptz,

  submitted_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.onboarding_submissions is
  'One row per merchant: the business-details submission from self-service onboarding and its super-admin review outcome.';
comment on column public.onboarding_submissions.review_status is
  'Onboarding review lifecycle — independent of merchants.status/kyc_status. Approving promotes both; see app/services/onboarding.py.';

create index onboarding_submissions_review_status_idx on public.onboarding_submissions (review_status);

create trigger onboarding_submissions_set_updated_at
  before update on public.onboarding_submissions
  for each row execute function public.set_updated_at();

alter table public.onboarding_submissions enable row level security;

create policy "merchant members can view their own onboarding submission"
  on public.onboarding_submissions for select
  using (public.current_user_has_merchant_access(merchant_id));

create policy "super admins can view all onboarding submissions"
  on public.onboarding_submissions for select
  using ((select public.current_user_is_super_admin()));

-- No insert/update/delete policy: created and reviewed by apps/api
-- (service_role) only, same convention as merchants/merchant_users.

-- --------------------------------------------------------------------------

create table public.onboarding_documents (
  id uuid primary key default gen_random_uuid(),
  merchant_id uuid not null references public.merchants (id) on delete cascade,

  document_type text not null
    check (document_type in ('NIDA', 'TIN_CERTIFICATE', 'BUSINESS_LICENCE')),

  file_path text not null,
  original_filename text not null,
  mime_type text not null,
  size_bytes bigint not null,

  upload_status text not null default 'UPLOADED'
    check (upload_status in ('UPLOADED', 'VERIFIED', 'REJECTED')),

  uploaded_by uuid not null references auth.users (id),
  uploaded_at timestamptz not null default now(),

  unique (merchant_id, document_type)
);

comment on table public.onboarding_documents is
  'Compliance documents (NIDA, TIN certificate, business licence) uploaded during onboarding. file_path points into the private "merchant-documents" storage bucket — never a public URL.';

create index onboarding_documents_merchant_id_idx on public.onboarding_documents (merchant_id);

alter table public.onboarding_documents enable row level security;

create policy "merchant members can view their own onboarding documents"
  on public.onboarding_documents for select
  using (public.current_user_has_merchant_access(merchant_id));

create policy "super admins can view all onboarding documents"
  on public.onboarding_documents for select
  using ((select public.current_user_is_super_admin()));

-- No insert/update/delete policy: uploaded via apps/api (service_role) only.

-- --------------------------------------------------------------------------
-- Private storage bucket for onboarding compliance documents. `public: false`
-- plus zero storage.objects policies is default-deny for anon/authenticated
-- — only service_role (apps/api) can read or write, and only signed URLs
-- (short-lived, generated on demand for super-admin review) ever expose a
-- document's bytes. No client (merchant or admin) ever gets the
-- service_role key or an unsigned path.

insert into storage.buckets (id, name, public)
values ('merchant-documents', 'merchant-documents', false)
on conflict (id) do nothing;
