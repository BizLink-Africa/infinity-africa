# Selcom Business Disbursement — Sandbox Test Accounts

**Sandbox only.** These three recipients come from Selcom's own Business
Disbursement API sandbox portal — they exist purely so an integrator can
exercise a real sandbox transaction without needing a live recipient. None
of them are secrets (Selcom hands them out to every sandbox integrator), but
they resolve to nothing in production — `SELCOM`/`TESTBANK`/`TESTWALLET`
must never appear as an accepted `recipient_fi_code` in merchant-facing
withdrawal validation. See §4 below and
[`docs/deployment-checklist.md`](./deployment-checklist.md#4-merchant-ui-validation-stays-strict).

## 1. Internal Transfer (Selcom to Selcom)

| Field | Value |
| --- | --- |
| Display format (with spaces, as shown in Selcom's portal) | `87747 38533 235` |
| API format (no spaces — what actually gets sent) | `8774738533235` |
| `recipientFiCode` | `SELCOM` |
| Recipient name | `Sandbox Selcom to Selcom` |

## 2. Bank

| Field | Value |
| --- | --- |
| Display format | `48423 18480 086` |
| API format | `4842318480086` |
| `recipientFiCode` | `TESTBANK` |
| Recipient name | `Sandbox Bank` |

## 3. Wallet

| Field | Value |
| --- | --- |
| Display format | `11405 54577 325` |
| API format | `1140554577325` |
| `recipientFiCode` | `TESTWALLET` |
| Recipient name | `Sandbox Wallet` |

## Running the direct sandbox test with these accounts

[`apps/api/scripts/test_selcom_disbursement_sandbox.py`](../apps/api/scripts/test_selcom_disbursement_sandbox.py)
has a `--preset` flag (`selcom` / `bank` / `wallet`) that fills in
`recipient_fi_code`/`recipient_account`/`recipient_name` from the table
above — no need to retype or reformat these account numbers by hand. The
account number is space-normalized automatically (spaces stripped) even if
pasted straight from the portal's display format.

```bash
cd apps/api

python scripts/test_selcom_disbursement_sandbox.py \
  --preset selcom \
  --amount 1000 \
  --purpose "Sandbox internal transfer test" \
  --remarks "Infinity Africa sandbox test"

python scripts/test_selcom_disbursement_sandbox.py \
  --preset bank \
  --amount 1000 \
  --purpose "Sandbox bank withdrawal test" \
  --remarks "Infinity Africa sandbox test"

python scripts/test_selcom_disbursement_sandbox.py \
  --preset wallet \
  --amount 1000 \
  --purpose "Sandbox wallet withdrawal test" \
  --remarks "Infinity Africa sandbox test"
```

A manual `--recipient-fi-code`/`--recipient-account`/`--recipient-name`
passed alongside `--preset` overrides just that field — everything else in
[`docs/deployment-checklist.md`](./deployment-checklist.md#3-direct-selcom-sandbox-connectivity-test-script)
about this script (masked output, requires `SELCOM_BUSINESS_MODE=sandbox`,
IP-whitelist behavior) still applies unchanged.

## 4. Sandbox-only — never a production destination

These three `recipientFiCode` values (`SELCOM`, `TESTBANK`, `TESTWALLET`)
and account numbers are for the direct sandbox test script only:

- The Merchant Portal withdrawal form and `POST /v1/merchant/withdrawals`
  are not changed to accept them.
- Wallet/mobile withdrawals still require a real `255XXXXXXXXX` phone
  format (no `+`) via `app/core/phone.py::normalize_tz_phone()`.
- Bank withdrawals still require a real, configured bank destination code.

## After a real sandbox response comes back

Compare the raw response body each preset run prints against
`app/services/selcom_business/parsing.py`'s field-name assumptions — see
[`docs/deployment-checklist.md`](./deployment-checklist.md#5-after-a-real-sandbox-response-comes-back)
for the full field-by-field comparison process.
