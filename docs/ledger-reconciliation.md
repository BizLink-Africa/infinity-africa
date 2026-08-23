# Ledger Reconciliation — Crediting, Reversal, and Review

How money actually moves into (and, when a payment turns out to have
been wrong, back out of) a merchant's wallet. Written after the
2026-08-23 incident where a wallet-push collection was credited then
later reversed by Selcom with nothing in this codebase able to react —
see `docs/selcom-checkout-collections.md`'s "Reversal after credit"
section for the collections-specific detail this doc assumes.

## The core rule

**A provider accepting a push/order request is not the same as a
payment being final.** Selcom's own stated rule for wallet-payment: a
success response only means the wallet provider accepted the push
request, not that the customer's wallet was finally debited or that
funds are settled. Every collection method in this codebase (USSD_PUSH,
STK_PUSH, SELCOM_PESA_PUSH, wallet-push via Selcom Checkout, Dynamic QR)
follows the same shape: the initiating call always leaves the collection
`"processing"`, never `"successful"` — see `app/services/wallet_push.py`
and `app/services/collections.py::initiate_collection()`'s own
docstrings. Only a *separate* resolution signal (webhook, manual
refresh, or the older mock callback) can move a collection to
`"successful"`, via `app/services/collections.py::resolve_collection()`.

## Why a webhook alone is not enough

A webhook delivery is the fastest resolution signal, but not a
sufficient one on its own, for two independent reasons proven in this
codebase:

1. **It might never arrive at all.** Every real production payment so
   far has resolved via manual refresh, not the webhook — see
   `docs/selcom-checkout-collections.md`'s "Known gaps" section. Manual
   refresh (`get_order_status()`) is a fully independent path that
   queries Selcom directly rather than waiting to be called back, and
   both paths converge on the exact same completion logic
   (`complete_checkout_collection_once()`), so neither can diverge from
   the other's credit rule.
2. **A single "success" webhook does not rule out a later reversal.**
   This is the 2026-08-23 incident exactly: Selcom's webhook/order-status
   can report `COMPLETED` and then, on a *later* call, report the
   payment actually failed/reversed — sometimes only visible in free-text
   `message` content (`"Payment unsuccessful. You are trying to pay into
   your own till"`), not a clean coded status. Reconciliation is
   therefore not "did a webhook fire" but "does the most recent signal —
   webhook or refresh, whichever arrived last — still agree with what we
   already recorded." `reverse_successful_collection()` exists
   specifically to handle the case where it doesn't.

## Crediting: post_collection_entries

`app/services/ledger.py::post_collection_entries()` is the only function
that ever credits a merchant wallet for a collection. Double-entry,
balanced within a single call:

```
debit  settlement_clearing   gross_amount
credit merchant_wallet       net_amount
credit platform_revenue      fee_amount   (only if fee_amount > 0)
```

Posted via the `post_ledger_entries` Postgres RPC
(`supabase/migrations/20260814140001_post_ledger_entries_balance_check.sql`),
which atomically enforces debits == credits per `transaction_id` **and**
atomically rejects any batch that would take a `merchant_wallet` balance
negative — raising `InsufficientBalanceError`
(`app/core/errors.py`). This guard is what makes a wallet negative
balance structurally impossible, not application-level bookkeeping.

Called from exactly two places:

- `resolve_collection()` — the normal path, once a collection resolves
  `"successful"` for the first time.
- `finalize_pending_review_collection()` — the self-payment/own-till
  review path (see below): the same posting, just gated behind an admin
  clearing the hold instead of happening automatically.

## Reversal: reverse_collection_entries

`app/services/ledger.py::reverse_collection_entries()` is the exact
opposite of `post_collection_entries()`, posted against the **same**
`transaction_id`:

```
debit  merchant_wallet       net_amount
debit  platform_revenue      fee_amount   (only if fee_amount > 0)
credit settlement_clearing   gross_amount
```

Same convention as the existing, already-proven
`reverse_disbursement_entries()` (withdrawals) — a new set of entries
against the original transaction, never editing or deleting the
original ones. `debit net_amount + debit fee_amount == credit
gross_amount` by construction (`gross = net + fee`), so each reversal
call balances independently of the original posting.

**This direction can raise `InsufficientBalanceError`** — unlike a
disbursement reversal (which only ever credits the wallet back), a
collection reversal *debits* the wallet, and the merchant may have
already withdrawn the funds. The database blocks the whole batch
atomically rather than partially clawing back what's left.
`reverse_successful_collection()` (`app/services/collections.py`) is
the only caller, and it catches this explicitly:

- **Balance available**: reversal posts cleanly, transaction and
  collection both move to `"reversed"`.
- **Balance insufficient**: the ledger reversal is skipped (nothing
  posts — the RPC is all-or-nothing), the collection still moves to
  `"reversed"` (so no UI keeps claiming success for money that's
  actually gone), and a **CRITICAL** admin notification is raised
  naming the merchant, amount, and currency for manual recovery
  (e.g. netting against a future payout, direct follow-up with the
  merchant). This is a deliberate "make it visible, don't hide it"
  choice — the alternative of silently leaving the collection
  `"successful"` is exactly the bug this whole fix responds to.

Guarded by requiring `status == "successful"` on entry — reversing an
already-`"reversed"` collection is a safe no-op, so a retried/duplicate
reversal signal can never double-reverse or drive the wallet further
negative.

## Self-payment / own-till: held before crediting

Reversal handling is a response *after* the fact. The self-payment/
own-till fraud rule (`SELF_PAYMENT_OWN_TILL`,
`app/services/fraud_monitoring_service.py::check_self_payment_risk()`)
is the one gate that runs *before* `resolve_collection()` would
otherwise credit: if the payer's phone matches the merchant's own
`contact_phone`, the collection is held `pending_review` instead —
no ledger entries posted, no `payment_link`/`invoice` marked `PAID` —
until a Super Admin clears the resulting fraud alert. See
`docs/selcom-checkout-collections.md`'s "Self-payment / own-till risk"
section for the full flow. This directly matches the live incident's
own root cause on Selcom's side ("trying to pay into your own till").

## Why full delayed clearance isn't wired up

The task that motivated this doc suggested a broader "hold every
collection briefly, recheck, then move to available balance" clearance
gate (`COLLECTION_AUTO_SETTLE_ENABLED` /
`COLLECTION_CLEARANCE_DELAY_MINUTES`, both in `app/config/settings.py`,
both reserved/unused). It was deliberately **not** implemented as a
blanket gate on every collection, for a concrete reason: this codebase
has no background worker or cron infrastructure at all (confirmed
elsewhere — see `app/services/disbursements.py::reconcile_pending_disbursements()`'s
own docstring, which is admin-button-triggered for the same reason), so
a time-based "recheck after N minutes" has nothing to actually perform
the recheck. Wiring the config flags without a real mechanism behind
them would create the appearance of a safety net that doesn't exist —
worse than being explicit that it doesn't exist yet.

The two safety nets that *are* real today — reversal handling and the
self-payment hold — together directly close the exact gap the live
incident exposed (crediting survives a later reversal; a known-risky
payer's phone never gets instant, unreviewable credit) without
depending on infrastructure this codebase doesn't have.

**If/when full delayed clearance is built**, the natural shape given
what exists now:

1. A real scheduling mechanism (cron, or a Railway-hosted worker) that
   can call something on a delay — none exists today, first prerequisite.
2. `resolve_collection()`'s success branch gated on
   `settings.collection_auto_settle_enabled`: when `False` (default),
   post to a new `pending_clearing` ledger purpose instead of
   `merchant_wallet` directly, exactly like `settlement_clearing`'s own
   asset-account pattern.
3. The scheduled recheck re-queries Selcom (`get_order_status()`, same
   call `refresh_checkout_collection_status()` already makes) and only
   then moves the net amount from `pending_clearing` to
   `merchant_wallet` — a third ledger function alongside
   `post_collection_entries()`/`reverse_collection_entries()`.
4. An admin "Finalize after recheck" action for the manual-override case,
   mirroring `finalize_pending_review_collection()`'s existing shape.

## Quick reference: what to check when a wallet balance looks wrong

1. `ledger_entries` for the merchant's wallet account
   (`app/services/ledger.py::list_wallet_ledger()`) — every credit/debit,
   newest first, with a computed running balance. The definitive source
   of truth; `ledger_accounts.balance` is only a cached total.
2. The linked `collections.status` — `successful` means credited and
   currently believed final; `reversed` means credited once, then
   clawed back (check `ledger_entries` for the matching reversing pair
   against the same `transaction_id`); `pending_review` means never
   credited, held on the self-payment rule.
3. `fraud_alerts` filtered to `rule_code = 'SELF_PAYMENT_OWN_TILL'` for
   review holds, or any `CRITICAL` alert with "manual recovery" in its
   `reason`/notification body for an insufficient-balance reversal
   shortfall.
4. `notifications` where `recipient_type = 'admin'` and
   `notification_type = 'collection_reversed'` — every reversal (clean
   or shortfall) notifies Super Admin, independent of the merchant's own
   notification.
