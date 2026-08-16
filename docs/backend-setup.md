# Backend Setup Guide

How to configure Supabase, run database migrations, start `apps/api` locally,
and how the Merchant Portal frontend (`apps/web`) connects to it. For the
endpoint reference, auth scheme, and idempotency rules, see
[`docs/api.md`](./api.md). For architecture/design rationale, see
[`docs/implementation-notes.md`](./implementation-notes.md).

## Why there's no Prisma here

The original request for this integration named Prisma for schema/migrations.
`apps/api` already had a complete, tested Postgres schema (28 migrations
under `supabase/migrations/`, applied via the Supabase CLI) with hand-written
Postgres functions and triggers — the atomic double-entry ledger posting
(`post_ledger_entries`) and its balance-check trigger in particular — that
don't map cleanly onto Prisma's declarative schema model. Introducing Prisma
now would mean either reverse-engineering a `schema.prisma` from 28 existing
migrations (requires a live DB to introspect) or hand-maintaining two parallel
schema-authoring systems. Given the existing system is real, tested (135+
passing tests), and already working, this integration keeps
`supabase/migrations/*.sql` as the single source of truth and does not
introduce Prisma anywhere.

## 1. Create a Supabase project

1. [supabase.com](https://supabase.com) → New Project. Note the project's
   **Project URL**, **anon public key**, and **service_role key**
   (Project Settings → API).
2. Note the **JWKS URL** and **issuer** for token verification (Project
   Settings → API → JWT Keys → "JWT Signing Keys" tab) — this is the
   current, preferred way `apps/api` verifies Supabase Auth access tokens
   (asymmetric ES256/RS256, no shared secret). Every Supabase project
   exposes these at predictable URLs: `SUPABASE_JWKS_URL` is
   `{Project URL}/auth/v1/.well-known/jwks.json` and `SUPABASE_JWT_ISSUER`
   is `{Project URL}/auth/v1`. The **Legacy JWT Secret** tab on that same
   page is a fallback, only needed if the project still signs tokens with a
   shared HS256 secret instead of JWKS signing keys — see `app/auth/jwt.py`.
3. Note the **connection string** (Project Settings → Database →
   Connection string, "URI" tab) — this is `DATABASE_URL`/`DIRECT_URL`,
   **not currently used by any code path**: `app/database/session.py` talks
   to Supabase over the REST API via `supabase-py`, never a direct Postgres
   driver, Prisma, or another ORM. Only fetch this if a future typed query
   layer is added — safe to skip otherwise.

## 2. Apply the database schema

Using the [Supabase CLI](https://supabase.com/docs/guides/cli):

```bash
supabase login
supabase link --project-ref <your-project-ref>
supabase db push
```

This applies every file in `supabase/migrations/` in order — all 15 tables
requested (`merchants`, `merchant_users`, `customers`, `api_keys`,
`payment_links`, `invoices`, `invoice_items`, `collections`, `disbursements`
[the "withdrawals" table — see naming note below], `transactions`,
`ledger_accounts`, `ledger_entries`, `webhook_events`, `audit_logs`,
`settlement_accounts`), plus `platform_admins`, `idempotency_keys`,
`selcom_webhook_events`, RLS policies, and the ledger's Postgres
functions/triggers. See `docs/implementation-notes.md`'s "Database schema"
section for what each table is for.

**Naming note**: the schema and every backend service/route uses
"disbursement" — this predates the current task and is deliberately left
unchanged (renaming a tested table/column name across 28 migrations for a
UI-wording preference is unwarranted risk). Only the user-facing frontend
copy and the new `/v1/merchant/withdrawals` route path say "withdrawal" —
matching the pre-existing convention (the portal nav already labels this
"Withdrawals" while linking to `/portal/disbursements`).

## 3. Configure `apps/api`

```bash
cd apps/api
cp .env.example .env
```

Fill in `.env`. **Required** — the backend won't authenticate or reach
Supabase without these:

| Variable | Value |
|---|---|
| `SUPABASE_URL` | Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | service_role key — **server-only, never exposed to the frontend** |
| `SUPABASE_JWKS_URL` | `{Project URL}/auth/v1/.well-known/jwks.json` — verifies Supabase Auth access tokens (asymmetric, no shared secret, no network call per request beyond an internally-cached JWKS fetch) |
| `SUPABASE_JWT_ISSUER` | `{Project URL}/auth/v1` |
| `CORS_ORIGINS` | `["http://localhost:3000"]` for local dev — **note**: the code reads exactly this name (a JSON array); `FRONTEND_ORIGINS` is not recognized and has no effect if set instead |
| `PUBLIC_APP_URL` | `http://localhost:3000` — used to build payment-link checkout URLs. **Note**: the code reads exactly this name; `PUBLIC_WEB_URL` is not recognized and has no effect if set instead |

**Optional / legacy / currently unused** — leave blank, this is never a
"missing required var" error (`pydantic-settings` silently ignores unset or
unrecognized keys):

| Variable | Why it's optional |
|---|---|
| `SUPABASE_JWT_SECRET` | Legacy HS256 shared-secret verification. Only needed for a project that still signs tokens with a shared secret instead of JWKS keys, or to keep verifying already-issued tokens through a JWKS rotation's grace period. JWKS (above) is tried first and should remain the preferred method — see `app/auth/jwt.py`. |
| `DATABASE_URL`, `DIRECT_URL` | No code path uses a direct Postgres connection — `apps/api` talks to Supabase exclusively over the REST API via `supabase-py`, never Prisma, SQLAlchemy, or another ORM. Only needed if a future direct-connection layer is added. |

Application config (defaults in `.env.example` are fine for local dev):
`SELCOM_WEBHOOK_SECRET` (any value locally — verifies the mock Selcom
webhook's HMAC signature), `PLATFORM_FEE_PERCENTAGE`,
`DISBURSEMENT_APPROVAL_THRESHOLD`, `MOCK_PROVIDER_*`.

**Selcom production integration** — all optional, all blank/default until
Selcom whitelisting is done and live credentials are issued. See
[`docs/selcom-live-go-live.md`](./selcom-live-go-live.md) for the full
deploy → whitelist → go-live procedure; summary here:

| Variable | Purpose |
|---|---|
| `SELCOM_BASE_URL` | Selcom's API base URL for your account/environment |
| `SELCOM_API_KEY`, `SELCOM_API_SECRET`, `SELCOM_VENDOR_ID` | Live Selcom credentials — **Railway/backend env vars only, never in `apps/web`/Vercel** |
| `SELCOM_COLLECTION_ENABLED`, `SELCOM_WITHDRAWAL_ENABLED` | Feature flags — keep `false` until whitelisting + credentials are confirmed |
| `SELCOM_WEBHOOK_PATH` | Informational only — the real route (`/v1/webhooks/selcom`) is hardcoded in `app/main.py` regardless of this value; documented here for convenience when giving Selcom your callback URL |
| `SELCOM_WEBHOOK_SECRET` | Shared secret verifying inbound webhook signatures — any value locally, a real shared secret from Selcom in production |
| `SELCOM_MODE` | `mock` today by default — see the note below |

**Current status**: `app/services/selcom/client.py::get_selcom_client()`
branches on `SELCOM_MODE` — `"mock"` (the default) returns
`MockSelcomClient` (`app/services/selcom/mock_client.py`) unchanged;
`"live"` constructs `LiveSelcomClient` (`app/services/selcom/live_client.py`)
from the `SELCOM_BASE_URL`/`SELCOM_API_KEY`/`SELCOM_API_SECRET`/
`SELCOM_VENDOR_ID` vars above, which calls Selcom's Collection (and,
minimally, Payout) API through the same file's `SelcomHTTPClient` — request
signing lives in `app/services/selcom/signature.py`.

**Important — unverified against Selcom's real API reference.** No Selcom
API documentation was available when `app/services/selcom/` was written.
The signing scheme (`Authorization: SELCOM <key>` + an HMAC-SHA256 digest
header), the endpoint paths (`_PATH_*` constants at the top of
`live_client.py`), and the response-field parsing (`extract_provider_reference`/
`extract_status` in `parsing.py`) all follow a plausible, industry-standard
shape — not a confirmed one. Before ever setting `SELCOM_MODE=live` against
production, work through `docs/selcom-live-go-live.md` in full — in
particular fixing `app/services/selcom/live_client.py` against Selcom's real
API reference and testing against a real sandbox account.

Until then, keep `SELCOM_MODE=mock` — every collection endpoint, payment
link, and invoice behaves identically either way, since both clients
implement the same `PaymentProvider` interface
(`app/services/selcom/client.py`).

## 4. Run FastAPI locally

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate        # Windows; source .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt

uvicorn app.main:app --reload
```

API at `http://localhost:8000`; interactive docs at `http://localhost:8000/docs`.

Run the test suite (uses an in-memory fake Supabase client — no live project
needed to run tests, only to actually serve requests):

```bash
pytest
ruff check .
```

## 5. Connect the Merchant Portal frontend

`apps/web/.env.local` already has everything needed:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=<your Supabase project URL>
NEXT_PUBLIC_SUPABASE_ANON_KEY=<your Supabase anon key>
```

(This integration reuses the existing `NEXT_PUBLIC_API_URL` — already the
live backend-base-URL variable, consumed by the public payment-link checkout
pages — rather than adding a second, differently-named variable for the same
thing.)

Every `lib/portal/api.ts` call attaches the signed-in merchant's Supabase
access token as `Authorization: Bearer <token>` (via
`lib/supabase/client-session.ts`'s `getAccessTokenClient()`, which calls the
Supabase browser client's `auth.getSession()`). The backend resolves the
caller's own merchant purely from that token — via
`merchant_users` — no merchant_id is ever sent by the frontend for anything
under `/v1/merchant/*`.

Routes covered end-to-end (`apps/web/src/lib/portal/api.ts` →
`apps/api/app/routers/merchant_portal.py`): merchant profile & overview,
payment links, invoices, collections, withdrawals, transactions, API keys —
see `docs/api.md`'s endpoint table for the full `/v1/merchant/*` list.
Customers, wallet, team, support, and webhooks still read from
`apps/web/src/lib/portal/mock-data.ts` — no `/v1/merchant/*` endpoint exists
for those yet.

### Known gap: onboarding doesn't create a real merchant yet

The Merchant Portal's account-creation/onboarding flow (`/create-account`,
`/onboarding`) writes to an in-memory mock store
(`apps/web/src/lib/onboarding/store.ts`), not a real `merchants`/
`merchant_users` row — and `POST /v1/merchants` (real merchant creation) is
super-admin-only today, so there's no self-service path connecting the two.
Until that's built, a user who signs up through the existing onboarding UI
has no real merchant the backend recognizes; `/merchant/overview` handles
this gracefully (falls back to the onboarding-status view when
`GET /v1/merchant/overview` 404s), but the other six Merchant Portal pages
will show empty lists for such a user. To test the live integration
end-to-end today, seed a `merchants` row and a `merchant_users` row (role
`MERCHANT_ADMIN`) directly for a real Supabase Auth user, e.g. via the
Supabase SQL editor or `POST /v1/merchants` as a super admin (seed a
`platform_admins` row for yourself first).

## 6. Deploying

- **Backend → Railway**: point it at this repo's `apps/api/` directory,
  set the same env vars as `.env`, start command `uvicorn app.main:app
  --host 0.0.0.0 --port $PORT`.
- **Frontend → Vercel**: point it at `apps/web/`, set `NEXT_PUBLIC_API_URL`
  to the deployed Railway URL and the real Supabase project's public values.
  **Never** set any `SELCOM_*` variable in Vercel/`apps/web` — Selcom
  credentials are backend-only (see [`docs/selcom-live-go-live.md`](./selcom-live-go-live.md)).

## 7. Selcom integration on Railway

Full deploy → whitelist → go-live procedure (Static Outbound IP, sending it
to Selcom, adding live credentials, flipping `SELCOM_MODE=live`, testing
each payment method, testing the webhook callback):
[`docs/selcom-live-go-live.md`](./selcom-live-go-live.md).

Short version: `apps/web` (Vercel) calls `apps/api` (Railway) only;
`apps/api` is the only thing that ever calls Selcom, and Selcom credentials
live in Railway's environment variables exclusively — never in Vercel,
never in any `apps/web` file, never committed to the repo. Selcom whitelists
by source IP, so the backend needs a Railway **Static Outbound IP** before
Selcom will accept live traffic from it.
