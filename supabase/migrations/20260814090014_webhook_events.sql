-- webhook_events: outbound event deliveries to a merchant's webhook endpoint.
-- event_name mirrors WebhookEvent in packages/shared/src/webhook-events.ts.

create table public.webhook_events (
  id uuid primary key default gen_random_uuid(),

  merchant_id uuid not null references public.merchants (id) on delete cascade,

  event_name text not null check (event_name in (
    'payment.succeeded', 'payment.failed', 'payment.pending',
    'disbursement.succeeded', 'disbursement.failed',
    'invoice.paid', 'invoice.overdue',
    'payment_link.created', 'payment_link.expired',
    'refund.succeeded', 'refund.failed',
    'chargeback.opened', 'chargeback.resolved'
  )),

  payload jsonb not null default '{}'::jsonb,
  target_url text not null,

  status text not null default 'pending'
    check (status in ('pending', 'delivered', 'failed', 'retrying')),
  attempts int not null default 0 check (attempts >= 0),
  last_attempted_at timestamptz,
  delivered_at timestamptz,
  response_status_code int,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.webhook_events is
  'Log + delivery state of each outbound webhook event sent to a merchant.';
comment on column public.webhook_events.event_name is
  'Mirrors WebhookEvent in packages/shared/src/webhook-events.ts.';
comment on column public.webhook_events.target_url is
  'Destination URL for this delivery attempt, as configured by the merchant.';

create index webhook_events_merchant_id_idx on public.webhook_events (merchant_id);
create index webhook_events_status_idx on public.webhook_events (status);
create index webhook_events_event_name_idx on public.webhook_events (event_name);

create trigger webhook_events_set_updated_at
  before update on public.webhook_events
  for each row execute function public.set_updated_at();

alter table public.webhook_events enable row level security;

-- Planned shape:
--   create policy "merchant staff can view their own webhook events"
--     on public.webhook_events for select
--     using (merchant_id in (select merchant_id from public.merchant_users where user_id = auth.uid()));
