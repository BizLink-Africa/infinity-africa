# Selcom Live Go-Live

How to move `apps/api` from the mock Selcom client to live Selcom API
calls. **Do not start this until you're ready to actually go live** — every
collection flow (payment links, invoices, `/v1/collections/*`) already
works end-to-end today against `app/services/selcom/mock_client.py`;
nothing about the frontend, the payment-link flow, or the customer payment
page is blocked on this.

**Withdrawals are a separate integration** — Selcom's Business
Disbursement API, not the checkout API this document covers. Own client
(`app/services/selcom_business/`), own env vars (`SELCOM_BUSINESS_*`), own
RSA-SHA256 signing. See "Selcom Business Disbursement API (withdrawals)"
near the end of this document, and
[`docs/withdrawal-pricing-and-approval.md`](./withdrawal-pricing-and-approval.md)
for the approval flow itself.

## Why this waits

Selcom whitelists by source IP. Railway's default outbound IP is shared and
not static, so Selcom cannot whitelist it — the backend needs a **static**
outbound IP first, which on Railway requires deploying the service before
you can even request one. That's why this is a post-deploy procedure, not
something to do locally.

## Architecture recap

`apps/web` (Vercel) calls `apps/api` (Railway) only. `apps/api` is the only
thing that ever calls Selcom. Selcom credentials live in Railway's
environment variables exclusively — never in Vercel, never in any
`apps/web` file, never committed to the repo. See
[`docs/backend-setup.md`](./backend-setup.md) for general deploy/env-var
setup; this doc covers only the Selcom-specific go-live steps.

## Steps

### 1. Deploy the FastAPI backend to Railway

Point the Railway service at this repo's `apps/api/` directory, same start
command as [`docs/backend-setup.md` §6](./backend-setup.md#6-deploying):
`uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Set every env var from
`.env.example`'s required section (Supabase URL/keys, JWKS, CORS,
`PUBLIC_APP_URL`); leave every `SELCOM_*` var at its default (blank /
`SELCOM_MODE=mock`) for now.

### 2. Enable Railway Static Outbound IP

Requires a Railway plan that supports Static Outbound IPs (Pro at the time
of writing — the free/Hobby tier does not offer this). In the Railway
service's **Settings → Networking**, enable **Static Outbound IPs**, then
redeploy the service — a static IP only applies to a fresh deployment, not
retroactively to one already running.

### 3. Copy the Railway static outbound IP

After the redeploy, copy the assigned outbound IPv4 address from that same
**Settings → Networking** panel.

### 4. Send the IP to Selcom for whitelisting

Send that IPv4 address to Selcom's technical/integration team and ask them
to whitelist it for your account. Live API calls from this backend will
fail (connection refused/rejected, or an auth error depending on how Selcom
enforces it) until whitelisting is confirmed on Selcom's side — there's
nothing to fix in this codebase if that's the failure you see.

### 5. Add Selcom production credentials to Railway env variables

Once Selcom issues live credentials, add them to the **Railway service's**
environment variables only — never to Vercel, never to any `apps/web` file:

| Variable | Value |
|---|---|
| `SELCOM_BASE_URL` | Selcom's API base URL for your account/environment |
| `SELCOM_API_KEY` | Issued by Selcom |
| `SELCOM_API_SECRET` | Issued by Selcom |
| `SELCOM_VENDOR_ID` | Issued by Selcom |
| `SELCOM_WEBHOOK_SECRET` | Shared secret for verifying inbound webhook signatures (agree this with Selcom, or generate one and share it with them if they support caller-provided secrets) |

Leave `SELCOM_MODE=mock` and `SELCOM_COLLECTION_ENABLED` at `false` until
the next step — adding credentials alone doesn't switch anything over.
`SELCOM_WITHDRAWAL_ENABLED` is informational-only today (surfaced via
`GET /v1/system/selcom-config-status`, doesn't gate any code path) — the
real withdrawal on/off switch is `SELCOM_BUSINESS_MODE`, covered separately
below.

### 6. Change `SELCOM_MODE=live`

Only after whitelisting is confirmed and the credentials above are set.
This is the one variable that actually switches
`app/services/selcom/client.py::get_selcom_client()` from
`MockSelcomClient` to `LiveSelcomClient` (`app/services/selcom/live_client.py`).
Enable `SELCOM_COLLECTION_ENABLED`/`SELCOM_WITHDRAWAL_ENABLED` as needed at
the same time.

**Before flipping this in production**, fix the placeholder pieces of
`app/services/selcom/`, none of which have been verified against a real
Selcom API reference or sandbox:

- `live_client.py` — the `_PATH_*` endpoint constants, and the request body
  shape `SelcomHTTPClient` sends for each call.
- `signature.py` — the outbound request-signing scheme (`Authorization:
  SELCOM <key>` + HMAC-SHA256 digest header) is a plausible, common shape,
  not a confirmed one.
- `parsing.py` — `extract_provider_reference`/`extract_status` guess at
  Selcom's response field names and result codes.

Test against a real Selcom sandbox account first if Selcom provides one.

Once live, confirm what the running Railway deployment actually sees —
without ever exposing the secret values themselves — via
`GET /v1/system/selcom-config-status` (super-admin only; see
[`docs/api.md`](./api.md)):

```json
{
  "success": true,
  "data": {
    "collection_enabled": true,
    "withdrawal_enabled": true,
    "mock_mode": false,
    "base_url_configured": true,
    "api_key_configured": true,
    "api_secret_configured": true,
    "vendor_id_configured": true,
    "business_mode": "sandbox",
    "business_api_key_configured": true,
    "business_private_key_configured": true,
    "business_account_number_configured": true
  }
}
```

The `business_*` fields report the separate Selcom Business Disbursement
API config (withdrawals) — see below; they're independent of the
`collection_enabled`/`mock_mode`/etc. fields above.

### 7. Test STK Push, Push USSD, Dynamic QR, Push to Selcom Pesa

All four collection methods go through the same `PaymentProvider` interface
regardless of mode — exercise each one for real once `SELCOM_MODE=live`:

- `/v1/collections/{method}` for `USSD_PUSH`, `STK_PUSH`,
  `SELCOM_PESA_PUSH`, `DYNAMIC_QR` (see [`docs/api.md`](./api.md)), or
- an actual payment link's checkout page (`/pay/{public_slug}`), which
  drives the same `initiate_collection`/`generate_dynamic_qr` calls via
  `POST /public/payment-links/{public_slug}/collect`.

For each: confirm the push/prompt actually reaches a real phone (or the QR
actually scans and resolves in a real wallet app), and that
`check_collection_status` / the resulting collection row reflects a real
Selcom result — not a `mock_selcom` provider reference.

### 8. Test the webhook callback and reconciliation

Give Selcom the callback URL `https://<your-railway-domain>/v1/webhooks/selcom`
(the route is fixed in `app/main.py` regardless of `SELCOM_WEBHOOK_PATH`,
which exists only as documentation). Trigger a real collection or payout
that resolves asynchronously and confirm:

- The delivery is verified (`X-Selcom-Signature` checked against
  `SELCOM_WEBHOOK_SECRET`, see `app/services/selcom/webhooks.py`) and
  logged to `selcom_webhook_events`.
- A duplicate delivery (same `event_id`) short-circuits with
  `{"status": "duplicate"}` instead of reprocessing.
- The linked collection and its transaction move out of `processing`
  correctly (`resolve_collection_from_callback` in
  `app/services/collections.py`), ledger entries post on success, and a
  `payment_link`/`invoice` linked to a collection updates accordingly.
  (`resolve_disbursement_from_callback` in `app/services/disbursements.py`
  still exists for a withdrawal left `PROCESSING`, but the Selcom Business
  Disbursement API's documented shape is request/response + a query
  endpoint, not a webhook — an admin-triggered refresh/reconcile action in
  the Super Admin console is the real path for that now, not this
  callback. See the Business API section below.)

If Selcom's real callback payload shape differs from what
`app/routers/webhooks.py`/`app/schemas/webhooks.py` currently expect,
that's the other placeholder to fix before relying on this in production —
same caveat as `live_client.py`/`parsing.py` above.

## Selcom Business Disbursement API (withdrawals)

A separate, real, documented Selcom product
([developer.selcom.business](https://developer.selcom.business/)) that
every withdrawal approval calls — see `app/services/selcom_business/` and
[`docs/withdrawal-pricing-and-approval.md`](./withdrawal-pricing-and-approval.md).
Independent of every step above: its own client, its own env-var
namespace, its own **RSA-SHA256** signing (not the checkout API's
HMAC-SHA256).

### 1. Configure sandbox

Set these in Railway (or locally in `.env` for development against
Selcom's real sandbox):

```
SELCOM_BUSINESS_MODE=sandbox
SELCOM_BUSINESS_SANDBOX_BASE_URL=https://sandbox.selcom.business
SELCOM_BUSINESS_API_KEY=<issued by Selcom for your sandbox account>
SELCOM_BUSINESS_PRIVATE_KEY_BASE64=<base64-encoded PEM RSA private key>
SELCOM_BUSINESS_ACCOUNT_NUMBER=<your Selcom Business account number>
```

Test a full withdrawal round-trip against the real sandbox: submit a
withdrawal (`POST /v1/merchant/withdrawals` — stays
`PENDING_ADMIN_APPROVAL`, never touches Selcom), then approve it as a
Super Admin (`POST /v1/admin/withdrawals/{id}/approve` — this is the one
and only call site that reaches Selcom). Confirm the response shape
`app/services/selcom_business/parsing.py` expects actually matches what
sandbox returns — that module's field-name guesses are the one piece not
yet verified against a real response (the request shape, headers, and
signing scheme were fetched directly from Selcom's own current docs, so
those should already be correct).

### 2. If Selcom returns error 611 / HTTP 403 (IP not whitelisted)

Same static-IP requirement as the checkout API above — Selcom whitelists
this API by source IP too. If sandbox or production calls come back 403
with error code 611, follow steps 2–4 above (enable Railway Static
Outbound IP, copy it, send it to Selcom) — the withdrawal itself is fine;
this backend's outbound IP just isn't whitelisted yet. A withdrawal that
hits this while `NEEDS_ADMIN_ATTENTION`/`BLOCKED_IP_WHITELIST` doesn't lose
its reserved funds — retry via the Super Admin console's refresh action
once whitelisting is confirmed.

### 3. Configure production

Once Selcom issues live credentials for your production account:

```
SELCOM_BUSINESS_MODE=live
SELCOM_BUSINESS_PRODUCTION_BASE_URL=https://api.selcom.business/v1
SELCOM_BUSINESS_API_KEY=<production key>
SELCOM_BUSINESS_PRIVATE_KEY_BASE64=<production private key, base64>
SELCOM_BUSINESS_ACCOUNT_NUMBER=<production account number>
```

**Never** set any `SELCOM_BUSINESS_*` variable in Vercel/`apps/web` —
same rule as every other Selcom credential in this document. Confirm what
Railway actually has configured (without exposing the secret values) via
`GET /v1/system/selcom-config-status`'s `business_*` fields.

## Rolling back

Checkout API: set `SELCOM_MODE=mock` (and `SELCOM_COLLECTION_ENABLED` back
to `false`) in Railway and redeploy — every collection immediately goes
back through `MockSelcomClient`. Business Disbursement API: set
`SELCOM_BUSINESS_MODE=mock` — every withdrawal approval immediately goes
back through `MockSelcomBusinessClient`. Neither needs a code change or a
data migration; these are the same switches used throughout local
development.
