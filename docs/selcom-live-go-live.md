# Selcom Live Go-Live

How to move `apps/api` from the mock Selcom client to live Selcom API
calls. **Do not start this until you're ready to actually go live** — every
collection/disbursement flow (payment links, invoices, `/v1/collections/*`,
withdrawals) already works end-to-end today against
`app/services/selcom/mock_client.py`; nothing about the frontend, the
payment-link flow, or the customer payment page is blocked on this.

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

Leave `SELCOM_MODE=mock` and both `SELCOM_COLLECTION_ENABLED`/
`SELCOM_WITHDRAWAL_ENABLED` at `false` until the next step — adding
credentials alone doesn't switch anything over.

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
    "vendor_id_configured": true
  }
}
```

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
- The linked collection/disbursement and its transaction move out of
  `processing` correctly (`resolve_collection_from_callback`/
  `resolve_disbursement_from_callback` in
  `app/services/collections.py`/`app/services/disbursements.py`), ledger
  entries post on success, and a `payment_link`/`invoice` linked to a
  collection updates accordingly.

If Selcom's real callback payload shape differs from what
`app/routers/webhooks.py`/`app/schemas/webhooks.py` currently expect,
that's the other placeholder to fix before relying on this in production —
same caveat as `live_client.py`/`parsing.py` above.

## Rolling back

Set `SELCOM_MODE=mock` (and both `SELCOM_*_ENABLED` flags back to `false`)
in Railway and redeploy — every collection/disbursement immediately goes
back through `MockSelcomClient`. No code change, no data migration; this is
the same switch used throughout local development.
