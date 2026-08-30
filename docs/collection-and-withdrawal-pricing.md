# Collection & Withdrawal Pricing (MVP policy)

**Merchant charges apply to collections only. Withdrawals do not charge
merchant fees during MVP. Any provider disbursement cost is treated as
an internal platform cost unless a future policy changes this.**

Effective 2026-08-31. Applies going forward only — historical
withdrawals that already stored a non-zero fee (before this date) are
untouched; nothing was rewritten. See
[`docs/withdrawal-pricing-and-approval.md`](./withdrawal-pricing-and-approval.md)
for how withdrawal pricing worked before this change, and for the
still-current approval-flow/status-glossary/Selcom-sequencing mechanics,
which this change didn't touch.

## Collections — unchanged

Every collection flow (Request Collection, Wallet Push, Push to Selcom
Pesa, TanQR, Payment Links, [Pay by Link](./PAY_BY_LINK.md), Invoices,
Merchant API collections) computes its fee the same way it always has,
through the single shared chokepoint
`app/services/collections.py::create_processing_transaction`:

```
fee_amount = gross_amount * settings.platform_fee_percentage / 100
net_amount = gross_amount - fee_amount
```

`settings.platform_fee_percentage` (`PLATFORM_FEE_PERCENTAGE` env var,
default `1.5`) is a single flat platform-wide rate — not per-merchant,
and not read from `merchant_pricing_rules` (that table has never driven
collection fees; it was, and is, a withdrawal-specific mechanism — see
below). This computation was not changed by this policy update; it's
documented here because this file is the "what does a merchant actually
pay" reference, not because anything about it moved.

## Withdrawals — fees removed

`app/services/withdrawals/fee_calculator.py::calculate_withdrawal_fee`
now unconditionally returns a zero-fee breakdown:

```
percentage_fee = 0
flat_fee = 0
infinity_fee = 0
processor_charge = 0          (processor_fee_pass_through is never applied)
total_charges = 0
total_reserved_amount = amount     (== the requested withdrawal amount)
recipient_net_amount = amount
```

This is unconditional — it does not consult `merchant_pricing_rules` at
all, so a merchant-specific or platform-fallback rule configured there
(even a real, non-zero one, e.g. left over from before this date) has no
effect. A withdrawal always reserves and debits the merchant's wallet
for exactly the amount they requested, subject only to available
balance, min/max/daily withdrawal limits, and Super Admin approval —
none of which this change touched.

`merchant_pricing_rules` and its precedence lookup
(`find_pricing_rule`) are **not dead code** — they're still used as a
production-API-key-eligibility gate
(`app/services/api_access.py::has_resolvable_pricing_rule` — "has this
merchant been assigned pricing at all"), which is unrelated to fee
amounts. The Super Admin "Pricing Rules" page
(`/super-admin/pricing-rules`) still edits this same table for that
reason, but is now labeled inactive for withdrawal-fee purposes — see
its own on-page notice.

### If a real provider disbursement cost needs tracking later

Selcom (or any future payout provider) may charge Infinity Africa a real
cost per payout. That cost is an **internal platform cost** — it must
never be deducted from what a merchant receives unless a deliberate,
separate future policy change says otherwise. Nothing in this codebase
currently records that cost anywhere (no field, no table); building that
tracking is explicitly out of scope for this change and intentionally
not stubbed in, to avoid a half-built, silently-unused mechanism.

## Why this split is safe

- Every collection-crediting path and every withdrawal-debiting path was
  already independently reviewed for wallet-ledger safety (see
  [`docs/MVP_30_TO_100_MERCHANT_READINESS.md`](./MVP_30_TO_100_MERCHANT_READINESS.md)
  §4/§5) — this change only replaces the *number* `calculate_withdrawal_fee`
  returns; it doesn't touch how or when a wallet is credited or debited.
- `total_reserved_amount` (what gets checked against available balance
  and what gets debited on approval) and `recipient_net_amount` (what
  the merchant sees as "you'll receive") both derive from the same
  `FeeBreakdown` — making them equal to `amount` was a one-function
  change, not two changes that could drift out of sync.
- No historical `disbursements` row was rewritten — a withdrawal
  submitted before 2026-08-31 keeps whatever real fee it already
  reserved/debited; only new withdrawals use the zero-fee policy.
