"""Dynamic, per-merchant COLLECTION fee calculation
(merchant_collection_pricing_rules) — the collection-side counterpart to
app/services/withdrawals/fee_calculator.py, which (as of the 2026-08-31
"fees apply to collections only" policy) no longer charges anything.

Looks up the most specific active merchant_collection_pricing_rules row
for a given merchant + collection channel, then computes the fee a
collection is credited net of — called from
app/services/collections.py::create_processing_transaction, the single
chokepoint every collection flow (Request Collection, Wallet Push, Push
to Selcom Pesa, TanQR, Payment Links, Pay by Link, Invoices, API
collections) already funnels through.

Precedence (most to least specific):
  1. merchant + channel
  2. merchant default (channel null)
  3. platform fallback + channel (merchant_id null)
  4. platform fallback, fully generic (merchant_id null, channel null)

If no row matches at all (not even a platform fallback configured), this
falls back to settings.platform_fee_percentage — the flat, single global
rate collections have always used before this per-merchant engine
existed. That preserves 100% backward compatibility: a merchant nobody
has explicitly priced yet keeps seeing exactly the rate they always did,
never a silent 0%.
"""

import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from supabase import Client

from app.config import get_settings
from app.schemas.enums import CollectionMethod


def _parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _query_candidates(client: Client, *, merchant_id: uuid.UUID | None, channel: str | None) -> list[dict]:
    query = client.table("merchant_collection_pricing_rules").select("*").eq("is_active", True)
    query = query.eq("merchant_id", str(merchant_id)) if merchant_id else query.is_("merchant_id", "null")
    query = query.eq("channel", channel) if channel else query.is_("channel", "null")
    result = query.execute()
    return result.data or []


def _pick_active_now(candidates: list[dict], now: datetime) -> dict | None:
    live = []
    for rule in candidates:
        if _parse_dt(rule["effective_from"]) > now:
            continue
        effective_to = rule.get("effective_to")
        if effective_to is not None and _parse_dt(effective_to) <= now:
            continue
        live.append(rule)
    if not live:
        return None
    # Most-recently-created wins if more than one active rule somehow
    # matches the same tier (shouldn't happen for well-formed data, but
    # avoids an arbitrary/undefined pick) — same convention as
    # app/services/withdrawals/fee_calculator.py::_pick_active_now.
    return max(live, key=lambda r: r["created_at"])


def find_collection_pricing_rule(
    client: Client, *, merchant_id: uuid.UUID, channel: CollectionMethod | str | None
) -> dict | None:
    channel_value = channel.value if isinstance(channel, CollectionMethod) else channel
    now = datetime.now(timezone.utc)

    tiers: list[tuple[uuid.UUID | None, str | None]] = [
        (merchant_id, channel_value),
        (merchant_id, None),
        (None, channel_value),
        (None, None),
    ]
    for tier_merchant_id, tier_channel in tiers:
        candidates = _query_candidates(client, merchant_id=tier_merchant_id, channel=tier_channel)
        rule = _pick_active_now(candidates, now)
        if rule:
            return rule
    return None


def _clamp(value: Decimal, *, minimum: Decimal | None, maximum: Decimal | None) -> Decimal:
    if minimum is not None and value < minimum:
        value = minimum
    if maximum is not None and value > maximum:
        value = maximum
    return value


def calculate_collection_fee(
    client: Client, *, merchant_id: uuid.UUID, amount: Decimal, channel: CollectionMethod | str | None
) -> Decimal:
    """Returns the fee amount only (not a full breakdown struct) — the
    one thing app/services/collections.py::create_processing_transaction
    actually needs; net_amount = amount - fee is computed there, exactly
    as before this per-merchant engine existed.

    Backend-only, never trusts any client-supplied fee/net value — the
    caller passes merchant_id resolved server-side from the
    authenticated request, never from request body input (see
    create_processing_transaction's own callers)."""
    rule = find_collection_pricing_rule(client, merchant_id=merchant_id, channel=channel)

    if rule is None:
        return (amount * get_settings().platform_fee_percentage / Decimal(100)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    percentage_fee = (amount * Decimal(str(rule["percentage_fee"])) / Decimal(100)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    flat_fee = Decimal(str(rule["flat_fee"]))
    minimum_fee = Decimal(str(rule["minimum_fee"])) if rule.get("minimum_fee") is not None else None
    maximum_fee = Decimal(str(rule["maximum_fee"])) if rule.get("maximum_fee") is not None else None
    return _clamp(percentage_fee + flat_fee, minimum=minimum_fee, maximum=maximum_fee)
