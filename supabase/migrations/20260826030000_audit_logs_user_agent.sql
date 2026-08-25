-- audit_logs already has ip_address (inet); add the request's User-Agent
-- alongside it so an API-key audit trail (created/rotated/revoked, failed
-- authentication, rejected IP attempts) captures both per Part 4 of the
-- self-service API credentials brief.

alter table public.audit_logs
  add column user_agent text;

comment on column public.audit_logs.user_agent is
  'Request User-Agent header at the time of the action, when known (e.g. API-key auth events). Null for actions with no associated HTTP request.';
