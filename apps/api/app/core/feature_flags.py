"""MVP launch kill switches — FastAPI dependencies for
Settings.enable_collections / enable_withdrawals / enable_merchant_api_keys
(see settings.py, "Production safety switches"). Add
`Depends(require_collections_enabled)` etc. to any endpoint that *creates*
a collection/withdrawal/API key; never to a read/list endpoint — existing
records must always remain viewable even while a flag is off.

Deliberately simple function dependencies (not middleware) so each flag
only ever gates the specific write endpoints it's meant to, and the gate
is visible directly in each router's own Depends(...) list rather than
buried in shared middleware.
"""

from app.config import get_settings
from app.core.errors import FeatureDisabledError


def require_collections_enabled() -> None:
    if not get_settings().enable_collections:
        raise FeatureDisabledError("Collections are temporarily paused. Please try again later.")


def require_withdrawals_enabled() -> None:
    if not get_settings().enable_withdrawals:
        raise FeatureDisabledError("Withdrawal requests are temporarily paused. Please try again later.")


def require_merchant_api_keys_enabled() -> None:
    if not get_settings().enable_merchant_api_keys:
        raise FeatureDisabledError("API key management is temporarily paused. Please try again later.")
