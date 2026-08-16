-- platform_admins: Infinity staff who operate the platform itself (the
-- SUPER_ADMIN role), independent of any single merchant. Membership in this
-- table — not any Supabase Auth user_metadata/app_metadata field — is what
-- public.current_user_is_super_admin() checks (see the next migration).

create table public.platform_admins (
  id uuid primary key default gen_random_uuid(),

  user_id uuid not null references auth.users (id) on delete cascade,
  role text not null default 'SUPER_ADMIN' check (role = 'SUPER_ADMIN'),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  unique (user_id)
);

comment on table public.platform_admins is
  'Platform staff with super-admin access to all merchant data. Deliberately separate from merchant_users — a super admin is not "a member" of any merchant.';

create trigger platform_admins_set_updated_at
  before update on public.platform_admins
  for each row execute function public.set_updated_at();

alter table public.platform_admins enable row level security;

-- Real policy: a user may always check their own admin status. Broader
-- roster-visibility policies (e.g. for a future admin-management screen)
-- are added in the RLS policies migration once the helper functions exist.
create policy "users can view their own admin record"
  on public.platform_admins for select
  using (user_id = auth.uid());
