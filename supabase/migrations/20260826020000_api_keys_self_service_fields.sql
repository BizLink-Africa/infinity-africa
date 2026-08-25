-- Self-service API credential fields:
--   key_last4                      -- last 4 chars of the plaintext secret,
--                                      captured only at creation/rotation,
--                                      for the masked "inf_live_xxxx....1234"
--                                      display (key_prefix alone already
--                                      shows the front; this shows the back).
--   ip_whitelist_enabled            -- the merchant's per-key choice: true =
--                                      enforce api_ip_allowlist for this key,
--                                      false = accept the key from any IP.
--   continue_without_ip_whitelist   -- explicit "I understand and want no
--                                      allowlist" acknowledgment, mutually
--                                      exclusive with ip_whitelist_enabled
--                                      (enforced app-side, not by a DB
--                                      constraint, since the choice is made
--                                      once at creation and never both).

alter table public.api_keys
  add column key_last4 text,
  add column ip_whitelist_enabled boolean not null default false,
  add column continue_without_ip_whitelist boolean not null default true;

comment on column public.api_keys.key_last4 is
  'Last 4 characters of the plaintext secret, captured once at creation/rotation, for masked display only.';
comment on column public.api_keys.ip_whitelist_enabled is
  'Merchant opt-in: when true, requests on this key are checked against api_ip_allowlist (live environment only).';
comment on column public.api_keys.continue_without_ip_whitelist is
  'Merchant opt-out acknowledgment: when true (the default), this key accepts requests from any IP.';
