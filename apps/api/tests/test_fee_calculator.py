"""app/services/withdrawals/fee_calculator.py — fee math and pricing-rule
precedence, against the in-memory FakeSupabaseClient.
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


def test_no_rule_at_all_means_zero_fee(fake_client):
    merchant_id = _merchant_id(fake_client)

    breakdown = calculate_withdrawal_fee(
        fake_client, merchant_id=merchant_id, amount=Decimal(100000), channel="MOBILE_MONEY", destination_code="MPESA"
    )

    assert breakdown.infinity_fee == Decimal(0)
    assert breakdown.processor_charge == Decimal(0)
    assert breakdown.total_charges == Decimal(0)
    assert breakdown.total_reserved_amount == Decimal(100000)
    assert breakdown.pricing_rule_id is None


def test_percentage_fee(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(fake_client, merchant_id=merchant_id, percentage_fee="1")

    breakdown = calculate_withdrawal_fee(
        fake_client, merchant_id=merchant_id, amount=Decimal(100000), channel="MOBILE_MONEY", destination_code="MPESA"
    )

    assert breakdown.percentage_fee == Decimal("1000.00")
    assert breakdown.infinity_fee == Decimal("1000.00")
    assert breakdown.total_reserved_amount == Decimal("101000.00")


def test_flat_fee(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(fake_client, merchant_id=merchant_id, flat_fee="1500")

    breakdown = calculate_withdrawal_fee(
        fake_client, merchant_id=merchant_id, amount=Decimal(100000), channel="BANK_ACCOUNT", destination_code="CRDB"
    )

    assert breakdown.flat_fee == Decimal(1500)
    assert breakdown.infinity_fee == Decimal(1500)


def test_minimum_fee_applies(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(fake_client, merchant_id=merchant_id, percentage_fee="1", minimum_fee="2000")

    breakdown = calculate_withdrawal_fee(
        fake_client, merchant_id=merchant_id, amount=Decimal(10000), channel="MOBILE_MONEY", destination_code="MPESA"
    )

    # 1% of 10000 = 100, below the 2000 floor.
    assert breakdown.infinity_fee == Decimal(2000)


def test_maximum_fee_applies(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(fake_client, merchant_id=merchant_id, percentage_fee="5", maximum_fee="3000")

    breakdown = calculate_withdrawal_fee(
        fake_client, merchant_id=merchant_id, amount=Decimal(1000000), channel="MOBILE_MONEY", destination_code="MPESA"
    )

    # 5% of 1,000,000 = 50,000, capped at 3,000.
    assert breakdown.infinity_fee == Decimal(3000)


def test_processor_charge_only_included_when_pass_through_enabled(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(fake_client, merchant_id=merchant_id, processor_fee_flat="300", processor_fee_pass_through=False)

    breakdown = calculate_withdrawal_fee(
        fake_client, merchant_id=merchant_id, amount=Decimal(100000), channel="MOBILE_MONEY", destination_code="MPESA"
    )

    assert breakdown.processor_charge == Decimal(0)
    assert breakdown.processor_fee_pass_through is False


def test_processor_charge_included_when_pass_through_enabled(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(fake_client, merchant_id=merchant_id, processor_fee_flat="300", processor_fee_pass_through=True)

    breakdown = calculate_withdrawal_fee(
        fake_client, merchant_id=merchant_id, amount=Decimal(100000), channel="MOBILE_MONEY", destination_code="MPESA"
    )

    assert breakdown.processor_charge == Decimal(300)
    assert breakdown.total_charges == breakdown.infinity_fee + Decimal(300)


def test_worked_example_from_spec(fake_client):
    """TZS 100,000 withdrawal; 1% Infinity fee + TZS 500 flat + TZS 300
    processor charge = TZS 1,800 total charges; TZS 101,800 reserved;
    recipient receives TZS 100,000."""
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

    assert breakdown.total_charges == Decimal("1800.00")
    assert breakdown.total_reserved_amount == Decimal("101800.00")
    assert breakdown.recipient_net_amount == Decimal(100000)


# --- precedence -----------------------------------------------------------------


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


# --- is_platform_fallback flag on the fee breakdown ---------------------------


def test_breakdown_flags_platform_fallback_when_no_merchant_rule_exists(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(fake_client, merchant_id=None, flat_fee="100", label="platform")

    breakdown = calculate_withdrawal_fee(
        fake_client, merchant_id=merchant_id, amount=Decimal(100000), channel="MOBILE_MONEY", destination_code="MPESA"
    )

    assert breakdown.is_platform_fallback is True
    assert breakdown.pricing_rule_label == "platform"


def test_breakdown_does_not_flag_merchant_specific_rule_as_fallback(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(fake_client, merchant_id=None, flat_fee="9999", label="platform")
    create_pricing_rule(fake_client, merchant_id=merchant_id, flat_fee="500", label="merchant-default")

    breakdown = calculate_withdrawal_fee(
        fake_client, merchant_id=merchant_id, amount=Decimal(100000), channel="MOBILE_MONEY", destination_code="MPESA"
    )

    assert breakdown.is_platform_fallback is False
    assert breakdown.pricing_rule_label == "merchant-default"


def test_breakdown_does_not_flag_fallback_when_no_rule_matches_at_all(fake_client):
    merchant_id = _merchant_id(fake_client)

    breakdown = calculate_withdrawal_fee(
        fake_client, merchant_id=merchant_id, amount=Decimal(100000), channel="MOBILE_MONEY", destination_code="MPESA"
    )

    assert breakdown.is_platform_fallback is False
    assert breakdown.pricing_rule_id is None
