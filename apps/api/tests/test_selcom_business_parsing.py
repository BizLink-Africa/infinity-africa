"""app/services/selcom_business/parsing.py — direct unit coverage of
parse_transaction_result() against Selcom's real sandbox response shape.

Verified 2026-08-21 against two real sandbox calls (see
docs/selcom-sandbox-test-accounts.md) — REAL_PROCESSING_RESPONSE and
REAL_FAILED_RESPONSE below are the actual (non-sensitive) bodies Selcom
returned, not guesses. Two things the earlier field-name guesses got
wrong, now fixed and covered here: `trans_id`/`selcom_receipt` are nested
inside `data`, not top-level, and the real "processing" resultcode is
`"111"`, not the previously guessed `"001"`.

test_selcom_business_client.py already covers the IP-whitelist (403 / code
611) detection at the HTTP layer; this file covers parse_transaction_result
in isolation, independent of any HTTP client.
"""

from app.services.selcom_business.parsing import parse_transaction_result

# --- real captured sandbox responses (redacted only where the real value
# would be Selcom-account-identifying; trans_id/receipt here are sandbox
# test artifacts, not sensitive) -------------------------------------------

REAL_PROCESSING_RESPONSE = {
    "success": True,
    "error_code": 1,
    "message": "Transaction processed successfully.",
    "result": "INPROGRESS",
    "resultcode": "111",
    "data": {
        "trans_id": "INF-5E4866FACAB94D94",
        "selcom_receipt": "SBS-595532PQVW",
        "status": "ACCEPTED",
        "amount": 1300,
        "principal_amount": 1000,
        "total_charges": 300,
        "charges_summary": "Fee 231, VAT 46, Excise Duty 23",
        "currency": "TZS",
    },
}

REAL_FAILED_RESPONSE = {
    "success": False,
    "error_code": -40,
    "message": "Invalid account number for the provided bank/FI code.",
    "result": "FAIL",
    "resultcode": "-40",
    "data": [],
}

# Verified 2026-08-22 against the first real production pilot withdrawal
# (transaction DIS-20260822-79DEB2B1, a status-check call after the initial
# process call succeeded). A third field-name variant: trans_id/receipt are
# still nested inside `data`, but camelCase (`transId`/`selcomReceipt`) here
# rather than the sandbox's snake_case — caught because the receipt column
# was silently staying null on a real successful disbursement.
REAL_PRODUCTION_SUCCESS_RESPONSE = {
    "success": True,
    "error_code": "000",
    "resultcode": "000",
    "result": "SUCCESS",
    "message": "Transaction status retrieved.",
    "data": {
        "transId": "DIS-20260822-79DEB2B1",
        "selcomReceipt": "SB0822PB1PU",
        "status": "COMPLETED",
        "amount": "1000.00",
        "principalAmount": "1000.00",
        "totalCharges": "0.00",
        "currency": "TZS",
        "senderAccount": "5529108708283",
        "senderName": "INFINITY DISBURSEMENT",
    },
}


def test_real_processing_response_parses_correctly():
    result = parse_transaction_result(REAL_PROCESSING_RESPONSE, trans_id="INF-5E4866FACAB94D94")
    assert result.status == "processing"
    assert result.transaction_id == "INF-5E4866FACAB94D94"
    assert result.receipt == "SBS-595532PQVW"
    assert result.failure_reason is None
    assert result.raw_status == "INPROGRESS"
    assert result.raw_response == REAL_PROCESSING_RESPONSE


def test_real_failed_response_parses_correctly():
    result = parse_transaction_result(REAL_FAILED_RESPONSE, trans_id="INF-FAIL-1")
    assert result.status == "failed"
    assert result.transaction_id == "INF-FAIL-1"  # not in `data` (it's []) — falls back to the arg
    assert result.receipt is None
    assert result.failure_reason == "Invalid account number for the provided bank/FI code."
    assert result.raw_status == "FAIL"


def test_real_production_success_response_parses_correctly():
    result = parse_transaction_result(REAL_PRODUCTION_SUCCESS_RESPONSE, trans_id="DIS-20260822-79DEB2B1")
    assert result.status == "successful"
    assert result.transaction_id == "DIS-20260822-79DEB2B1"
    assert result.receipt == "SB0822PB1PU"
    assert result.failure_reason is None
    assert result.raw_status == "SUCCESS"


# --- recognized status text (`result`/`status`/`transactionStatus`) -------


def test_status_word_success_parses_as_successful():
    result = parse_transaction_result({"status": "SUCCESS"}, trans_id="INF-1")
    assert result.status == "successful"


def test_status_word_inprogress_parses_as_processing():
    result = parse_transaction_result({"status": "INPROGRESS"}, trans_id="INF-1")
    assert result.status == "processing"


def test_status_word_fail_parses_as_failed():
    result = parse_transaction_result({"status": "FAIL"}, trans_id="INF-1")
    assert result.status == "failed"


def test_status_word_ambiguous_parses_as_ambiguous():
    result = parse_transaction_result({"status": "AMBIGUOUS"}, trans_id="INF-1")
    assert result.status == "ambiguous"


def test_unrecognized_status_falls_back_to_failed():
    result = parse_transaction_result({"status": "no-such-status"}, trans_id="INF-1")
    assert result.status == "failed"


def test_transaction_status_field_name_is_also_read():
    result = parse_transaction_result({"transactionStatus": "success"}, trans_id="INF-1")
    assert result.status == "successful"


def test_result_field_name_is_also_read():
    result = parse_transaction_result({"result": "completed"}, trans_id="INF-1")
    assert result.status == "successful"


def test_result_is_preferred_over_status_when_both_present():
    # `result` is the field real responses actually use; a top-level
    # `status` has never been observed in a real response, but if one ever
    # shows up alongside `result`, `result` wins.
    result = parse_transaction_result({"result": "INPROGRESS", "status": "FAIL"}, trans_id="INF-1")
    assert result.status == "processing"


# --- resultcode fallback, used when `result`/`status` isn't a recognized
# word — "111" is a real confirmed code; "927"/"999" are Selcom-documented
# codes not yet seen in a real response (see
# docs/selcom-sandbox-test-accounts.md's result-interpretation table). ----


def test_resultcode_000_parses_as_successful():
    result = parse_transaction_result({"resultcode": "000"}, trans_id="INF-1")
    assert result.status == "successful"


def test_resultcode_111_parses_as_processing():
    result = parse_transaction_result({"resultcode": "111"}, trans_id="INF-1")
    assert result.status == "processing"


def test_resultcode_927_parses_as_processing():
    result = parse_transaction_result({"resultcode": "927"}, trans_id="INF-1")
    assert result.status == "processing"


def test_resultcode_999_parses_as_ambiguous():
    result = parse_transaction_result({"resultcode": "999"}, trans_id="INF-1")
    assert result.status == "ambiguous"


def test_unrecognized_resultcode_falls_back_to_failed():
    result = parse_transaction_result({"resultcode": "-99"}, trans_id="INF-1")
    assert result.status == "failed"


# --- transaction id extraction: nested data.trans_id first, then
# top-level fallbacks, then the caller-supplied trans_id argument --------


def test_transaction_id_prefers_nested_data_trans_id():
    result = parse_transaction_result(
        {"status": "SUCCESS", "transId": "TOP-LEVEL", "data": {"trans_id": "NESTED-1"}}, trans_id="INF-1"
    )
    assert result.transaction_id == "NESTED-1"


def test_transaction_id_falls_back_to_top_level_transid_field():
    result = parse_transaction_result(
        {"status": "SUCCESS", "transId": "SELCOM-1", "transactionId": "OTHER"}, trans_id="INF-1"
    )
    assert result.transaction_id == "SELCOM-1"


def test_transaction_id_falls_back_to_the_trans_id_argument_when_absent():
    result = parse_transaction_result({"status": "SUCCESS"}, trans_id="INF-1")
    assert result.transaction_id == "INF-1"


def test_transaction_id_falls_back_to_argument_when_data_is_a_list():
    # confirmed real shape on failure: "data": [] — not a dict, must not
    # be treated as one
    result = parse_transaction_result({"status": "FAIL", "data": []}, trans_id="INF-1")
    assert result.transaction_id == "INF-1"


# --- receipt extraction: nested data.selcom_receipt first, then top-level
# fallbacks, then None -----------------------------------------------------


def test_receipt_prefers_nested_data_selcom_receipt():
    result = parse_transaction_result(
        {"status": "SUCCESS", "receipt": "TOP-LEVEL", "data": {"selcom_receipt": "SBS-NESTED"}},
        trans_id="INF-1",
    )
    assert result.receipt == "SBS-NESTED"


def test_receipt_falls_back_to_top_level_receipt_field():
    result = parse_transaction_result(
        {"status": "SUCCESS", "receipt": "R-1", "receiptNumber": "R-2"}, trans_id="INF-1"
    )
    assert result.receipt == "R-1"


def test_receipt_is_none_when_no_receipt_field_present():
    result = parse_transaction_result({"status": "SUCCESS"}, trans_id="INF-1")
    assert result.receipt is None


def test_receipt_is_none_when_data_is_a_list():
    result = parse_transaction_result({"status": "FAIL", "data": []}, trans_id="INF-1")
    assert result.receipt is None


# --- failure reason + raw response passthrough -----------------------------


def test_failure_reason_is_populated_only_when_status_is_failed():
    result = parse_transaction_result({"status": "SUCCESS"}, trans_id="INF-1")
    assert result.failure_reason is None


def test_failure_reason_prefers_message_field():
    result = parse_transaction_result(
        {"status": "FAIL", "message": "Invalid recipient account", "reason": "OTHER"}, trans_id="INF-1"
    )
    assert result.failure_reason == "Invalid recipient account"


def test_failure_reason_falls_back_to_a_default_when_no_message_or_reason():
    result = parse_transaction_result({"status": "FAIL"}, trans_id="INF-1")
    assert result.failure_reason == "Selcom reported this transaction failed"


def test_raw_response_is_stored_unmodified():
    response = {"status": "SUCCESS", "transId": "INF-1", "some_other_field": "value"}
    result = parse_transaction_result(response, trans_id="INF-1")
    assert result.raw_response == response
