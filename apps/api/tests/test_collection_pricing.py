"""app/services/collection_pricing.py — per-merchant collection fee math
and precedence, against the in-memory FakeSupabaseClient. Mirrors
test_fee_calculator.py's structure (the withdrawal-side sibling).
"""

import uuid
from decimal import Decimal

from app.config import get_settings
from app.services.collection_pricing import (
    calculate_collection_fee,
    find_collection_pricing_rule,
)
from tests.factories import create_collection_pricing_rule, create_merchant


def _merchant_id(fake_client) -> uuid.UUID:
    return uuid.UUID(create_merchant(fake_client)["id"])


# --- calculate_collection_fee: math -------------------------------------------


def test_no_rule_falls_back_to_the_flat_platform_percentage(fake_client, monkeypatch):
    """Backward compatibility: a merchant nobody has explicitly priced
    yet keeps seeing exactly the same flat rate collections have always
    used, never a silent 0%."""
    monkeypatch.setenv("PLATFORM_FEE_PERCENTAGE", "1.5")
    get_settings.cache_clear()
    merchant_id = _merchant_id(fake_client)

    fee = calculate_collection_fee(fake_client, merchant_id=merchant_id, amount=Decimal(100000), channel="STK_PUSH")

    assert fee == Decimal("1500.00")
    get_settings.cache_clear()


def test_percentage_fee(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_collection_pricing_rule(fake_client, merchant_id=merchant_id, percentage_fee="0.4")

    fee = calculate_collection_fee(fake_client, merchant_id=merchant_id, amount=Decimal(10000), channel="STK_PUSH")

    assert fee == Decimal("40.00")


def test_worked_examples_from_spec(fake_client):
    """Merchant A/B/C negotiated rates from the feature spec: TZS 10,000
    collected at 0.4% / 0.8% / 2.0% yields TZS 40 / 80 / 200 fee and TZS
    9,960 / 9,920 / 9,800 net credit."""
    for rate, expected_fee, expected_net in [
        ("0.4", Decimal("40.00"), Decimal("9960.00")),
        ("0.8", Decimal("80.00"), Decimal("9920.00")),
        ("2.0", Decimal("200.00"), Decimal("9800.00")),
    ]:
        merchant_id = _merchant_id(fake_client)
        create_collection_pricing_rule(fake_client, merchant_id=merchant_id, percentage_fee=rate)

        fee = calculate_collection_fee(
            fake_client, merchant_id=merchant_id, amount=Decimal(10000), channel="STK_PUSH"
        )

        assert fee == expected_fee
        assert Decimal(10000) - fee == expected_net


def test_flat_fee(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_collection_pricing_rule(fake_client, merchant_id=merchant_id, flat_fee="150")

    fee = calculate_collection_fee(fake_client, merchant_id=merchant_id, amount=Decimal(10000), channel="STK_PUSH")

    assert fee == Decimal(150)


def test_minimum_fee_applies(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_collection_pricing_rule(fake_client, merchant_id=merchant_id, percentage_fee="0.4", minimum_fee="100")

    # 0.4% of 10,000 = 40, below the 100 floor.
    fee = calculate_collection_fee(fake_client, merchant_id=merchant_id, amount=Decimal(10000), channel="STK_PUSH")

    assert fee == Decimal(100)


def test_maximum_fee_applies(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_collection_pricing_rule(fake_client, merchant_id=merchant_id, percentage_fee="2", maximum_fee="5000")

    # 2% of 1,000,000 = 20,000, capped at 5,000.
    fee = calculate_collection_fee(fake_client, merchant_id=merchant_id, amount=Decimal(1000000), channel="STK_PUSH")

    assert fee == Decimal(5000)


# --- precedence -----------------------------------------------------------------


def test_channel_specific_rule_overrides_merchant_default(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_collection_pricing_rule(fake_client, merchant_id=merchant_id, percentage_fee="1", label="default")
    create_collection_pricing_rule(
        fake_client, merchant_id=merchant_id, channel="HOSTED_CHECKOUT", percentage_fee="0.5", label="channel"
    )

    rule = find_collection_pricing_rule(fake_client, merchant_id=merchant_id, channel="HOSTED_CHECKOUT")
    assert rule["label"] == "channel"


def test_merchant_default_overrides_platform_fallback(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_collection_pricing_rule(fake_client, merchant_id=None, percentage_fee="5", label="platform")
    create_collection_pricing_rule(fake_client, merchant_id=merchant_id, percentage_fee="0.8", label="merchant-default")

    rule = find_collection_pricing_rule(fake_client, merchant_id=merchant_id, channel="STK_PUSH")
    assert rule["label"] == "merchant-default"


def test_platform_fallback_used_when_merchant_has_no_rule(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_collection_pricing_rule(fake_client, merchant_id=None, percentage_fee="0.8", label="platform")

    rule = find_collection_pricing_rule(fake_client, merchant_id=merchant_id, channel="STK_PUSH")
    assert rule["label"] == "platform"


def test_platform_channel_rule_overrides_platform_generic_rule(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_collection_pricing_rule(fake_client, merchant_id=None, percentage_fee="5", label="platform-generic")
    create_collection_pricing_rule(
        fake_client, merchant_id=None, channel="DYNAMIC_QR", percentage_fee="1", label="platform-channel"
    )

    rule = find_collection_pricing_rule(fake_client, merchant_id=merchant_id, channel="DYNAMIC_QR")
    assert rule["label"] == "platform-channel"


def test_inactive_rule_is_skipped(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_collection_pricing_rule(
        fake_client, merchant_id=merchant_id, percentage_fee="5", is_active=False, label="inactive"
    )
    create_collection_pricing_rule(fake_client, merchant_id=None, percentage_fee="0.8", label="platform")

    rule = find_collection_pricing_rule(fake_client, merchant_id=merchant_id, channel="STK_PUSH")
    assert rule["label"] == "platform"


def test_not_yet_effective_rule_is_skipped(fake_client):
    merchant_id = _merchant_id(fake_client)
    future = "2099-01-01T00:00:00+00:00"
    create_collection_pricing_rule(
        fake_client, merchant_id=merchant_id, percentage_fee="5", effective_from=future, label="future"
    )
    create_collection_pricing_rule(fake_client, merchant_id=None, percentage_fee="0.8", label="platform")

    rule = find_collection_pricing_rule(fake_client, merchant_id=merchant_id, channel="STK_PUSH")
    assert rule["label"] == "platform"


def test_expired_rule_is_skipped(fake_client):
    merchant_id = _merchant_id(fake_client)
    create_collection_pricing_rule(
        fake_client,
        merchant_id=merchant_id,
        percentage_fee="5",
        effective_from="2020-01-01T00:00:00+00:00",
        effective_to="2020-06-01T00:00:00+00:00",
        label="expired",
    )
    create_collection_pricing_rule(fake_client, merchant_id=None, percentage_fee="0.8", label="platform")

    rule = find_collection_pricing_rule(fake_client, merchant_id=merchant_id, channel="STK_PUSH")
    assert rule["label"] == "platform"


def test_different_merchants_can_have_different_rates_at_once(fake_client):
    """Core requirement: pricing is negotiated separately per merchant —
    two merchants' rules must never interfere with each other."""
    merchant_a = _merchant_id(fake_client)
    merchant_b = _merchant_id(fake_client)
    create_collection_pricing_rule(fake_client, merchant_id=merchant_a, percentage_fee="0.4")
    create_collection_pricing_rule(fake_client, merchant_id=merchant_b, percentage_fee="2.0")

    fee_a = calculate_collection_fee(fake_client, merchant_id=merchant_a, amount=Decimal(10000), channel="STK_PUSH")
    fee_b = calculate_collection_fee(fake_client, merchant_id=merchant_b, amount=Decimal(10000), channel="STK_PUSH")

    assert fee_a == Decimal("40.00")
    assert fee_b == Decimal("200.00")
