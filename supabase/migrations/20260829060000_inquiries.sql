-- inquiries: a "contact us" submission from the public marketing site
-- (apps/web/src/components/landing/contact-form.tsx). Saved first, then a
-- notification email is sent to the CEO (see
-- app/services/email.py::send_inquiry_notification_email) — email failure
-- never loses the inquiry, since it's already committed before the send
-- is attempted.

create table public.inquiries (
  id uuid primary key default gen_random_uuid(),

  full_name text not null,
  business_name text,
  email text not null,
  phone text,
  message text not null,

  -- Where the submission came from (e.g. 'contact_page') — free text
  -- rather than an enum, since new source pages are just new string
  -- values, no schema change needed.
  source text not null default 'contact_page',

  created_at timestamptz not null default now()
);

comment on table public.inquiries is
  'A "contact us" / inquiry submission from the public marketing site, notified to the CEO by email.';

create index inquiries_created_at_idx on public.inquiries (created_at desc);

alter table public.inquiries enable row level security;

create policy "super admins can view all inquiries"
  on public.inquiries for select
  using ((select public.current_user_is_super_admin()));

-- No insert/update/delete policy: written by apps/api (service_role) only
-- — the public contact form never talks to Supabase directly.
