-- Role-check helper functions used throughout RLS policies (see the next
-- migration) and callable from the frontend/backend via `.rpc()` if needed.
--
-- Each is SECURITY DEFINER with a pinned search_path, which lets it look up
-- role membership regardless of the *caller's* own row-level access to
-- platform_admins/merchant_users — avoiding recursive RLS (a policy on
-- platform_admins that itself queried platform_admins under the caller's
-- own restricted view would only ever see rows it's already allowed to see,
-- which breaks self-checks). Pinning search_path is required for any
-- SECURITY DEFINER function to stop a caller from shadowing `public.*` with
-- objects of their own and hijacking its execution.
--
-- These functions only ever return a boolean or a role name — never raw
-- row data — so elevating their privileges like this does not leak
-- anything a policy wouldn't already be deciding to expose.

create or replace function public.current_user_is_super_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.platform_admins where user_id = auth.uid()
  );
$$;

comment on function public.current_user_is_super_admin() is
  'True if the current Supabase Auth user is a platform super admin (platform_admins membership).';

create or replace function public.current_user_merchant_role(p_merchant_id uuid)
returns text
language sql
stable
security definer
set search_path = public
as $$
  select role from public.merchant_users
  where merchant_id = p_merchant_id
    and user_id = auth.uid()
    and status = 'active'
  limit 1;
$$;

comment on function public.current_user_merchant_role(uuid) is
  'The current user''s role on the given merchant (MERCHANT_ADMIN/MERCHANT_STAFF/DEVELOPER), or null if not an active member.';

create or replace function public.current_user_has_merchant_access(p_merchant_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select public.current_user_merchant_role(p_merchant_id) is not null;
$$;

comment on function public.current_user_has_merchant_access(uuid) is
  'True if the current user is an active member (any role) of the given merchant.';
