-- merchant_users: links Supabase Auth users to the merchant(s) they can act
-- on behalf of, with a role. A user can belong to more than one merchant
-- (e.g. an accountant managing several businesses).

create table public.merchant_users (
  id uuid primary key default gen_random_uuid(),

  merchant_id uuid not null references public.merchants (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,

  role text not null default 'staff'
    check (role in ('owner', 'admin', 'staff')),
  status text not null default 'invited'
    check (status in ('invited', 'active', 'suspended')),

  invited_by uuid references auth.users (id) on delete set null,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  unique (merchant_id, user_id)
);

comment on table public.merchant_users is
  'Membership + role of each Supabase Auth user within a merchant account.';
comment on column public.merchant_users.role is
  'owner: full control incl. billing. admin: manage team/settings. staff: day-to-day operations.';

create index merchant_users_user_id_idx on public.merchant_users (user_id);
create index merchant_users_merchant_id_idx on public.merchant_users (merchant_id);

create trigger merchant_users_set_updated_at
  before update on public.merchant_users
  for each row execute function public.set_updated_at();

alter table public.merchant_users enable row level security;

-- Planned shape:
--   create policy "members can view their own memberships"
--     on public.merchant_users for select
--     using (user_id = auth.uid());
