"""Response-field parsing for the Selcom Business Disbursement API.

**Best-effort placeholder for response shape** — developer.selcom.business's
landing page (fetched for this integration) documents the *request* fields
for each endpoint precisely (`transId`, `recipientFiCode`, `recipientAccount`,
etc.) but doesn't show a full example *response* body. The field names
guessed at below follow the same reasonable, industry-standard shape the
rest of this codebase's Selcom integration already uses for the same
reason (see app/services/selcom/parsing.py's identical caveat) — verify
against a real sandbox response before relying on this in production.
"""

from app.services.selcom_business.schemas import (
    SelcomBusinessResult,
    SelcomBusinessStatus,
)


def _extract_status(response: dict) -> SelcomBusinessStatus:
    raw = str(
        response.get("status") or response.get("transactionStatus") or response.get("result") or ""
    ).strip().lower()
    if raw in ("success", "successful", "completed", "000"):
        return "successful"
    if raw in ("pending", "processing", "accepted", "inprogress", "001"):
        return "processing"
    if raw in ("ambiguous", "unknown"):
        return "ambiguous"
    return "failed"


def _extract_transaction_id(response: dict, *, fallback: str) -> str:
    return str(
        response.get("transId")
        or response.get("transactionId")
        or response.get("reference")
        or fallback
    )


def _extract_receipt(response: dict) -> str | None:
    receipt = response.get("receipt") or response.get("receiptNumber") or response.get("selcomReceipt")
    return str(receipt) if receipt else None


def parse_transaction_result(response: dict, *, trans_id: str) -> SelcomBusinessResult:
    status = _extract_status(response)
    failure_reason = None
    if status == "failed":
        failure_reason = str(
            response.get("message") or response.get("reason") or "Selcom reported this transaction failed"
        )
    return SelcomBusinessResult(
        transaction_id=_extract_transaction_id(response, fallback=trans_id),
        status=status,
        receipt=_extract_receipt(response),
        failure_reason=failure_reason,
        raw_status=str(response.get("status") or response.get("result") or ""),
    )
