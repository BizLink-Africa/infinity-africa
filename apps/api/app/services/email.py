"""Transactional email via Resend. RESEND_API_KEY is backend/Railway-only
— apps/web never reads it (nothing in apps/web ever imports this module or
its config). See docs/email-delivery.md.

Every send — success or failure — is logged to email_deliveries
(app/routers/*.py never writes that table directly). send_email() itself
never swallows a failure: it always raises EmailDeliveryError so a caller
like "send invoice" can refuse to mark anything SENT unless delivery
actually happened.
"""

import logging
from decimal import Decimal
from typing import Any

import resend
from supabase import Client

from app.config import get_settings
from app.core.errors import EmailDeliveryError
from app.services.crud import insert_row

logger = logging.getLogger("infinity.email")


def send_email(*, to: str, subject: str, html: str, sender: str, reply_to: str | None = None) -> str:
    """Sends one email through Resend. Returns the provider's message id
    (empty string if Resend didn't return one). Raises EmailDeliveryError
    on any failure — a missing API key, a rejected send, or the request
    itself failing outright. Never logs the API key; the raw exception is
    logged server-side only (not included in the message raised, which is
    safe to surface to a merchant)."""
    settings = get_settings()
    if not settings.resend_api_key:
        raise EmailDeliveryError("Email delivery is not configured yet.")

    resend.api_key = settings.resend_api_key
    params: dict[str, Any] = {"from": sender, "to": [to], "subject": subject, "html": html}
    if reply_to:
        params["reply_to"] = reply_to

    try:
        result = resend.Emails.send(params)
    except Exception:
        logger.exception("Resend send failed (to=%s, subject=%s)", to, subject)
        raise EmailDeliveryError("Couldn't send the email — the email provider rejected the request.") from None

    if isinstance(result, dict):
        return result.get("id") or ""
    return getattr(result, "id", "") or ""


def _log_delivery(
    client: Client,
    *,
    merchant_id: str | None,
    email_type: str,
    related_resource_type: str | None,
    related_resource_id: str | None,
    recipient_email: str,
    sender_email: str,
    subject: str,
    status: str,
    provider_message_id: str | None = None,
    error_message: str | None = None,
) -> dict:
    return insert_row(
        client,
        "email_deliveries",
        {
            "merchant_id": merchant_id,
            "email_type": email_type,
            "related_resource_type": related_resource_type,
            "related_resource_id": related_resource_id,
            "recipient_email": recipient_email,
            "sender_email": sender_email,
            "subject": subject,
            "provider": "resend",
            "provider_message_id": provider_message_id,
            "status": status,
            "error_message": error_message,
        },
    )


def _money(value: object, currency: str) -> str:
    amount = Decimal(str(value))
    return f"{currency} {amount:,.2f}"


def _render_invoice_email_html(*, merchant: dict, invoice: dict, items: list[dict], payment_url: str) -> str:
    """Table-based HTML with inline styles throughout — the only layout
    approach that renders consistently across real email clients (Gmail,
    Outlook, Apple Mail strip <style> blocks and most CSS unless it's
    inline). Never references the Material Symbols icon font used
    elsewhere in the app (unsupported in email); the ∞ mark is a plain
    Unicode character so it always renders."""
    settings = get_settings()
    business_name = merchant.get("business_name") or "Your merchant"
    customer_name = invoice.get("customer_name") or "Customer"
    currency = invoice.get("currency") or "TZS"
    total_amount = invoice.get("total_amount")
    due_date = invoice.get("due_date")
    notes = invoice.get("notes")

    item_rows = "".join(
        f"""
        <tr>
          <td style="padding:10px 0;border-bottom:1px solid #e5e7eb;font-size:14px;color:#1f2937;">{item.get("description", "")}</td>
          <td style="padding:10px 0;border-bottom:1px solid #e5e7eb;font-size:14px;color:#6b7280;text-align:center;">{item.get("quantity", "")}</td>
          <td style="padding:10px 0;border-bottom:1px solid #e5e7eb;font-size:14px;color:#1f2937;text-align:right;">{_money(item.get("unit_price", 0), currency)}</td>
        </tr>"""
        for item in items
    )
    items_table = (
        f"""
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:20px 0;">
          <tr>
            <th style="text-align:left;font-size:12px;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;padding-bottom:8px;border-bottom:2px solid #04332a;">Description</th>
            <th style="text-align:center;font-size:12px;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;padding-bottom:8px;border-bottom:2px solid #04332a;">Qty</th>
            <th style="text-align:right;font-size:12px;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;padding-bottom:8px;border-bottom:2px solid #04332a;">Unit Price</th>
          </tr>
          {item_rows}
        </table>"""
        if items
        else ""
    )
    due_date_row = (
        f"""
        <tr>
          <td style="padding:6px 0;font-size:14px;color:#6b7280;">Due date</td>
          <td style="padding:6px 0;font-size:14px;color:#1f2937;text-align:right;">{due_date}</td>
        </tr>"""
        if due_date
        else ""
    )
    notes_block = (
        f"""<p style="margin:16px 0 0;font-size:13px;color:#6b7280;">{notes}</p>""" if notes else ""
    )

    return f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background-color:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f5;padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background-color:#ffffff;border-radius:12px;overflow:hidden;">
            <tr>
              <td style="background-color:#04332a;padding:24px 28px;">
                <span style="font-size:20px;color:#9cf5c1;vertical-align:middle;">&#8734;</span>
                <span style="font-size:18px;font-weight:700;color:#ffffff;vertical-align:middle;margin-left:6px;">Infinity Africa</span>
              </td>
            </tr>
            <tr>
              <td style="padding:28px;">
                <p style="margin:0 0 4px;font-size:13px;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;">Payment Request</p>
                <h1 style="margin:0 0 20px;font-size:20px;color:#1f2937;">Invoice {invoice.get("invoice_number", "")} from {business_name}</h1>
                <p style="margin:0 0 20px;font-size:14px;color:#374151;">Hi {customer_name},</p>
                <p style="margin:0 0 20px;font-size:14px;color:#374151;">{business_name} has sent you an invoice via Infinity Africa. You can review the details below and pay securely online.</p>

                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f9fafb;border-radius:8px;padding:16px;margin:0 0 8px;">
                  <tr>
                    <td style="padding:6px 16px;font-size:14px;color:#6b7280;">Amount due</td>
                    <td style="padding:6px 16px;font-size:20px;font-weight:700;color:#04332a;text-align:right;">{_money(total_amount, currency)}</td>
                  </tr>
                  {due_date_row}
                </table>

                {items_table}
                {notes_block}

                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:28px 0 8px;">
                  <tr>
                    <td align="center">
                      <a href="{payment_url}" style="display:inline-block;background-color:#04332a;color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;padding:14px 32px;border-radius:8px;">Pay Now</a>
                    </td>
                  </tr>
                </table>
                <p style="margin:8px 0 0;font-size:12px;color:#9ca3af;text-align:center;word-break:break-all;">Or copy this link: <a href="{payment_url}" style="color:#04332a;">{payment_url}</a></p>

                <p style="margin:28px 0 0;font-size:13px;color:#6b7280;">Questions about this invoice? Contact {business_name} directly, or reach Infinity Africa support at <a href="mailto:{settings.email_reply_to}" style="color:#04332a;">{settings.email_reply_to}</a>.</p>
              </td>
            </tr>
            <tr>
              <td style="padding:16px 28px;background-color:#f9fafb;text-align:center;">
                <p style="margin:0;font-size:12px;color:#9ca3af;">Powered by Infinity Africa</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


def batch_latest_email_deliveries(
    client: Client, *, related_resource_type: str, related_resource_ids: set[str]
) -> dict[str, dict]:
    """resource_id -> its most recent email_deliveries row — for Super
    Admin list views that show delivery status alongside the resource
    (e.g. an invoice's Sent column). A resource can have more than one
    delivery attempt (retries after a failure); only the latest matters
    for a summary view."""
    if not related_resource_ids:
        return {}
    rows = (
        client.table("email_deliveries")
        .select("*")
        .eq("related_resource_type", related_resource_type)
        .in_("related_resource_id", list(related_resource_ids))
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    latest: dict[str, dict] = {}
    for row in rows:
        resource_id = row["related_resource_id"]
        if resource_id not in latest:
            latest[resource_id] = row
    return latest


def send_invoice_email(
    client: Client, *, merchant: dict, invoice: dict, items: list[dict], payment_url: str
) -> dict:
    """Sends the invoice payment-request email and always records an
    email_deliveries row, success or failure. Raises EmailDeliveryError
    (after logging the failure) if the send didn't go through — callers
    (the "send invoice" endpoints) must never mark an invoice SENT unless
    this returns normally.

    Caller's responsibility: invoice["customer_email"] must already be
    present — this function doesn't validate that (it's a business rule
    the router enforces before generating a payment link at all)."""
    settings = get_settings()
    recipient = invoice["customer_email"]
    business_name = merchant.get("business_name") or "Your merchant"
    subject = f"Invoice from {business_name} via Infinity Africa"
    sender = settings.invoice_email_from
    html = _render_invoice_email_html(merchant=merchant, invoice=invoice, items=items, payment_url=payment_url)

    try:
        message_id = send_email(to=recipient, subject=subject, html=html, sender=sender, reply_to=settings.email_reply_to)
    except EmailDeliveryError as exc:
        _log_delivery(
            client,
            merchant_id=merchant.get("id"),
            email_type="invoice_payment_request",
            related_resource_type="invoice",
            related_resource_id=invoice.get("id"),
            recipient_email=recipient,
            sender_email=sender,
            subject=subject,
            status="failed",
            error_message=str(exc),
        )
        raise

    return _log_delivery(
        client,
        merchant_id=merchant.get("id"),
        email_type="invoice_payment_request",
        related_resource_type="invoice",
        related_resource_id=invoice.get("id"),
        recipient_email=recipient,
        sender_email=sender,
        subject=subject,
        status="sent",
        provider_message_id=message_id or None,
    )
