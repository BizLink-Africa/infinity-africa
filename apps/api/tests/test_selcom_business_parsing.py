"""app/services/selcom_business/parsing.py — direct unit coverage of
parse_transaction_result()'s field-name guessing against simulated
response shapes. See that module's docstring: the *request* field names
are confirmed against developer.selcom.business's own documentation, but
no full example *response* body was shown there, so these tests document
current behavior for a range of plausible response shapes rather than
proving Selcom's real field names — do not change the mappings below
based on these tests alone; only a real sandbox response can confirm them
(see docs/selcom-live-go-live.md's "Selcom readiness" section).

test_selcom_business_client.py already covers the IP-whitelist (403 / code
611) detection at the HTTP layer; this file covers parse_transaction_result
in isolation, independent of any HTTP client.
"""

from app.services.selcom_business.parsing import parse_transaction_result

# --- recognized status codes ----------------------------------------------


def test_status_code_000_parses_as_successful():
    result = parse_transaction_result({"status": "000", "transId": "INF-1"}, trans_id="INF-1")
    assert result.status == "successful"


def test_status_word_success_parses_as_successful():
    result = parse_transaction_result({"status": "SUCCESS"}, trans_id="INF-1")
    assert result.status == "successful"


def test_status_code_001_parses_as_processing():
    result = parse_transaction_result({"status": "001"}, trans_id="INF-1")
    assert result.status == "processing"


def test_status_word_inprogress_parses_as_processing():
    result = parse_transaction_result({"status": "INPROGRESS"}, trans_id="INF-1")
    assert result.status == "processing"


def test_status_word_ambiguous_parses_as_ambiguous():
    result = parse_transaction_result({"status": "AMBIGUOUS"}, trans_id="INF-1")
    assert result.status == "ambiguous"


def test_unrecognized_status_falls_back_to_failed():
    result = parse_transaction_result({"status": "no-such-status"}, trans_id="INF-1")
    assert result.status == "failed"


# --- codes seen in Selcom's docs/support threads but not yet in the
# recognized set below — documents CURRENT behavior (falls back to
# "failed") so a real sandbox response is needed to confirm whether these
# should map to "processing"/"ambiguous" instead. Deliberately not changed
# here without that confirmation. ---------------------------------------


def test_status_code_111_currently_falls_back_to_failed():
    result = parse_transaction_result({"status": "111"}, trans_id="INF-1")
    assert result.status == "failed"


def test_status_code_927_currently_falls_back_to_failed():
    result = parse_transaction_result({"status": "927"}, trans_id="INF-1")
    assert result.status == "failed"


def test_status_code_999_currently_falls_back_to_failed():
    result = parse_transaction_result({"status": "999"}, trans_id="INF-1")
    assert result.status == "failed"


# --- alternate field names for the same concept ---------------------------


def test_transaction_status_field_name_is_also_read():
    result = parse_transaction_result({"transactionStatus": "success"}, trans_id="INF-1")
    assert result.status == "successful"


def test_result_field_name_is_also_read():
    result = parse_transaction_result({"result": "completed"}, trans_id="INF-1")
    assert result.status == "successful"


# --- transaction id / receipt extraction, with fallback chains -----------


def test_transaction_id_prefers_transid_field():
    result = parse_transaction_result(
        {"status": "000", "transId": "SELCOM-1", "transactionId": "OTHER"}, trans_id="INF-1"
    )
    assert result.transaction_id == "SELCOM-1"


def test_transaction_id_falls_back_to_the_trans_id_argument_when_absent():
    result = parse_transaction_result({"status": "000"}, trans_id="INF-1")
    assert result.transaction_id == "INF-1"


def test_receipt_prefers_receipt_field_over_alternates():
    result = parse_transaction_result(
        {"status": "000", "receipt": "R-1", "receiptNumber": "R-2"}, trans_id="INF-1"
    )
    assert result.receipt == "R-1"


def test_receipt_is_none_when_no_receipt_field_present():
    result = parse_transaction_result({"status": "000"}, trans_id="INF-1")
    assert result.receipt is None


# --- failure reason + raw response passthrough -----------------------------


def test_failure_reason_is_populated_only_when_status_is_failed():
    result = parse_transaction_result({"status": "000"}, trans_id="INF-1")
    assert result.failure_reason is None


def test_failure_reason_prefers_message_field():
    result = parse_transaction_result(
        {"status": "failed", "message": "Invalid recipient account", "reason": "OTHER"}, trans_id="INF-1"
    )
    assert result.failure_reason == "Invalid recipient account"


def test_failure_reason_falls_back_to_a_default_when_no_message_or_reason():
    result = parse_transaction_result({"status": "failed"}, trans_id="INF-1")
    assert result.failure_reason == "Selcom reported this transaction failed"


def test_raw_response_is_stored_unmodified():
    response = {"status": "000", "transId": "INF-1", "some_other_field": "value"}
    result = parse_transaction_result(response, trans_id="INF-1")
    assert result.raw_response == response
