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

Merchant-facing UI (and the Super Admin console) always say
**"Withdrawal"** — `DisbursementMethod`/`Disbursement`/"Selcom Business
Disbursement API" are internal/backend vocabulary only, used in code,
comments, and this document, never surfaced to a merchant.

### Required Railway env variables

Backend/Railway only — **never** set any of these in Vercel or any
`apps/web` file. `apps/web` only ever reads `NEXT_PUBLIC_SUPABASE_URL`,
`NEXT_PUBLIC_SUPABASE_ANON_KEY`, and `NEXT_PUBLIC_API_URL` (see
`apps/web/.env.example`) — if a `SELCOM_BUSINESS_*` value ever shows up in
a Vercel env var or an `apps/web` file, treat that as a credential leak:
remove it immediately and rotate the key with Selcom.

| Variable | Sandbox | Production |
|---|---|---|
| `SELCOM_BUSINESS_MODE` | `sandbox` | `live` |
| `SELCOM_BUSINESS_SANDBOX_BASE_URL` | `https://sandbox.selcom.business` | *(unused in `live` mode)* |
| `SELCOM_BUSINESS_PRODUCTION_BASE_URL` | *(unused in `sandbox` mode)* | `https://api.selcom.business/v1` |
| `SELCOM_BUSINESS_API_KEY` | sandbox key from Selcom | production key from Selcom |
| `SELCOM_BUSINESS_PRIVATE_KEY_BASE64` | sandbox RSA private key, base64-encoded PEM | production RSA private key, base64-encoded PEM |
| `SELCOM_BUSINESS_ACCOUNT_NUMBER` | sandbox Selcom Business account number | production account number |
| `SELCOM_BUSINESS_TIMEOUT_SECONDS` | `30` (default; raise if sandbox responses are slow) | `30` (default) |

`SELCOM_BUSINESS_MODE=mock` also exists, but is **local-development-only**
and enforced as such: `get_selcom_business_client()` raises
`SelcomBusinessMisconfiguredError` if `SELCOM_BUSINESS_MODE=mock` while
`ENVIRONMENT` is anything other than `development` — a stray mock setting
can no longer silently fake a real merchant payout as "successful" in a
deployed sandbox/production Railway environment. See "Rolling back" below
for what to do instead if a deployed environment needs withdrawal payouts
paused.

### Sandbox setup

1. Generate sandbox test credentials from the Selcom developer portal — an
   API key plus an RSA key pair (keep the private key; provide the public
   key to Selcom per their onboarding instructions).
2. Set the **Sandbox** column of the table above in Railway's environment
   variables (or locally in `apps/api/.env`, git-ignored, for development
   against Selcom's real sandbox — not the same as
   `SELCOM_BUSINESS_MODE=mock`, which never calls Selcom at all).
3. Confirm Railway's static outbound IP (steps 2–4 near the top of this
   document) has already been sent to Selcom for whitelisting — sandbox
   enforces the same source-IP allowlist as production.
4. Test a full withdrawal round-trip against the real sandbox: submit a
   withdrawal (`POST /v1/merchant/withdrawals` — stays
   `PENDING_ADMIN_APPROVAL`, never touches Selcom), then approve it as a
   Super Admin (`POST /v1/admin/withdrawals/{id}/approve` — the one and
   only call site that reaches Selcom; see "Withdrawal approval flow"
   below). Confirm the response shape `app/services/selcom_business/parsing.py`
   expects actually matches what sandbox returns — see "Selcom readiness"
   below for exactly what's unverified.

### Production setup

Once Selcom issues live credentials for your production account, set the
**Production** column of the table above in Railway. **Never** set any
`SELCOM_BUSINESS_*` variable in Vercel/`apps/web`. Confirm what Railway
actually has configured (without exposing the secret values) via
`GET /v1/system/selcom-config-status`'s `business_*` fields. Do not switch
`SELCOM_BUSINESS_MODE=live` until a real sandbox round-trip has confirmed
the response parsing is correct (see "Selcom readiness" below).

### Selcom credential placement

- `SELCOM_BUSINESS_API_KEY`, `SELCOM_BUSINESS_PRIVATE_KEY_BASE64`,
  `SELCOM_BUSINESS_ACCOUNT_NUMBER` live in Railway environment variables on
  the `apps/api` service only.
- Never commit them to the repo — `apps/api/.env` is git-ignored; use it
  only for a local sandbox test, never for production credentials.
- Never in `apps/web`/Vercel or any frontend/client-side code path — the
  frontend only ever calls `apps/api`, which is the sole caller of Selcom
  (see "Architecture recap" above).
- The private key is read once per request from
  `SELCOM_BUSINESS_PRIVATE_KEY_BASE64`, base64-decoded, and loaded as a PEM
  RSA private key (`app/services/selcom_business/signing.py`). It is never
  logged, never returned in an API response, and never persisted to the
  database — `app/services/selcom_business/live_client.py` only ever logs
  `path`/`status`/`latency_ms`, never the request body, headers, API key,
  private key, or a raw recipient account number.

### Withdrawal approval flow

1. Merchant submits a withdrawal (`POST /v1/merchant/withdrawals`) — this
   creates a `disbursements` row with `status: PENDING_ADMIN_APPROVAL` and
   **never calls Selcom**. The fee breakdown is calculated once and frozen
   onto the row at this point (`pricing_snapshot_json`).
2. A Super Admin reviews the pending withdrawal in the console and clicks
   **Approve** (`POST /v1/admin/withdrawals/{id}/approve`) — this is the
   only code path anywhere in the codebase that calls
   `get_selcom_business_client().process_transaction(...)`. Rejecting
   (`.../reject`) or requesting more information (`.../request-info`)
   never reaches Selcom.
3. On approval: funds are reserved from the merchant's wallet first (atomic
   ledger entries), then Selcom is called. Selcom's `transId`, `receipt`,
   `status`, and the full raw response body are stored on the disbursement
   row (`selcom_trans_id` / `selcom_receipt` / `selcom_status` /
   `selcom_raw_response`) whenever a real response was received, regardless
   of outcome — kept for support/reconciliation debugging even when the
   parsed fields alone don't explain what happened.
4. Outcomes:
   - **Success** → `status: SUCCESS`, funds stay debited, merchant notified.
   - **Clean failure** (Selcom rejects the payout) → funds reversed,
     `status: FAILED`, merchant notified.
   - **Processing** (Selcom hasn't resolved synchronously) → `status:
     PROCESSING`; a Super Admin later calls
     `POST /v1/admin/withdrawals/{id}/refresh-status` to poll
     `transaction/query` and resolve it. Not automatic — no background
     worker exists in this codebase.
   - **Ambiguous** response → `status: NEEDS_RECONCILIATION`, funds stay
     reserved (not reversed — we don't yet know the payout didn't happen)
     pending manual refresh/investigation.
   - **IP not whitelisted** (HTTP 403 and/or Selcom's own error code 611 —
     see below) → `status: BLOCKED_IP_WHITELIST`, funds stay reserved (an
     operator/network problem, not a payout failure).
   - **Outright provider failure** (timeout/connection error/other HTTP
     error) → funds reversed, `status: FAILED`.

### If Selcom returns error 611 / HTTP 403 (IP not whitelisted)

Same static-IP requirement as the checkout API above — Selcom whitelists
this API by source IP too. `app/services/selcom_business/live_client.py`
detects this from **either** signal — an HTTP 403 status, or Selcom's own
error code `611` appearing in the response body under a `code` /
`errorCode` / `resultcode` field, regardless of HTTP status — and raises
`SelcomAPIError(is_ip_whitelist_error=True)`, which
`app/services/disbursements.py` routes to `BLOCKED_IP_WHITELIST` instead of
treating it as a normal payout failure (deliberately *not* just "any HTTP
403", since a bare 403 could also mean a bad API key). If sandbox or
production calls come back this way, follow steps 2–4 near the top of
this document (enable Railway Static Outbound IP, copy it, send it to
Selcom) — the withdrawal itself is fine; this backend's outbound IP just
isn't whitelisted yet. A withdrawal that hits this doesn't lose its
reserved funds — retry via the Super Admin console's refresh action once
whitelisting is confirmed.

### Phone number format

Wallet/mobile-money destinations (`MOBILE_MONEY`, `SELCOM_PESA`) are
normalized to **`255XXXXXXXXX`** — country code `255`, no leading `+`, no
leading `0` — by `app/core/phone.py::normalize_tz_phone()`, both at
withdrawal submission (`PhoneDisbursementRequest`'s validator) and again at
approval time as defense-in-depth (data isn't assumed immutable between the
two). **Bank account numbers (`BANK_ACCOUNT`, `destination_identifier` with
a `bank_name`) are never run through phone normalization** at either point
— they reach Selcom exactly as the merchant entered them.

### Selcom readiness — what's confirmed vs. still unverified

- **Confirmed**: RSA-SHA256 signing shape, request field names, and
  endpoint paths (`transId` / `recipientFiCode` / `recipientAccount` /
  etc. for `POST /transaction/process`, `GET /transaction/query`,
  `GET /account/lookup`, `POST /balance`) — sourced directly from
  developer.selcom.business's own current documentation, not guessed.
- **Not yet confirmed — response body field names.** Selcom's docs didn't
  show a full example response, so `app/services/selcom_business/parsing.py`
  guesses at reasonable, industry-standard field names
  (`status` / `transactionStatus` / `result` for the outcome;
  `transId` / `transactionId` / `reference` for the transaction id;
  `receipt` / `receiptNumber` / `selcomReceipt` for the receipt). **Verify
  this against a real sandbox transaction before ever setting
  `SELCOM_BUSINESS_MODE=live`** — if the real field names differ, a
  successful payout could be misparsed as `ambiguous`/`failed`.
- **Implemented but not yet wired into the approval flow**:
  `SelcomBusinessClient.account_lookup()` (recipient name/account
  verification) and `.balance()` (account balance check) both exist and
  are directly callable, but `_reserve_and_run_disbursement_provider` only
  calls `process_transaction`/`query_transaction` today — available for a
  future pre-payout recipient-verification or balance-reconciliation step.
- **Blocked on Selcom**: no real sandbox round-trip has been exercised yet
  — this integration is waiting on Selcom to issue sandbox test
  credentials (API key + RSA key pair). Everything above is exercised
  against a fake HTTP layer instead (`tests/test_selcom_business_client.py`,
  `tests/test_admin_withdrawals.py`), which proves the signing/error-
  handling/state-machine logic is correct in isolation but cannot prove
  Selcom's actual response shape matches `parsing.py`'s guesses.

## Rolling back

Checkout API: set `SELCOM_MODE=mock` (and `SELCOM_COLLECTION_ENABLED` back
to `false`) in Railway and redeploy — every collection immediately goes
back through `MockSelcomClient`.

Business Disbursement API: **`SELCOM_BUSINESS_MODE=mock` is no longer a
valid rollback in a deployed environment.** `get_selcom_business_client()`
raises `SelcomBusinessMisconfiguredError` unless `ENVIRONMENT=development`,
specifically so a stray mock-mode setting can never silently fake a real
merchant payout as "successful" in sandbox or production. To pause
withdrawal payouts in a deployed environment instead: stop approving
pending withdrawals in the Super Admin console — they stay safely
`PENDING_ADMIN_APPROVAL` (nothing times out or auto-approves) — or
temporarily revoke the Super Admin role from whoever would otherwise
approve them. This is a deliberate process-level pause, not a code/env-var
switch.
