"""Direct Selcom Checkout Create Order - Minimal connectivity test
(https://developers.selcommobile.com/#create-order-minimal) — calls
SelcomCheckoutHTTPClient.create_order_minimal() directly, bypassing every
merchant-facing/admin validation layer, so signing and network
reachability can be verified independently.

Manual use only — never wired into any route or test suite. Reads
Checkout credentials the same way the running app does
(get_selcom_checkout_credentials(), app/config/settings.py), so set them
in apps/api/.env for a local run:

    SELCOM_CHECKOUT_BASE_URL=...
    SELCOM_CHECKOUT_API_KEY=...
    SELCOM_CHECKOUT_API_SECRET=...
    SELCOM_CHECKOUT_VENDOR=...

**Important, unlike the Business Disbursement API's equivalent script**:
this product has no separate sandbox/production base-URL split in this
codebase's settings (app/config/settings.py has one
SELCOM_CHECKOUT_BASE_URL, not a sandbox/production pair) — whatever URL
is currently configured is exactly what this script will hit. This
script cannot tell sandbox and production apart and will not try to —
confirm SELCOM_CHECKOUT_BASE_URL actually points at Selcom's sandbox
before running this, or you will create a real order.

Two open questions this script exists to resolve against a real sandbox
response, per docs/selcom-checkout-go-live.md's "not yet confirmed"
list (once that doc exists) and create_order_minimal()'s own docstring:

1. Signed-Fields *order* — resolved as moot for this endpoint: once
   fields absent from every real Minimal payload example are dropped,
   the docs' shell example and the parameter-table order agree. Nothing
   to test here.
2. Timestamp *format* — genuinely unresolved: signer.build_timestamp()
   (ISO-8601 UTC, ".000Z") vs. signer.build_timestamp_php_style()
   ("yyyy-dd-mm H:i:s", per the shell headers' literal description).
   This script tries the ISO-8601 default first; if Selcom rejects it
   with what looks like a signature/auth failure, it retries once with
   the PHP-style timestamp and reports both outcomes so a human can
   judge which one Selcom actually accepted. **Only this script does
   this retry — production code (client.py) always uses the ISO-8601
   default until this script confirms otherwise (task instruction: try
   the alternative only here, never silently in the production path).**

Once one variant is confirmed working end to end, update
create_order_minimal()'s default and this script's own docstring/
docs/selcom-checkout-go-live.md to say so — don't leave this ambiguity
open once it's actually been tested.

Never prints the API key, API secret, or a full buyer email/phone —
only a masked form, in both the outgoing request summary and Selcom's
raw response body.

Usage:

    python apps/api/scripts/test_selcom_checkout_sandbox.py \\
      --buyer-email test@example.com \\
      --buyer-name "Sandbox Test" \\
      --buyer-phone 255700000000 \\
      --amount 8000

Every flag has a matching env var fallback (SELCOM_TEST_BUYER_EMAIL,
SELCOM_TEST_BUYER_NAME, SELCOM_TEST_BUYER_PHONE, SELCOM_TEST_AMOUNT,
SELCOM_TEST_NO_OF_ITEMS) so it can be scripted without shell history
exposing values.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from app.config import get_settings
from app.core.errors import SelcomAPIError
from app.core.references import generate_reference
from app.services.selcom_checkout.client import (
    SelcomCheckoutHTTPClient,
    get_selcom_checkout_credentials,
)
from app.services.selcom_checkout.errors import SelcomCheckoutMisconfiguredError
from app.services.selcom_checkout.signer import (
    build_timestamp,
    build_timestamp_php_style,
)


def _mask_email(value: str) -> str:
    if "@" not in value:
        return "*" * len(value)
    local, _, domain = value.partition("@")
    masked_local = local[0] + "*" * max(len(local) - 1, 0)
    return f"{masked_local}@{domain}"


def _mask_phone(value: str) -> str:
    if len(value) <= 4:
        return "*" * len(value)
    return "*" * (len(value) - 4) + value[-4:]


def _mask_response_body(response: dict) -> dict:
    """Best-effort redaction — Selcom's own data, not a secret of ours,
    but buyer contact details are still sensitive."""
    masked = dict(response)
    data = masked.get("data")
    if isinstance(data, list) and data and isinstance(data[0], dict):
        masked = {**masked, "data": [dict(data[0])]}
    return masked


def _env_or_arg(arg_value: str | None, env_name: str) -> str | None:
    if arg_value is not None:
        return arg_value
    return os.environ.get(env_name)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--order-id", default=None, help="default: generated")
    parser.add_argument("--buyer-email", default=None, help="env: SELCOM_TEST_BUYER_EMAIL")
    parser.add_argument("--buyer-name", default=None, help="env: SELCOM_TEST_BUYER_NAME")
    parser.add_argument("--buyer-phone", default=None, help="env: SELCOM_TEST_BUYER_PHONE (255XXXXXXXXX)")
    parser.add_argument("--amount", default=None, help="env: SELCOM_TEST_AMOUNT")
    parser.add_argument("--no-of-items", default=None, help="env: SELCOM_TEST_NO_OF_ITEMS (default: 1)")
    return parser.parse_args()


async def _attempt(client: SelcomCheckoutHTTPClient, *, timestamp: str, label: str, **kwargs):
    print(f"--- Attempt: {label} (timestamp={timestamp}) ---")
    try:
        result = await client.create_order_minimal(timestamp=timestamp, **kwargs)
    except SelcomAPIError as exc:
        print("  Selcom API error:")
        print(f"    message:                {exc.message}")
        print(f"    provider_status_code:   {exc.provider_status_code}")
        if exc.provider_response_body is not None:
            print(f"    provider_response_body: {_mask_response_body(exc.provider_response_body)}")
        print()
        return None

    print("  Result:")
    print(f"    resultcode:  {result.resultcode}")
    print(f"    result:      {result.result}")
    print(f"    message:     {result.message}")
    print(f"    is_success:  {result.is_success}")
    print(f"    reference:   {result.reference}")
    print(f"    raw_response (masked): {_mask_response_body(result.raw_response)}")
    print()
    return result


async def _main() -> int:
    args = _parse_args()

    order_id = args.order_id or generate_reference("ORD-SANDBOX")
    buyer_email = _env_or_arg(args.buyer_email, "SELCOM_TEST_BUYER_EMAIL")
    buyer_name = _env_or_arg(args.buyer_name, "SELCOM_TEST_BUYER_NAME")
    buyer_phone = _env_or_arg(args.buyer_phone, "SELCOM_TEST_BUYER_PHONE")
    amount = _env_or_arg(args.amount, "SELCOM_TEST_AMOUNT")
    no_of_items = _env_or_arg(args.no_of_items, "SELCOM_TEST_NO_OF_ITEMS") or "1"

    missing = [
        flag
        for flag, value in [
            ("--buyer-email", buyer_email),
            ("--buyer-name", buyer_name),
            ("--buyer-phone", buyer_phone),
            ("--amount", amount),
        ]
        if not value
    ]
    if missing:
        print(f"Missing required value(s): {', '.join(missing)} (pass as a flag or matching env var)", file=sys.stderr)
        return 2

    settings = get_settings()

    print(
        "SELCOM_CHECKOUT_BASE_URL has no sandbox/production split in this codebase — "
        "whatever it's currently set to is exactly what this script will hit."
    )
    print(f"  SELCOM_CHECKOUT_BASE_URL:  {settings.selcom_checkout_base_url or '(not set)'}")
    print(f"  SELCOM_CHECKOUT_MODE:      {settings.selcom_checkout_mode}")
    confirm = input("Type 'yes' to confirm this is a safe (sandbox) endpoint to test against: ")
    if confirm.strip().lower() != "yes":
        print("Aborted.", file=sys.stderr)
        return 1

    print("Request summary (masked):")
    print(f"  order_id:            {order_id}")
    print(f"  buyer_email:         {_mask_email(buyer_email)}")
    print(f"  buyer_name:          {buyer_name}")
    print(f"  buyer_phone:         {_mask_phone(buyer_phone)}")
    print(f"  amount:              {amount}")
    print(f"  no_of_items:         {no_of_items}")
    print(f"  api_key_configured:  {bool(settings.selcom_checkout_api_key)}")
    print(f"  digest_method:       {settings.selcom_checkout_digest_method}")
    print()

    try:
        client = SelcomCheckoutHTTPClient(credentials=get_selcom_checkout_credentials(settings))
    except SelcomCheckoutMisconfiguredError as exc:
        print(f"Client misconfigured: {exc}", file=sys.stderr)
        return 2

    kwargs = {
        "order_id": order_id,
        "buyer_email": buyer_email,
        "buyer_name": buyer_name,
        "buyer_phone": buyer_phone,
        "amount": amount,
        "no_of_items": int(no_of_items),
    }

    result = await _attempt(client, timestamp=build_timestamp(), label="ISO-8601 UTC (production default)", **kwargs)

    if result is not None and result.is_success:
        print("ISO-8601 UTC timestamp succeeded — no need to try the alternative format.")
        return 0

    print(
        "ISO-8601 UTC attempt did not succeed — trying the shell headers' literal "
        "'yyyy-dd-mm H:i:s' format next, per task instruction (diagnostic script only, "
        "never silently in production code)."
    )
    kwargs["order_id"] = args.order_id or generate_reference("ORD-SANDBOX")  # fresh order_id, first may be consumed
    result = await _attempt(client, timestamp=build_timestamp_php_style(), label="yyyy-dd-mm H:i:s (shell literal)", **kwargs)

    if result is not None and result.is_success:
        print(
            "yyyy-dd-mm H:i:s succeeded where ISO-8601 UTC did not — update "
            "create_order_minimal()'s default timestamp format to match, and record "
            "this in docs/selcom-checkout-go-live.md before relying on it elsewhere."
        )
        return 0

    print("Neither timestamp format produced a successful order. Investigate the raw responses above before retrying.")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
