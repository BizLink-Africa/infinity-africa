"""Response handling for the Selcom Checkout/Collections API
(https://developers.selcommobile.com/).

**Endpoint response bodies are not yet confirmed.** The fetched docs
confirm the request-signing scheme (see signer.py) and list the Checkout
endpoints (Create Order, Get Order Status, etc. — see client.py) but the
page truncated before showing example request/response payloads for
them (checked 2026-08-22). Per this task's own instruction not to guess:
no endpoint-specific field extraction (order reference, status, etc.) is
implemented here yet. Add it only once a real example response — from
Selcom's docs directly, or a real sandbox call — confirms the actual
field names. app/services/selcom/parsing.py guessed field names for this
same product before a real reference was available and was wrong in
several ways once real ones surfaced elsewhere in this codebase (see
app/services/selcom_business/parsing.py's docstring for that history) —
this module exists specifically so that mistake isn't repeated here.

What IS safe to implement without guessing: decoding the raw HTTP
envelope (status code, JSON-or-not) — every JSON API does this the same
way regardless of Selcom-specific field names.
"""

import json

from app.services.selcom_checkout.errors import SelcomCheckoutError


def decode_json_response(*, status_code: int, body: bytes, path: str) -> dict:
    """Raises SelcomCheckoutError for a non-2xx status or an unparseable
    body; otherwise returns the decoded JSON as-is, unparsed further — see
    module docstring for why field-level extraction isn't implemented
    yet."""
    if status_code >= 400:
        raise SelcomCheckoutError(
            f"Selcom Checkout API returned HTTP {status_code} for {path}",
            provider_status_code=status_code,
        )
    try:
        return json.loads(body) if body else {}
    except ValueError as exc:
        raise SelcomCheckoutError(f"Selcom Checkout API returned a non-JSON response for {path}") from exc
