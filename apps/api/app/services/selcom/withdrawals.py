"""Selcom-specific withdrawal (payout/disbursement) initiation — the
method-aware translation layer between app/services/disbursements.py's
shapes and SelcomHTTPClient.create_payout(). Mirrors live_client.py's
LiveSelcomClient role for the collection side.

**Best-effort placeholder** — same caveat as the rest of app/services/selcom/:
no real Selcom API documentation was available when this was written. In
particular, whether Selcom's payout endpoint actually differs per method
(SELCOM_PESA vs. MOBILE_MONEY vs. BANK_ACCOUNT) — one endpoint with
different optional fields, as built here, vs. genuinely separate
endpoints/payload shapes — is unverified. Fix this module first once a
real Selcom sandbox response is available.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from app.services.selcom.parsing import extract_provider_reference, extract_status
from app.services.selcom.schemas import DisbursementResult

if TYPE_CHECKING:
    from app.services.selcom.live_client import SelcomHTTPClient

_PROVIDER_NAME = "selcom"


async def initiate_withdrawal(
    client: "SelcomHTTPClient",
    *,
    method: str,
    amount: Decimal,
    currency: str,
    destination_identifier: str,
    bank_name: str | None,
    network: str | None,
    reference: str,
) -> DisbursementResult:
    """Calls Selcom's payout endpoint with method-appropriate fields and
    parses the result. Unlike a collection push (always "processing" until
    a webhook/status-check resolves it), a payout call is expected to
    resolve synchronously — matching MockSelcomClient's disbursement
    behavior and app/services/disbursements.py's "reserve, call, settle or
    reverse" flow, which has nothing to do while a disbursement sits in an
    intermediate state."""
    if method not in ("SELCOM_PESA", "MOBILE_MONEY", "BANK_ACCOUNT"):
        raise ValueError(f"Unsupported withdrawal method for Selcom: {method}")

    response = await client.create_payout(
        amount=amount,
        currency=currency,
        destination_identifier=destination_identifier,
        reference=reference,
        bank_name=bank_name if method == "BANK_ACCOUNT" else None,
        network=network if method == "MOBILE_MONEY" else None,
    )

    status = extract_status(response)
    failure_reason = None
    if status == "failed":
        failure_reason = str(response.get("message") or response.get("reason") or "Selcom reported this payout failed")

    return DisbursementResult(
        provider=_PROVIDER_NAME,
        provider_reference=extract_provider_reference(response) or reference,
        status=status,
        failure_reason=failure_reason,
    )
