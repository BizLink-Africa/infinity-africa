"""app/core/feature_flags.py — MVP launch kill switches
(Settings.enable_collections/enable_withdrawals/enable_merchant_api_keys).
Unit-level coverage of the shared dependency functions themselves;
tests/test_disbursements.py, tests/test_collections_api.py, and
tests/test_merchant_portal_api_keys.py (wherever each already exists) cover
that the flags are actually wired onto the right endpoints, not just that
the functions raise correctly in isolation.
"""

import pytest

from app.config import get_settings
from app.core.errors import FeatureDisabledError
from app.core.feature_flags import (
    require_collections_enabled,
    require_merchant_api_keys_enabled,
    require_withdrawals_enabled,
)


@pytest.fixture(autouse=True)
def _reset_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_require_collections_enabled_is_a_noop_by_default():
    require_collections_enabled()  # must not raise


def test_require_collections_enabled_raises_when_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_COLLECTIONS", "false")
    get_settings.cache_clear()

    with pytest.raises(FeatureDisabledError):
        require_collections_enabled()


def test_require_withdrawals_enabled_is_a_noop_by_default():
    require_withdrawals_enabled()


def test_require_withdrawals_enabled_raises_when_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_WITHDRAWALS", "false")
    get_settings.cache_clear()

    with pytest.raises(FeatureDisabledError):
        require_withdrawals_enabled()


def test_require_merchant_api_keys_enabled_is_a_noop_by_default():
    require_merchant_api_keys_enabled()


def test_require_merchant_api_keys_enabled_raises_when_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_MERCHANT_API_KEYS", "false")
    get_settings.cache_clear()

    with pytest.raises(FeatureDisabledError):
        require_merchant_api_keys_enabled()


def test_feature_disabled_error_is_503_not_403_or_409():
    """Distinguishes a platform-wide pause from a caller-specific
    permission (403) or a data conflict (409) — see the error class's
    own docstring."""
    err = FeatureDisabledError("test")
    assert err.status_code == 503
    assert err.code == "feature_disabled"
