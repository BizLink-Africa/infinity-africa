"""app/services/withdrawals/fee_calculator.py:

- calculate_withdrawal_fee — MVP policy (2026-08-31): always zero fees,
  regardless of any merchant_pricing_rules row that exists. See its own
  docstring for why a configured rule is never consulted for the amount
  math anymore.
- find_pricing_rule — the precedence lookup itself is unchanged and
  still exercised (app/services/api_access.py::has_resolvable_pricing_rule
  uses it as a production-API-eligibility gate, unrelated to fees) — its
  own precedence tests below are untouched by the fee-policy change.
"""

import uuid
from decimal import Decimal

from app.services.withdrawals.fee_calculator import (
    calculate_withdrawal_fee,
    find_pricing_rule,
)
from tests.factories import create_merchant, create_pricing_rule


def _merchant_id(fake_client) -> uuid.UUID:
    return uuid.UUID(create_merchant(fake_client)["id"])


# --- calculate_withdrawal_fee: always zero, regardless of configuration -------


def test_no_rule_at_all_means_zero_fee(fake_client):
    merchant_id = _merchant_id(fake_client)

    breakdown = calculate_withdrawal_fee(
        fake_client, merchant_id=merchant_id, amount=Decimal(100000), channel="MOBILE_MONEY", destination_code="MPESA"
    )

    assert breakdown.infinity_fee == Decimal(0)
    assert breakdown.processor_charge == Decimal(0)
    assert breakdown.total_charges == Decimal(0)
    assert breakdown.total_reserved_amount == Decimal(100000)
    assert breakdown.recipient_net_amount == Decimal(100000)
    assert breakdown.pricing_rule_id is None


def test_configured_percentage_fee_is_not_applied(fake_client):
    """A merchant_pricing_rules row with a real percentage fee still
    exists (e.g. left over from before this policy, or configured by
    mistake) — calculate_withdrawal_fee must not apply it."""
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(fake_client, merchant_id=merchant_id, percentage_fee="1")

    breakdown = calculate_withdrawal_fee(
        fake_client, merchant_id=merchant_id, amount=Decimal(100000), channel="MOBILE_MONEY", destination_code="MPESA"
    )

    assert breakdown.percentage_fee == Decimal(0)
    assert breakdown.infinity_fee == Decimal(0)
    assert breakdown.total_reserved_amount == Decimal(100000)


def test_configured_flat_fee_is_not_applied(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(fake_client, merchant_id=merchant_id, flat_fee="1500")

    breakdown = calculate_withdrawal_fee(
        fake_client, merchant_id=merchant_id, amount=Decimal(100000), channel="BANK_ACCOUNT", destination_code="CRDB"
    )

    assert breakdown.flat_fee == Decimal(0)
    assert breakdown.infinity_fee == Decimal(0)


def test_configured_minimum_fee_is_not_applied(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(fake_client, merchant_id=merchant_id, percentage_fee="1", minimum_fee="2000")

    breakdown = calculate_withdrawal_fee(
        fake_client, merchant_id=merchant_id, amount=Decimal(10000), channel="MOBILE_MONEY", destination_code="MPESA"
    )

    assert breakdown.infinity_fee == Decimal(0)


def test_configured_maximum_fee_is_not_applied(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(fake_client, merchant_id=merchant_id, percentage_fee="5", maximum_fee="3000")

    breakdown = calculate_withdrawal_fee(
        fake_client, merchant_id=merchant_id, amount=Decimal(1000000), channel="MOBILE_MONEY", destination_code="MPESA"
    )

    assert breakdown.infinity_fee == Decimal(0)


def test_configured_processor_charge_pass_through_is_not_applied(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(fake_client, merchant_id=merchant_id, processor_fee_flat="300", processor_fee_pass_through=True)

    breakdown = calculate_withdrawal_fee(
        fake_client, merchant_id=merchant_id, amount=Decimal(100000), channel="MOBILE_MONEY", destination_code="MPESA"
    )

    assert breakdown.processor_charge == Decimal(0)
    assert breakdown.total_charges == Decimal(0)


def test_fully_configured_rule_still_yields_zero_charges_and_full_recipient_amount(fake_client):
    """Same scenario test_worked_example_from_spec used to exercise
    non-zero math for (1% + TZS 500 flat + TZS 300 processor pass-
    through) — now every one of those must be ignored: zero total
    charges, and the merchant's wallet reserves/debits exactly the
    requested amount, not amount + fees."""
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(
        fake_client,
        merchant_id=merchant_id,
        percentage_fee="1",
        flat_fee="500",
        processor_fee_flat="300",
        processor_fee_pass_through=True,
    )

    breakdown = calculate_withdrawal_fee(
        fake_client, merchant_id=merchant_id, amount=Decimal(100000), channel="MOBILE_MONEY", destination_code="MPESA"
    )

    assert breakdown.total_charges == Decimal(0)
    assert breakdown.total_reserved_amount == Decimal(100000)
    assert breakdown.recipient_net_amount == Decimal(100000)
    # Also confirms the breakdown no longer references the rule that
    # would otherwise have applied — the amount math is entirely
    # independent of merchant_pricing_rules now.
    assert breakdown.pricing_rule_id is None
    assert breakdown.is_platform_fallback is False


def test_platform_fallback_rule_is_also_not_applied(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(fake_client, merchant_id=None, flat_fee="9999", percentage_fee="10", label="platform")

    breakdown = calculate_withdrawal_fee(
        fake_client, merchant_id=merchant_id, amount=Decimal(100000), channel="MOBILE_MONEY", destination_code="MPESA"
    )

    assert breakdown.total_charges == Decimal(0)
    assert breakdown.total_reserved_amount == Decimal(100000)
    assert breakdown.is_platform_fallback is False
    assert breakdown.pricing_rule_id is None
    assert breakdown.pricing_rule_label is None


# --- find_pricing_rule precedence (unrelated to fees — the eligibility gate
# in app/services/api_access.py still relies on this exact logic) -------------


def test_destination_specific_rule_overrides_channel_rule(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(fake_client, merchant_id=merchant_id, channel="MOBILE_MONEY", flat_fee="1000", label="channel")
    create_pricing_rule(
        fake_client,
        merchant_id=merchant_id,
        channel="MOBILE_MONEY",
        destination_code="MPESA",
        flat_fee="250",
        label="destination",
    )

    rule = find_pricing_rule(fake_client, merchant_id=merchant_id, channel="MOBILE_MONEY", destination_code="MPESA")
    assert rule["label"] == "destination"


def test_channel_rule_overrides_merchant_default(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(fake_client, merchant_id=merchant_id, flat_fee="1000", label="default")
    create_pricing_rule(fake_client, merchant_id=merchant_id, channel="BANK_ACCOUNT", flat_fee="1500", label="channel")

    rule = find_pricing_rule(fake_client, merchant_id=merchant_id, channel="BANK_ACCOUNT", destination_code="CRDB")
    assert rule["label"] == "channel"


def test_merchant_default_overrides_platform_fallback(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(fake_client, merchant_id=None, flat_fee="9999", label="platform")
    create_pricing_rule(fake_client, merchant_id=merchant_id, flat_fee="500", label="merchant-default")

    rule = find_pricing_rule(fake_client, merchant_id=merchant_id, channel="MOBILE_MONEY", destination_code="MPESA")
    assert rule["label"] == "merchant-default"


def test_platform_fallback_used_when_merchant_has_no_rule(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(fake_client, merchant_id=None, flat_fee="9999", label="platform")

    rule = find_pricing_rule(fake_client, merchant_id=merchant_id, channel="MOBILE_MONEY", destination_code="MPESA")
    assert rule["label"] == "platform"


def test_inactive_rule_is_skipped(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(fake_client, merchant_id=merchant_id, flat_fee="500", is_active=False, label="inactive")
    create_pricing_rule(fake_client, merchant_id=None, flat_fee="100", label="platform")

    rule = find_pricing_rule(fake_client, merchant_id=merchant_id, channel="MOBILE_MONEY", destination_code="MPESA")
    assert rule["label"] == "platform"


def test_not_yet_effective_rule_is_skipped(fake_client):
    merchant_id = _merchant_id(fake_client)
    future = "2099-01-01T00:00:00+00:00"
    create_pricing_rule(fake_client, merchant_id=merchant_id, flat_fee="500", effective_from=future, label="future")
    create_pricing_rule(fake_client, merchant_id=None, flat_fee="100", label="platform")

    rule = find_pricing_rule(fake_client, merchant_id=merchant_id, channel="MOBILE_MONEY", destination_code="MPESA")
    assert rule["label"] == "platform"


def test_expired_rule_is_skipped(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(
        fake_client,
        merchant_id=merchant_id,
        flat_fee="500",
        effective_from="2020-01-01T00:00:00+00:00",
        effective_to="2020-06-01T00:00:00+00:00",
        label="expired",
    )
    create_pricing_rule(fake_client, merchant_id=None, flat_fee="100", label="platform")

    rule = find_pricing_rule(fake_client, merchant_id=merchant_id, channel="MOBILE_MONEY", destination_code="MPESA")
    assert rule["label"] == "platform"


def test_most_recently_created_rule_wins_within_same_tier(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(
        fake_client, merchant_id=merchant_id, flat_fee="500", label="older", created_at="2026-01-01T00:00:00+00:00"
    )
    create_pricing_rule(
        fake_client, merchant_id=merchant_id, flat_fee="750", label="newer", created_at="2026-06-01T00:00:00+00:00"
    )

    rule = find_pricing_rule(fake_client, merchant_id=merchant_id, channel="MOBILE_MONEY", destination_code="MPESA")
    assert rule["label"] == "newer"


def test_platform_destination_specific_rule_overrides_platform_channel_rule(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(fake_client, merchant_id=None, channel="MOBILE_MONEY", flat_fee="1000", label="platform-channel")
    create_pricing_rule(
        fake_client,
        merchant_id=None,
        channel="MOBILE_MONEY",
        destination_code="MPESA",
        flat_fee="250",
        label="platform-destination",
    )

    rule = find_pricing_rule(fake_client, merchant_id=merchant_id, channel="MOBILE_MONEY", destination_code="MPESA")
    assert rule["label"] == "platform-destination"


def test_platform_channel_rule_overrides_platform_generic_rule(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(fake_client, merchant_id=None, flat_fee="9999", label="platform-generic")
    create_pricing_rule(fake_client, merchant_id=None, channel="BANK_ACCOUNT", flat_fee="1500", label="platform-channel")

    rule = find_pricing_rule(fake_client, merchant_id=merchant_id, channel="BANK_ACCOUNT", destination_code="CRDB")
    assert rule["label"] == "platform-channel"
