"""Resolves app/schemas/enums.py::CollectionSource for a collection being
created — always server-side, never trusted from client input. Two
shapes:

- A standalone creation call site (POST /v1/collections/wallet-push,
  /selcom-pesa, /qr, or the legacy Merchant Portal dashboard-push
  endpoints) already knows its own source outright — no lookup needed.
- A payment-page-resolved collection (any method chosen on a payment
  link's public page, via app/services/collection_payment.py) derives
  it from the payment_links row it's linked through:
  invoice-linked -> INVOICE; created via POST /v1/collections (an API
  key) -> API_PAYMENT_PAGE; created via Merchant Portal's "Request
  Collection" form -> DASHBOARD_REQUEST; otherwise a genuine Payment
  Link -> PAYMENT_LINK.
"""

from supabase import Client

from app.schemas.enums import CollectionSource
from app.services.crud import execute_maybe_single


def resolve_payment_link_collection_source(client: Client, *, payment_link: dict) -> CollectionSource:
    is_invoice_link = execute_maybe_single(
        client.table("invoices").select("id").eq("payment_link_id", payment_link["id"]).maybe_single()
    )
    if is_invoice_link:
        return CollectionSource.INVOICE
    if payment_link.get("api_key_id"):
        return CollectionSource.API_PAYMENT_PAGE
    if payment_link.get("created_via") == "request_collection":
        return CollectionSource.DASHBOARD_REQUEST
    return CollectionSource.PAYMENT_LINK


def resolve_invoice_id_for_payment_link(client: Client, *, payment_link_id: str) -> str | None:
    """Companion to resolve_payment_link_collection_source's own
    invoice-link lookup — a collection resolved through an invoice's "Pay
    Now" link must carry that invoice's id (not just its payment_link_id)
    so collections.invoice_id is a reliable ownership/reporting join,
    matching every other collection-creation call site."""
    invoice = execute_maybe_single(
        client.table("invoices").select("id").eq("payment_link_id", payment_link_id).maybe_single()
    )
    return invoice["id"] if invoice else None
