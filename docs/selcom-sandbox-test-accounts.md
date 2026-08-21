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

## Selcom's whitelisted outbound IPs

As of 2026-08-21, the Selcom Business Disbursement API portal shows these
three static/public IPs as whitelisted (status Active, "Continue without IP
whitelisting" unchecked):

```
208.77.244.241
152.55.184.240
152.55.185.189
```

**No local development machine is whitelisted, and never will be** — only
Railway's static outbound IP is. Confirmed by direct comparison: a local
machine's public IP (`curl https://api.ipify.org`) does not match any of
the three above, while Railway's (checked via `railway ssh`, see below)
matched `152.55.184.240` exactly. Running the sandbox test script locally
will always fail with an IP-whitelist error (HTTP 403, or Selcom error code
`611`) regardless of credentials — this is structural, not a transient
propagation delay. Always run it via Railway SSH instead.

## Running the sandbox tests via Railway SSH (required)

`railway run` / `railway shell` execute **locally** with Railway's env vars
injected — they do NOT route traffic through Railway's network, so they
don't help here. Only `railway ssh` connects into the actual running
deployment instance, so a request from inside that session genuinely
egresses via Railway's whitelisted static IP.

Prerequisites (one-time): install the Railway CLI
(`npm install -g @railway/cli`), `railway login`, link this project
(`railway link` — the Railway dashboard project is internally named
"content-manifestation", not "infinity-africa"; confirm with `railway
status` that `repo: BizLink-Africa/infinity-africa` and the service URL
match), and register a local SSH public key
(`railway ssh keys add -k <path-to-.pub> -n "<name>"` — only ever share the
`.pub` file, never the private key). The first `railway ssh` connection
prompts to accept Railway's SSH host key interactively — accept it once
per machine.

**Verify the outbound IP first:**

```bash
railway ssh -- python -c "import urllib.request; print(urllib.request.urlopen('https://api.ipify.org').read().decode())"
```

(the container has no `curl` — use the Python one-liner above, not
`curl https://api.ipify.org`). The result must be one of the three IPs
listed above, or Selcom testing will still fail.

**Verify Selcom config is loaded correctly** (safe — prints only booleans
and the non-secret sandbox base URL, no key material):

```bash
railway ssh -- python -c "from app.config import get_settings; s = get_settings(); print('mode:', s.selcom_business_mode); print('api_key_present:', bool(s.selcom_business_api_key)); print('private_key_present:', bool(s.selcom_business_private_key_base64)); print('account_number_present:', bool(s.selcom_business_account_number)); print('sandbox_base_url:', s.selcom_business_sandbox_base_url)"
```

**Run the three presets** — the container's working directory is already
`apps/api` (confirmed via `railway ssh -- pwd` / `ls`, which show
`scripts/`, `app/`, `tests/` directly), so the commands are unchanged from
running locally, just prefixed with `railway ssh --`:

```bash
railway ssh -- python scripts/test_selcom_disbursement_sandbox.py \
  --preset selcom --amount 1000 \
  --purpose "Sandbox internal transfer test" \
  --remarks "Infinity Africa sandbox test"

railway ssh -- python scripts/test_selcom_disbursement_sandbox.py \
  --preset bank --amount 1000 \
  --purpose "Sandbox bank withdrawal test" \
  --remarks "Infinity Africa sandbox test"

railway ssh -- python scripts/test_selcom_disbursement_sandbox.py \
  --preset wallet --amount 1000 \
  --purpose "Sandbox wallet withdrawal test" \
  --remarks "Infinity Africa sandbox test"
```

If the container's working directory ever isn't the app root, wrap it:
`railway ssh -- bash -lc "cd apps/api && python scripts/test_selcom_disbursement_sandbox.py ..."`.

### Interpreting the result

| Response | Meaning | Next step |
| --- | --- | --- |
| HTTP 403, or Selcom code `611` (`is_ip_whitelist_error: True`) | Outbound IP isn't whitelisted, or the whitelist setting wasn't saved/applied on Selcom's side | Re-check the outbound IP command above against the whitelist list; don't touch signing code |
| `{"success": false, "message": "Invalid signature."}` (HTTP 401) | IP whitelist is fine — Selcom received and evaluated the request. The RSA signature itself doesn't verify | Almost always means the **public** half of the RSA keypair isn't registered with Selcom for this API key/account (see below) — don't rewrite signing logic without evidence from Selcom docs/support first |
| `SUCCESS` / result code `000` | Both IP whitelist and signature are working | Capture the raw response body (redact sensitive fields), compare against `apps/api/app/services/selcom_business/parsing.py`'s guessed field names, update the parser if they differ |
| `INPROGRESS` / `111` / `927` | Accepted, pending — treat as a real success path, not a failure | Same as above — capture the shape and verify the parser handles it |
| `AMBIGUOUS` / `999` | Selcom itself is unsure of the outcome (needs reconciliation) | Capture the shape and verify the parser's ambiguous-status handling |

**If stuck on "Invalid signature":** this project's keypair was
self-generated (not issued by Selcom), so Selcom must have the matching
**public** key on file to verify signatures made with the private key.
Derive the public key (safe to share — never the private key) with:

```bash
cd apps/api
python -c "import base64; from cryptography.hazmat.primitives import serialization; b64 = [l for l in open('.env') if l.startswith('SELCOM_BUSINESS_PRIVATE_KEY_BASE64=')][0].strip().split('=',1)[1]; key = serialization.load_pem_private_key(base64.b64decode(b64), password=None); print(key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode())"
```

then confirm with Selcom (portal or support) that this exact public key is
registered against the `SELCOM_BUSINESS_API_KEY` in use.

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
