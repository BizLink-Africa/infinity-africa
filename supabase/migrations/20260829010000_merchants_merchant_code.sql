-- Human-friendly Merchant ID: an 8-digit code (27 + 6 random digits) shown
-- to Super Admin and the merchant themselves so a business can be looked up
-- and communicated about without pasting a UUID. Identification only — not
-- a secret, not an auth credential, never used as/inside an API key.
--
-- Generated once per merchant (see app/services/merchant_code.py, wired
-- into app/services/onboarding.py and app/routers/merchants.py) and never
-- changed afterward. Column starts nullable so this migration can backfill
-- existing merchants in the same transaction before locking it down with
-- NOT NULL — no merchant is ever left without one after this migration
-- completes.

alter table public.merchants
  add column merchant_code varchar(8)
    check (merchant_code ~ '^27[0-9]{6}$');

create unique index merchants_merchant_code_key on public.merchants (merchant_code);

comment on column public.merchants.merchant_code is
  'Human-friendly Merchant ID (27 + 6 digits) for Super Admin/merchant identification. Not a secret, not an auth credential. Generated once, immutable.';

-- Backfill: assign a fresh, unique 27****** code to every merchant that
-- predates this column. Never touches a merchant that already has one
-- (the whole point of self-payment-review-style backfills is to only fill
-- gaps, never overwrite). Uses plain random() — adequate for a one-time
-- administrative backfill of a non-secret display code; the ongoing
-- application-level generator (app/services/merchant_code.py) is the one
-- that uses a cryptographically safe RNG for newly-created merchants.
do $$
declare
  m record;
  candidate varchar(8);
  attempts int;
begin
  for m in select id from public.merchants where merchant_code is null loop
    attempts := 0;
    loop
      candidate := '27' || lpad(floor(random() * 1000000)::int::text, 6, '0');
      attempts := attempts + 1;
      exit when not exists (select 1 from public.merchants where merchant_code = candidate);
      if attempts > 50 then
        raise exception 'merchant_code backfill: could not find a unique code for merchant % after % attempts', m.id, attempts;
      end if;
    end loop;
    update public.merchants set merchant_code = candidate where id = m.id;
  end loop;
end;
$$;

alter table public.merchants
  alter column merchant_code set not null;
