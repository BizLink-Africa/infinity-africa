# Collections Production Go-Live Checklist

Verification checklist for enabling wallet-push Collections in production,
written after the 2026-08-23 incident and its fix (commit `bb041bc`,
`fix: prevent wallet push reversal from crediting merchant`). For the
mechanics themselves see
[`docs/selcom-checkout-collections.md`](./selcom-checkout-collections.md)
and [`docs/ledger-reconciliation.md`](./ledger-reconciliation.md); this
doc is the go/no-go checklist, not the explanation.

## 1. Pre-go-live checks

- [x] Root cause identified and fixed: `resolve_collection()`'s
      idempotency guard made a post-credit reversal unreachable — see
      `docs/ledger-reconciliation.md`
- [x] Migration `20260823030000_collection_reversal_and_self_payment_review.sql`
      applied to production Supabase (confirmed by user, 2026-08-23 —
      `alter table` + `insert` ran successfully, "Success. No rows
      returned")
- [x] Code fix deployed: commit `bb041bc` pushed to `origin/main`
      (`e9608fd..bb041bc`) — Railway/Vercel auto-deploy from `main`
- [x] Backend test suite green: `python -m pytest` — **598 passed**
      (587 pre-existing + 11 new regression tests for this exact
      incident, `apps/api/tests/test_collection_reversal.py`)
- [x] `python -m ruff check .` clean (one pre-existing, unrelated
      `app/routers/health.py` B008 warning, not touched by this fix)
- [x] `npm run lint --workspace=apps/web`, `npx tsc --noEmit`,
      `npm run build --workspace=apps/web` all clean
- [ ] Merchant Portal browser walkthrough (§4) — **pending**, checklist
      handed to the user 2026-08-23 (no browser-automation tool or
      merchant credentials available to this agent)
- [ ] Super Admin browser walkthrough (§4) — **pending**, same reason
- [ ] Controlled live wallet-push test (§5) — **not run**, requires
      explicit approval per the task brief that produced this checklist
- [ ] Controlled self-payment/own-till test (§6) — **not run**, same
      reason, and additionally gated on "only if it won't cause
      unnecessary fees"

## 2. What is and isn't covered by this fix

**Covered and tested:**

- Wallet-push API success (`resultcode=000`/PENDING) never credits —
  `app/services/wallet_push.py` never advances `collections.status`
  past `"processing"` itself; confirmed by
  `test_wallet_push_collection_never_credits_synchronously` and
  `test_wallet_push_collection_failed_push_recorded_not_502`.
- A collection already `"successful"` that later receives a
  `REVERSED`/failed/reversal-worded signal is reversed for real:
  ledger reversing entries posted, `payment_link`/`invoice` reopened,
  merchant + admin notified — `test_reversed_after_completed_reverses_ledger_and_wallet`,
  `test_reversal_reopens_linked_invoice_from_paid`,
  `test_reversal_message_marker_triggers_reversal_even_with_ambiguous_status`.
- Duplicate signals (repeat webhook, repeat manual refresh) never
  double-credit or double-reverse —
  `test_duplicate_completion_does_not_double_credit` (existing),
  `test_duplicate_reversal_signal_does_not_double_reverse`,
  `test_reversing_an_already_reversed_collection_is_a_noop`.
- A reversal that can't be fully clawed back (merchant already
  withdrew the funds) still marks the collection `"reversed"` and
  raises a CRITICAL admin alert rather than silently leaving it
  `"successful"` — `test_reversal_with_insufficient_balance_marks_reversed_and_alerts_admin`.
- Self-payment/own-till (payer phone == merchant's own `contact_phone`)
  holds the collection `pending_review` before any credit, ledger
  post, or `PAID` marking — `test_self_payment_phone_match_holds_pending_review_not_credited`,
  `test_self_payment_holds_linked_invoice_from_being_marked_paid`.
  A different phone still credits normally —
  `test_different_phone_from_merchant_credits_normally`.
- Clearing the resulting fraud alert (Super Admin) is the one place
  that then credits it, exactly once —
  `test_finalizing_pending_review_collection_credits_it_exactly_once`,
  `test_admin_clearing_self_payment_alert_finalizes_collection`.

**Not covered — by deliberate choice, not oversight:**

- **General delayed clearance for every collection** (hold *any*
  first-time `COMPLETED` briefly before crediting, then recheck) is
  **not implemented**. `COLLECTION_AUTO_SETTLE_ENABLED` /
  `COLLECTION_CLEARANCE_DELAY_MINUTES` exist in `app/config/settings.py`
  as reserved config, unused — this codebase has no background
  worker/cron infrastructure to actually perform a delayed recheck, and
  half-wiring the flags would create a false sense of safety. See
  `docs/ledger-reconciliation.md`'s "Why full delayed clearance isn't
  wired up" section for the reasoning and what a real implementation
  would need. **A normal (non-self-payment) collection that resolves
  `COMPLETED` is still credited immediately**, same as before this fix
  — the two safety nets that changed are reversal-after-credit and the
  self-payment hold, not a universal clearance delay.
- Reversal detection depends on a *second* signal arriving (webhook or
  manual refresh) after the first `COMPLETED` — if Selcom never sends
  one and nobody clicks refresh, a reversal that happened entirely on
  Selcom's side stays undetected here. Manual refresh remains the
  reliable path per `docs/selcom-checkout-collections.md`'s "Known
  gaps" section (webhook delivery has been unreliable historically).
- This fix does not retroactively rescan any collection credited
  *before* it was deployed — the 2026-08-23 incident's own already-
  credited collection (if any) needs manual reconciliation, not
  automatic correction.

## 3. Guardrails already in place (verified by test, not just by reading code)

| Guardrail | Where enforced | Confirmed |
|---|---|---|
| Push API success never credits | `wallet_push.py` caps `collections.status` at `"processing"` | ✅ test |
| Ledger can't go negative | `post_ledger_entries` Postgres RPC, atomic | ✅ (pre-existing, reused) |
| Reversal after credit actually reverses | `reverse_successful_collection()` | ✅ test |
| Reversal is idempotent | guarded on `status == "successful"` | ✅ test |
| Insufficient-balance reversal still flips status + alerts admin | `InsufficientBalanceError` caught, not swallowed | ✅ test |
| Self-payment/own-till held pre-credit | `check_self_payment_risk()` inside `resolve_collection()` | ✅ test |
| Held collection only credited via explicit admin clear | `finalize_pending_review_collection()`, called only from `admin_risk.py` alert-clear | ✅ test |
| Payment link / invoice reopened on reversal, held on self-payment | `_apply_collection_reversal()` / gate before `_apply_collection_success()` | ✅ test |
| Original ledger entries never edited/deleted | reversal posts new entries against the same `transaction_id` | ✅ test (`ledger_entries` count-based assertions) |
| No secrets in this fix's diff | `rg` scan against the commit | ✅ manual scan, twice |

## 4. Browser verification — Merchant Portal + Super Admin

See the checklist handed to the user directly in-session (2026-08-23):
exact badge text/color per `collections.status` value
(`processing`/`successful`/`failed`/`reversed`/`pending_review`), traced
from `apps/web/src/lib/portal/status-tones.ts` and
`apps/web/src/lib/admin/status-tones.ts`. **Do not submit the "Request
Collection" form or clear a fraud alert during this read-only pass** —
both have real side effects (§5/§6).

Report back: does every row match the documented badge/color/wording for
its actual `status`? Any `pending_review`/`reversed` collection showing
as "Success"/green would be the fix not working.

## 5. Controlled live wallet-push test (requires explicit approval)

1. Small payment link or Merchant Portal "Request Collection", 1000 TZS
   (or smallest practical amount).
2. Customer phone **must not** match the merchant's own `contact_phone`
   — this test is specifically to confirm the *normal* path still works,
   not the self-payment path (that's §6).
3. Trigger the push, approve on the phone.
4. Immediately after: prompt sent, collection `processing`, wallet
   balance **unchanged** — check `/portal/wallet` before refreshing
   anything.
5. Run status refresh:
   - Selcom `PENDING` → stays `processing`, balance still unchanged.
   - Selcom `COMPLETED` → collection moves `successful` (no general
     clearance gate exists — see §2), balance updates **exactly once**
     by net amount (gross minus platform fee).
6. Re-run refresh once more — balance must not change again (idempotency).

## 6. Controlled self-payment/own-till test (requires explicit approval; skip if it would incur unnecessary fees)

1. Repeat §5 using the merchant's own registered `contact_phone` as the
   payer.
2. Confirm the collection resolves `pending_review`, **not**
   `successful` — wallet balance unchanged.
3. Confirm Super Admin's Risk Monitoring shows a `SELF_PAYMENT_OWN_TILL`
   CRITICAL alert for it.
4. Confirm the merchant's own Collections page shows "Pending review",
   never "Success".
5. Only if intentionally finalizing the test: clear the alert as Super
   Admin and confirm the balance updates exactly once, then. Otherwise
   leave it `pending_review` — clearing it is a real credit action.

## 7. Stop conditions — halt go-live immediately if any of these occur

- Any collection shows `"successful"`/green in either portal while its
  actual DB `status` is `pending_review` or `reversed`.
- A reversal signal arrives for an already-`"successful"` collection and
  the wallet balance does not decrease.
- Running refresh or re-delivering a webhook twice changes the wallet
  balance a second time (double-credit or double-reverse).
- A self-payment collection ever reaches `"successful"` without an
  explicit admin alert-clear action.
- `ledger_entries` for a reversed collection don't net to zero against
  the original posting, or the original entries are missing/edited
  rather than reversed by new ones.
- Any Selcom credential, Supabase service role key, or private key
  appears anywhere in the browser — page source, DevTools, Network tab,
  or frontend logs.

If any of these happen: do not enable Collections broadly, keep the
fix's code path as the only path (don't roll back to pre-fix behavior),
and treat it as an incident — root-cause before resuming.
