"""Shared response-parsing helpers for translating a raw Selcom API
response into this app's provider-result shapes (CollectionResult,
DynamicQrResult, DisbursementResult) — used by both collections.py and
withdrawals.py so the two don't duplicate the same field-guessing logic.

**Best-effort placeholder** — same caveat as the rest of app/services/selcom/:
no real Selcom response payload was available to verify field names or
result codes against. These two functions are the ones to fix first once a
real Selcom sandbox response has been observed.
"""


def extract_provider_reference(response: dict) -> str:
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    return str(response.get("reference") or response.get("transid") or response.get("order_id") or data.get("reference") or "")


def extract_status(response: dict) -> str:
    """Maps Selcom's result/status field onto this app's
    "successful"/"failed"/"processing" vocabulary. Placeholder mapping —
    verify against real Selcom response codes before going live."""
    raw = str(response.get("result") or response.get("status") or response.get("resultcode") or "").strip().lower()
    if raw in ("success", "successful", "000", "completed", "paid"):
        return "successful"
    if raw in ("pending", "processing", "001", ""):
        return "processing"
    return "failed"
