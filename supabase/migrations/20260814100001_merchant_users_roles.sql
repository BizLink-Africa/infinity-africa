-- Replace merchant_users' initial (owner/admin/staff) role vocabulary with
-- the platform's authoritative merchant-scoped roles: MERCHANT_ADMIN,
-- MERCHANT_STAFF, DEVELOPER. (SUPER_ADMIN is platform-wide and lives in
-- platform_admins, not here — a merchant_users row is always one of these
-- three.) A later migration must never edit an already-applied migration
-- file in place, so this ships as its own ALTER.

alter table public.merchant_users
  drop constraint merchant_users_role_check;

alter table public.merchant_users
  alter column role set default 'MERCHANT_STAFF';

alter table public.merchant_users
  add constraint merchant_users_role_check
  check (role in ('MERCHANT_ADMIN', 'MERCHANT_STAFF', 'DEVELOPER'));

comment on column public.merchant_users.role is
  'MERCHANT_ADMIN: full control incl. team & API keys. MERCHANT_STAFF: day-to-day operations. DEVELOPER: API docs + API key management only.';
