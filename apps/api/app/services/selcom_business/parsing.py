"""Response-field parsing for the Selcom Business Disbursement API.

**Verified against a real sandbox response** as of 2026-08-21 — see
docs/selcom-sandbox-test-accounts.md. Two real examples confirmed via
apps/api/scripts/test_selcom_disbursement_sandbox.py's `bank` preset
(processing) and `selcom` preset (failed):

    # processing (HTTP 200)
    {"success": true, "error_code": 1, "message": "Transaction processed successfully.",
     "result": "INPROGRESS", "resultcode": "111",
     "data": {"trans_id": "...", "selcom_receipt": "SBS-...", "status": "ACCEPTED",
               "amount": 1300, "principal_amount": 1000, "total_charges": 300,
               "charges_summary": "...", "currency": "TZS"}}

    # failed (HTTP 400 — raised as SelcomAPIError before reaching this module;
    # kept here too in case Selcom ever returns a FAIL result on a 200)
    {"success": false, "error_code": -40, "message": "Invalid account number for the provided bank/FI code.",
     "result": "FAIL", "resultcode": "-40", "data": []}

Two things the earlier guessed field names got wrong, now fixed: the
transaction id and receipt are nested inside `data`, not top-level, and the
real "processing" code is `"111"`, not the guessed `"001"`. `"927"`
(processing) and `"999"` (ambiguous) are Selcom-documented codes not yet
seen in a real response — included per docs/selcom-sandbox-test-accounts.md's
result-interpretation table, not a guess. `data` is `[]` (not a dict) on
failure — handled below rather than assumed to always be a dict.

**Verified against a real production `SUCCESS` response** (status-check
call, not the initial process call) as of 2026-08-22 — first real pilot
withdrawal, transaction `DIS-20260822-79DEB2B1`:

    {"success": true, "error_code": "000", "resultcode": "000", "result": "SUCCESS",
     "message": "Transaction status retrieved.",
     "data": {"transId": "DIS-20260822-79DEB2B1", "selcomReceipt": "SB0822PB1PU",
               "status": "COMPLETED", "amount": "1000.00", "principalAmount": "1000.00",
               "totalCharges": "0.00", "currency": "TZS", "senderAccount": "5529108708283",
               "senderName": "INFINITY DISBURSEMENT", "createdAt": "...", "updatedAt": "...",
               "transDatetime": "...", "chargesSummary": "-", "receiptMessage": "-"}}

Here `trans_id`/`selcom_receipt` are camelCase (`transId`/`selcomReceipt`),
still nested inside `data` — a third shape variant distinct from both the
sandbox example above and the guessed top-level camelCase originally coded
for. `_extract_transaction_id`/`_extract_receipt` check both casings, both
nesting levels.
"""

from app.services.selcom_business.schemas import (
    SelcomBusinessResult,
    SelcomBusinessStatus,
)

_TEXT_TO_STATUS: dict[str, SelcomBusinessStatus] = {
    "success": "successful",
    "successful": "successful",
    "completed": "successful",
    "pending": "processing",
    "processing": "processing",
    "accepted": "processing",
    "inprogress": "processing",
    "ambiguous": "ambiguous",
    "unknown": "ambiguous",
    "fail": "failed",
    "failed": "failed",
}

_RESULTCODE_TO_STATUS: dict[str, SelcomBusinessStatus] = {
    "000": "successful",
    "111": "processing",
    "927": "processing",
    "999": "ambiguous",
}


def _extract_status(response: dict) -> SelcomBusinessStatus:
    raw_text = str(
        response.get("result") or response.get("status") or response.get("transactionStatus") or ""
    ).strip().lower()
    if raw_text in _TEXT_TO_STATUS:
        return _TEXT_TO_STATUS[raw_text]

    resultcode = str(response.get("resultcode") or "").strip()
    if resultcode in _RESULTCODE_TO_STATUS:
        return _RESULTCODE_TO_STATUS[resultcode]

    return "failed"


def _response_data(response: dict) -> dict:
    """The nested `data` object on a real response — a dict on success/
    processing, an empty list `[]` (confirmed) on failure. Never assume
    it's a dict."""
    data = response.get("data")
    return data if isinstance(data, dict) else {}


def _extract_transaction_id(response: dict, *, fallback: str) -> str:
    data = _response_data(response)
    return str(
        data.get("trans_id")
        or data.get("transId")
        or response.get("transId")
        or response.get("transactionId")
        or response.get("reference")
        or fallback
    )


def _extract_receipt(response: dict) -> str | None:
    data = _response_data(response)
    receipt = (
        data.get("selcom_receipt")
        or data.get("selcomReceipt")
        or response.get("receipt")
        or response.get("receiptNumber")
        or response.get("selcomReceipt")
    )
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
        raw_status=str(response.get("result") or response.get("status") or ""),
        raw_response=response,
    )
