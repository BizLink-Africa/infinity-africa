# Transactional email (Resend)

All outbound transactional email goes through [Resend](https://resend.com),
via `app/services/email.py`. `RESEND_API_KEY` is backend/Railway-only —
never set it in `apps/web`/Vercel, and nothing in `apps/web` imports this
module or reads that key.

## What's actually wired up today

Only **invoice payment-request emails** are implemented right now (see
`send_invoice_email` in `app/services/email.py`, called from
`POST /v1/invoices/{id}/send` and `POST /v1/merchant/invoices/{id}/send`).
An invoice is only ever marked `SENT` once that email has actually been
delivered — if Resend rejects the send, or `RESEND_API_KEY` isn't
configured, the invoice stays in its previous status and the caller gets a
clear `email_delivery_failed` error. Every attempt — success or failure —
is logged to the `email_deliveries` table (`app/services/email.py::_log_delivery`),
which Super Admin's Invoices list surfaces (delivery status, provider
message id, failure reason).

## Sender addresses

Two senders, chosen by email type — not configurable per-email, only per
deployment:

| Email type | Sender | Env var |
| --- | --- | --- |
| Invoice payment requests | `Infinity Africa Invoices <invoice@infinityafrica.net>` | `INVOICE_EMAIL_FROM` |
| Everything else (staff invites, password resets, payment receipts, welcome emails, inquiry notifications) | `Infinity Africa <notification@infinityafrica.net>` | `EMAIL_FROM` |

If `INVOICE_EMAIL_FROM` isn't set, invoice emails fall back to whatever
`EMAIL_FROM` is set to (see `Settings.invoice_email_from` in
`app/config/settings.py`) — a deployment that forgets to set the
invoice-specific sender still sends *something* sane rather than failing
outright.

**Only invoice payment-request emails are built today.** The other four
email types in the table above (staff invites, password resets, receipts,
welcome emails, inquiry notifications) don't exist as features yet — the
sender convention is documented here ahead of time so whoever builds them
next doesn't have to guess which address to use, and so they log through
the same `email_deliveries` table via `email.py`'s existing helpers
(`send_email` for the raw send, a `_log_delivery`-shaped call for the
audit row).

## Required Railway/backend env vars

```
RESEND_API_KEY=                                                    # backend-only, never in Vercel
EMAIL_FROM="Infinity Africa <notification@infinityafrica.net>"
INVOICE_EMAIL_FROM="Infinity Africa Invoices <invoice@infinityafrica.net>"
EMAIL_REPLY_TO="support@infinityafrica.net"
CEO_EMAIL="ceo@infinityafrica.net"                                 # reserved — no inquiry-notification feature exists yet
APP_URL="https://infinityafrica.net"
```

`APP_URL` is distinct from the existing `PUBLIC_APP_URL` — `PUBLIC_APP_URL`
specifically builds the `/pay/{slug}` payment-link URL
(`app/services/payment_links.py::build_public_url`) and is untouched by
this feature; `APP_URL` (`Settings.app_url`, falls back to
`PUBLIC_APP_URL` when unset) is a general site base URL available for
email templates that need one, distinct from the payment-link builder so
neither has to guess the other's intent.

## Safety notes

- The Resend API key is never logged, never included in an error message
  returned to a client, and never printed. `send_email`'s exception
  handler logs the *provider's* exception server-side only; the message
  raised to callers is a fixed, safe string.
- `email_deliveries` never stores an email body — only metadata (sender,
  recipient, subject, provider message id, status, failure reason).
- An invoice email is a **payment request**, never a receipt — it must
  never be sent (and today, never is) in response to a successful
  payment. Receipts are a distinct, not-yet-built feature that will use
  `EMAIL_FROM`/`notification@infinityafrica.net` per the table above.
- Password reset / invite emails must never carry a plaintext password —
  not relevant to the invoice flow, but binding on whatever implements
  those two email types next.
