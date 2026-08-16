-- audit_logs: append-only history of admin/system actions, for compliance
-- and support investigations (super-admin "Audit Logs").

create table public.audit_logs (
  id uuid primary key default gen_random_uuid(),

  actor_id uuid references auth.users (id) on delete set null,
  actor_type text not null default 'user' check (actor_type in ('user', 'system', 'api_key')),

  merchant_id uuid references public.merchants (id) on delete set null,

  action text not null,
  resource_type text not null,
  resource_id uuid,

  metadata jsonb not null default '{}'::jsonb,
  ip_address inet,

  created_at timestamptz not null default now()
  -- No updated_at: audit history is append-only, see the immutability trigger below.
);

comment on table public.audit_logs is
  'Append-only record of who did what, for compliance and support investigations.';
comment on column public.audit_logs.actor_id is
  'The Supabase Auth user who performed the action; null for system-initiated actions.';
comment on column public.audit_logs.merchant_id is
  'The merchant whose data was affected, if any; null for platform-level actions.';
comment on column public.audit_logs.action is
  'Dot.case action identifier, e.g. "merchant.suspended", "api_key.revoked".';

create index audit_logs_actor_id_idx on public.audit_logs (actor_id);
create index audit_logs_merchant_id_idx on public.audit_logs (merchant_id);
create index audit_logs_resource_idx on public.audit_logs (resource_type, resource_id);
create index audit_logs_created_at_idx on public.audit_logs (created_at);

create trigger audit_logs_immutable
  before update or delete on public.audit_logs
  for each row execute function public.forbid_mutation();

alter table public.audit_logs enable row level security;

-- Planned shape: platform-internal only.
--   create policy "platform admins can view audit logs"
--     on public.audit_logs for select
--     using (auth.jwt() ->> 'role' = 'platform_admin');
