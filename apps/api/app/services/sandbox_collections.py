"""Sandbox collection simulation for the three direct server-to-server API
endpoints (POST /v1/collections/{wallet-push,selcom-pesa,qr}) — the only
collection-creation paths a sandbox-environment API key is ever routed
to. Never calls Selcom, never inserts a linked `transactions` row, so
resolve_collection()'s ledger-posting path is structurally unreachable
for anything created here — sandbox activity cannot touch a real wallet
balance by construction, not by a runtime check that could be bypassed
or forgotten elsewhere.

TODO (documented gap, not attempted here): this only covers the direct
API push/QR endpoints, the ones a merchant's own backend is expected to
call per the "integrate into your backend" business case. The "Infinity
Payment Page" flow (POST /v1/collections -> a payment_links row -> the
public customer-facing /pay/{slug} page) is NOT sandbox-aware — an
API-created payment link always goes through the real payment flow
regardless of the creating key's environment, since that page is
rendered and driven by Infinity itself, not the merchant's backend, and
extending simulation there would mean teaching the public,
unauthenticated pay endpoint to know a payment link's origin
environment. Out of scope for this pass.
"""

import uuid
from decimal import Decimal

from supabase import Client

from app.core.references import generate_reference
from app.core.time import utc_now_iso
from app.services.crud import insert_row

_SIMULATE_TO_INTERNAL_STATUS: dict[str, str] = {
    "successful": "successful",
    "failed": "failed",
    "pending_clearance": "pending_review",
    "reversed": "reversed",
}

_EXTERNAL_METHOD_TO_INTERNAL: dict[str, str] = {
    "wallet_push": "STK_PUSH",
    "selcom_pesa": "SELCOM_PESA_PUSH",
    "qr": "DYNAMIC_QR",
}

_TERMINAL_STATUSES = {"successful", "failed", "reversed"}


def execute_sandbox_collection(
    client: Client,
    *,
    merchant_id: uuid.UUID,
    external_method: str,
    amount: Decimal,
    currency: str,
    customer_phone: str | None,
    customer_name: str | None,
    merchant_reference: str | None,
    description: str | None,
    api_key_id: uuid.UUID,
    source: str,
    simulate_status: str | None,
) -> dict:
    """Creates a `collections` row with its FINAL status set directly —
    defaults to "successful" (a sandbox integration test should work by
    default without needing to know a magic value first), or whatever
    `simulate_status` asked for. No Selcom call, no transactions row."""
    internal_status = _SIMULATE_TO_INTERNAL_STATUS.get(simulate_status or "successful", "successful")
    now = utc_now_iso()
    sandbox_reference = f"SANDBOX-{uuid.uuid4().hex[:12].upper()}"

    row = insert_row(
        client,
        "collections",
        {
            "merchant_id": str(merchant_id),
            "environment": "sandbox",
            "method": _EXTERNAL_METHOD_TO_INTERNAL[external_method],
            "amount": str(amount),
            "currency": currency,
            "customer_phone": customer_phone,
            "merchant_reference": merchant_reference,
            "provider": "sandbox",
            "status": internal_status,
            "source": source,
            "api_key_id": str(api_key_id),
            "provider_reference": sandbox_reference,
            "provider_transid": generate_reference("SANDBOXTXN"),
            "initiated_at": now,
            "completed_at": now if internal_status in _TERMINAL_STATUSES else None,
            "failure_reason": "Simulated failure (sandbox)" if internal_status == "failed" else None,
            "metadata": {"sandbox": True, "customer_name": customer_name, "description": description},
        },
    )

    if external_method == "qr":
        row = {
            **row,
            "payment_token": f"SANDBOX-TOKEN-{uuid.uuid4().hex[:8].upper()}",
            "qr": f"00020101021226SANDBOXQR{sandbox_reference}",
        }
    return row
