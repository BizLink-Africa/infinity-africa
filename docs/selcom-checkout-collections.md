# Selcom Checkout Collections — Wallet Push, Webhook & Reconciliation

The full Push STK/USSD ("Mobile Money Push") flow for a customer paying
a payment link: create an order shell, trigger a real push, then
resolve the outcome via webhook or manual refresh — and only then credit
the merchant. For the general pricing/withdrawal-side approval flow see
[`docs/withdrawal-pricing-and-approval.md`](./withdrawal-pricing-and-approval.md);
for the Selcom Checkout signing scheme itself see the module docstrings
in `apps/api/app/services/selcom_checkout/`.

## The flow

```
customer submits phone
        │
        ▼
POST /public/payment-links/{slug}/pay/wallet-push
        │
        ├─ create-order-minimal  (order shell — never charges anyone)
        │
        └─ wallet-payment        (the real push — the one call that can move money)
        │
        ▼
collection created, status = "processing"  (never "successful" here)
        │
   ┌────┴────┐
   ▼         ▼
webhook   manual refresh (merchant/admin "Refresh status")
   │         │
   └────┬────┘
        ▼
complete_checkout_collection_once()
        │
        ▼
resolve_collection()  ← the credit rule is enforced here, once
```

Both resolution paths (webhook and manual refresh) go through the exact
same function — see "Shared completion / idempotency" below. Neither
`create_order_minimal()` nor `process_wallet_payment()` ever credits a
merchant directly; `app/services/wallet_push.py`'s own module docstring
explains why the collection created there is capped at `"processing"`,
never `"successful"`.

## Webhook endpoint

```
POST /v1/webhooks/selcom/checkout
GET  /v1/webhooks/selcom/checkout   (reachability probe only — Selcom's
                                     portal "Test URL" check; carries no
                                     data, verifies nothing)
```

Distinct from the older `/v1/webhooks/selcom` (a different, unconfirmed
placeholder product — see `docs/selcom-live-go-live.md`). Every delivery
is logged to `selcom_webhook_events` (`provider = "selcom_checkout"`)
before signature verification even runs, so the very first real delivery
can be inspected regardless of whether verification passed. As of
2026-08-23 a safe, secret-free log line (`order_id`/`transid`/`reference`/
`payment_status` only — never `Timestamp`/`Digest`/`Digest-Method`, since
those are the signature material itself) is also emitted before
verification, for the same reason.

### Exact URL to register with Selcom

```
https://web-production-3fdc4a.up.railway.app/v1/webhooks/selcom/checkout
```

This is the **verified-live, currently-reachable** URL (confirmed via a
real `GET` reachability check returning `{"status": "ok"}`). Do **not**
register `https://api.infinityafrica.net/...` — as of 2026-08-22/23 that
subdomain does **not resolve at all** (confirmed NXDOMAIN via `nslookup`
and curl), despite being referenced as the "production" domain in both
`apps/api/.env.example` and `apps/web/.env.example`. That stale
documentation is the leading suspect for why no real webhook delivery
has ever arrived (see "Known gaps" below) — if Selcom's account was ever
configured with that URL, delivery would silently fail on their end
regardless of anything this codebase does. If/when a stable custom
domain is set up and DNS-verified, update this doc, both `.env.example`
files, and re-register the new URL with Selcom.

### Selcom account configuration required

Two independent things must both be true for a real delivery to ever
arrive — confirming one does not imply the other:

1. **Our side sends the callback URL on order creation.** Every
   `create-order-minimal` call now includes a `webhook` field (base64
   encoded per Selcom's docs) whenever `SELCOM_CHECKOUT_WEBHOOK_URL` is
   set — see `app/services/checkout_orders.py::create_checkout_order_minimal()`.
   **This was NOT happening before 2026-08-23** — the client method
   (`SelcomCheckoutHTTPClient.create_order_minimal()`) always supported a
   `webhook` parameter, but the one real production call site never
   passed it, so Selcom was never told where to deliver a callback for
   any order, ever, independent of the DNS issue above. This is now
   fixed.
2. **Selcom's own Merchant Portal callback setting**, if their platform
   also requires (or additionally uses) a portal-level, account-wide
   callback URL rather than trusting the per-order `webhook` field —
   confirm with Selcom support which applies to this account. Set it to
   the exact same URL above.

### Railway env var

```
SELCOM_CHECKOUT_WEBHOOK_URL=https://web-production-3fdc4a.up.railway.app/v1/webhooks/selcom/checkout
```

Backend/Railway only — never set in `apps/web`/Vercel (it's not a
secret, but it's a backend implementation detail with no frontend use).
Left blank, no `webhook` field is sent to Selcom at all — a deliberate,
safe default: reconciliation still works via the manual refresh
endpoints below, it just relies on nobody ever calling this app back.

Expected payload fields (per the reconciliation task brief — field
names not yet independently re-verified against a live delivery the way
`create-order-minimal` was):

| Field | Notes |
|---|---|
| `transid` | The value this backend generated at wallet-payment time — the precise match key |
| `order_id` | Fallback match key if `transid` isn't found |
| `reference` | Selcom's own reference |
| `result` | e.g. `"SUCCESS"` |
| `resultcode` | e.g. `"000"` |
| `payment_status` | The authoritative completion signal — see below |
| `channel` | Optional — which telco/PSP handled it |
| `amount`, `phone` | Optional, not persisted from the webhook itself |

## Signature verification

**Inferred, not yet confirmed against a real delivery.** The docs page
for the webhook-callback section truncates before showing the actual
header names/scheme (same issue affecting every still-unconfirmed
Checkout endpoint). `verify_webhook_signature()`
(`apps/api/app/services/selcom_checkout/signer.py`) mirrors the one
signing scheme that *is* confirmed for this product — the outbound
request signing (`build_auth_headers`) — in the opposite direction:

- Selcom is assumed to send `Digest-Method` / `Digest` / `Timestamp` /
  `Signed-Fields` headers on the callback, computed the same way as
  outbound requests: `HMAC-SHA256("timestamp=<ts>&field1=value1&...")`,
  keyed with the same shared `SELCOM_CHECKOUT_API_SECRET`.
- `Signed-Fields` for this endpoint: `transid,order_id,reference,result,resultcode,payment_status`.
- Only `HS256` is supported — verifying `RS256` would need Selcom's
  *public* key, which this account's configuration doesn't have (our
  `SELCOM_CHECKOUT_PRIVATE_KEY_BASE64`, if ever set, is only ever *our*
  key for outbound RS256 signing).
- Fails closed on anything missing/malformed — never guesses in the
  caller's favor, because a webhook this code accepts is what actually
  moves money.

**Confirm this against the first real delivery** by checking
`selcom_webhook_events.raw_body`/`signature_valid` once one arrives —
if verification is consistently failing on genuine deliveries, that's
the signal this inference needs correcting, not a reason to weaken it.

Independent of whether the webhook verification is right: the manual
refresh endpoints below never receive anything from Selcom, they only
call it, so they keep working regardless.

## Order status query

```
GET /v1/checkout/order-status?order_id={order_id}
Signed-Fields: order_id
```

`get_order_status()` on `SelcomCheckoutHTTPClient` — read-only, never
changes anything on Selcom's side. Used by both manual refresh
endpoints. Response `data[0].payment_status` is the same authoritative
field the webhook carries; `data[0].transid`/`channel`/`reference` are
folded into the collection the same way a webhook delivery would be.

## Manual refresh (independent of the webhook)

```
POST /v1/merchant/collections/{id}/refresh-status   (merchant-scoped)
POST /v1/admin/collections/{id}/refresh-status       (Super Admin, any merchant)
```

Both call `get_order_status()` then apply the exact same completion
logic the webhook uses. This is a fully independent path — even if the
webhook signature inference above turns out wrong and every real
delivery gets rejected, a merchant or admin can still reconcile a
payment by clicking refresh. Never double-credits (see idempotency
below).

## Completion rule — when a merchant actually gets credited

A collection is only ever resolved `"successful"` — and therefore only
ever credited — when **all three** agree:

```
result      == "SUCCESS"
resultcode  == "000"
payment_status == "COMPLETED"
```

`payment_status == "COMPLETED"` alone, without `result`/`resultcode`
agreeing, is **not** credited and **not** marked failed — that
combination is treated as corrupted/suspicious input, not a normal
outcome, and the safe response is to leave the collection `"processing"`
(unresolved, still refreshable) rather than guess. This mapping lives in
one place: `app/services/checkout_reconciliation.py::map_checkout_status_to_provider_status`.

### Status mappings

| Selcom `payment_status` | Internal status | Credited? |
|---|---|---|
| `COMPLETED` (+ result/resultcode agree) | `successful` | **Yes** |
| `COMPLETED` (result/resultcode disagree) | `processing` | No — stays open |
| `PENDING` | `processing` | No |
| `INPROGRESS` | `processing` | No |
| `CANCELLED` | `failed` | No |
| `USERCANCELLED` | `failed` | No |
| `REJECTED` | `failed` | No |
| *(no payment_status yet — bare wallet-payment result)* | falls back to `resultcode`: `000`→successful, `111`/`927`→processing, `999`→processing (ambiguous, never a silent failure), else→failed | per mapping |

## Shared completion / idempotency

`app/services/checkout_reconciliation.py::complete_checkout_collection_once()`
is the one function both the webhook and both refresh endpoints call.
It doesn't reimplement crediting — it reuses
`app/services/collections.py::resolve_collection()`, which was already
idempotent (a no-op once a collection is no longer `"processing"`),
already posts ledger entries exactly once, already marks a linked
`payment_link` `PAID` and a linked `invoice` `PAID`/`PARTIALLY_PAID`.

What `complete_checkout_collection_once()` adds on top:

1. Always refreshes audit fields (`provider_reference`, `provider_transid`,
   `provider_result`, `provider_resultcode`, `provider_payment_status`,
   `channel`, `raw_response`) — even on a repeat call, so a later
   delivery's data is never lost even once the outcome can't change
   anymore.
2. Captures whether the collection was still `"processing"` **before**
   calling `resolve_collection()` — this is what stops a duplicate
   webhook/refresh from re-notifying the merchant or re-marking the
   linked `checkout_orders` row `"completed"`, even though the ledger
   itself was already safe via `resolve_collection()`'s own guard.
3. On a genuine (not duplicate) success: marks the linked
   `checkout_orders` row `"completed"` and sends a `payment_received`
   notification to the merchant.

Both `provider_transid`-based matching (the precise key — unique per
wallet-payment attempt) and a `checkout_orders.order_id` fallback exist
(`find_collection_by_transid` / `find_collection_by_order_id`), so a
delivery missing one still resolves via the other.

## Merchant/admin/customer visibility

- **Merchant portal** — `GET /v1/merchant/collections` now includes
  `checkout_order_id`, `provider_transid`, `provider_resultcode`,
  `provider_result`, `provider_payment_status`, `channel`,
  `failure_reason`.
- **Super Admin** — `GET /v1/admin/collections` additionally surfaces
  `order_id` (joined from the linked `checkout_orders` row).
- **Customer payment page** — polls
  `GET /public/payment-links/{slug}/collections/{collection_id}/status`,
  which maps the collection's status to one of: `pending`, `completed`,
  `failed`, `cancelled`, `user_cancelled`, `rejected` — never the
  payment link's own status (which only ever reflects `PAID` once, with
  no per-attempt detail).

## How to confirm a webhook actually arrives

1. Check `selcom_webhook_events` for a row where `provider =
   'selcom_checkout'` — its existence alone confirms delivery reached
   this backend, independent of whether signature verification passed.
   As of 2026-08-22 this table has **zero** such rows in production —
   see "Known gaps" below.
2. Check the collection's `status` — `successful` means it was fully
   resolved and credited; `processing` means either nothing arrived yet
   or `payment_status` wasn't yet `COMPLETED`.
3. Check the merchant's ledger/wallet balance actually moved by the net
   amount (gross minus platform fee) — the definitive confirmation that
   crediting happened, not just that a row changed status.
4. The safe log line (`selcom_checkout webhook received: order_id=...
   transid=... reference=... payment_status=...`, `app/routers/
   webhooks.py`) is visible in Railway's logs the instant a delivery
   lands, before signature verification even runs.

**If no webhook arrives** (this has been the case for every real
transaction so far): use the manual refresh endpoints —
`POST /v1/merchant/collections/{id}/refresh-status` or
`POST /v1/admin/collections/{id}/refresh-status` — which query Selcom
directly via `get_order_status()` and apply the identical completion
logic. If refresh also never resolves a collection past `PENDING` after
a customer has genuinely paid, that's a signal to contact Selcom/support
directly to confirm: (a) the callback URL is correctly registered on
their side for this account, and (b) their systems have actually
attempted delivery (ask for their own delivery logs/attempts for a
specific `order_id`/`transid`).

## Known gaps / what to verify once real traffic exists

- **Webhook delivery has never fired, not even once, as of 2026-08-22**
  — confirmed by a completely empty `selcom_webhook_events` table for
  `provider = 'selcom_checkout'` after a real, fully-paid, real-money
  live transaction (order `ORD-20260822-ECA39908`, resolved instead via
  manual refresh). Two root causes identified and fixed the same day:
  the per-order `webhook` field was never being sent (see above), and
  the documented "production" API domain (`api.infinityafrica.net`)
  doesn't resolve at all. Whether a real delivery arrives now that both
  are fixed is still unconfirmed — needs a fresh live transaction to
  test, plus Selcom's own account-level callback URL confirmed (see
  above).
- Webhook signature scheme itself is still inferred, not confirmed (see
  above) — moot until a delivery actually arrives to test it against.
- `get-order-status`'s exact response field names came from the task
  brief, not an independently re-verified live call the way
  `create-order-minimal` was — see
  `apps/api/app/services/selcom_checkout/parsing.py`'s module docstring.
  (The live test on 2026-08-22 did confirm `payment_status`, `transid`,
  `channel` — `MPESA-TZ` — and `reference` all come back exactly as
  expected.)
- `collections.method` stores `"STK_PUSH"` for every wallet-push
  collection regardless of which real channel Selcom actually used —
  a labeling simplification (Selcom's wallet-payment call takes no
  channel parameter at all), not a claim about the real channel. The
  real channel Selcom reports is kept separately in `collections.channel`.
