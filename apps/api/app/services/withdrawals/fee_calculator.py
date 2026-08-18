"""Dynamic, per-merchant withdrawal fee calculation.

Looks up the most specific active merchant_pricing_rules row for a given
merchant + channel + destination, then computes the fee breakdown a
merchant sees on POST /v1/merchant/withdrawals/quote and that gets frozen
onto a withdrawal at submission time (execute_disbursement in
app/services/disbursements.py) — see FeeBreakdown/pricing_snapshot_json.

Precedence (most to least specific):
  1. merchant + destination_code
  2. merchant + channel (destination_code null)
  3. merchant default (channel and destination_code both null)
  4. platform fallback (merchant_id null), itself searched in the same
     destination -> channel -> generic order — a robustness addition
     beyond the literal 4-tier spec, so a platform-wide per-channel
     default (e.g. "bank transfers cost more everywhere") can still beat
     a fully generic platform rule.

If no rule matches at all (not even a platform fallback configured), the
fee is zero everywhere — matches today's pre-pricing-engine behavior
rather than blocking a withdrawal for missing configuration.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from supabase import Client

from app.schemas.enums import DestinationCode, DisbursementMethod
from app.schemas.withdrawals import FeeBreakdown


def _parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _query_candidates(
    client: Client, *, merchant_id: uuid.UUID | None, channel: str | None, destination_code: str | None
) -> list[dict]:
    query = client.table("merchant_pricing_rules").select("*").eq("is_active", True)
    query = query.eq("merchant_id", str(merchant_id)) if merchant_id else query.is_("merchant_id", "null")
    query = query.eq("channel", channel) if channel else query.is_("channel", "null")
    query = (
        query.eq("destination_code", destination_code) if destination_code else query.is_("destination_code", "null")
    )
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
    # avoids an arbitrary/undefined pick).
    return max(live, key=lambda r: r["created_at"])


def find_pricing_rule(
    client: Client,
    *,
    merchant_id: uuid.UUID,
    channel: DisbursementMethod | str,
    destination_code: DestinationCode | str,
) -> dict | None:
    channel_value = channel.value if isinstance(channel, DisbursementMethod) else channel
    destination_value = destination_code.value if isinstance(destination_code, DestinationCode) else destination_code
    now = datetime.now(timezone.utc)

    tiers: list[tuple[uuid.UUID | None, str | None, str | None]] = [
        (merchant_id, channel_value, destination_value),
        (merchant_id, channel_value, None),
        (merchant_id, None, None),
        (None, channel_value, destination_value),
        (None, channel_value, None),
        (None, None, None),
    ]
    for tier_merchant_id, tier_channel, tier_destination in tiers:
        candidates = _query_candidates(
            client, merchant_id=tier_merchant_id, channel=tier_channel, destination_code=tier_destination
        )
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


def calculate_withdrawal_fee(
    client: Client,
    *,
    merchant_id: uuid.UUID,
    amount: Decimal,
    channel: DisbursementMethod | str,
    destination_code: DestinationCode | str,
) -> FeeBreakdown:
    channel_value = channel.value if isinstance(channel, DisbursementMethod) else channel
    destination_value = destination_code.value if isinstance(destination_code, DestinationCode) else destination_code

    rule = find_pricing_rule(client, merchant_id=merchant_id, channel=channel_value, destination_code=destination_value)

    if rule is None:
        return FeeBreakdown(
            withdrawal_amount=amount,
            processor_charge=Decimal(0),
            infinity_fee=Decimal(0),
            percentage_fee=Decimal(0),
            flat_fee=Decimal(0),
            total_charges=Decimal(0),
            total_reserved_amount=amount,
            recipient_net_amount=amount,
            channel=channel_value,
            destination_code=destination_value,
            pricing_rule_id=None,
            pricing_rule_label=None,
            processor_fee_pass_through=False,
        )

    percentage_fee = (amount * Decimal(str(rule["percentage_fee"])) / Decimal(100)).quantize(Decimal("0.01"))
    flat_fee = Decimal(str(rule["flat_fee"]))
    minimum_fee = Decimal(str(rule["minimum_fee"])) if rule.get("minimum_fee") is not None else None
    maximum_fee = Decimal(str(rule["maximum_fee"])) if rule.get("maximum_fee") is not None else None
    infinity_fee = _clamp(percentage_fee + flat_fee, minimum=minimum_fee, maximum=maximum_fee)

    processor_pass_through = bool(rule["processor_fee_pass_through"])
    processor_charge = Decimal(str(rule["processor_fee_flat"])) if processor_pass_through else Decimal(0)

    total_charges = infinity_fee + processor_charge

    return FeeBreakdown(
        withdrawal_amount=amount,
        processor_charge=processor_charge,
        infinity_fee=infinity_fee,
        percentage_fee=percentage_fee,
        flat_fee=flat_fee,
        total_charges=total_charges,
        total_reserved_amount=amount + total_charges,
        recipient_net_amount=amount,
        channel=channel_value,
        destination_code=destination_value,
        pricing_rule_id=uuid.UUID(rule["id"]),
        pricing_rule_label=rule.get("label"),
        processor_fee_pass_through=processor_pass_through,
        is_platform_fallback=rule.get("merchant_id") is None,
    )
