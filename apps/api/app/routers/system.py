"""Platform-internal system diagnostics — /v1/system/*. Super-admin gated:
this reports whether production credentials/feature flags are configured,
which is operationally sensitive even though no secret value is ever
returned (it tells an unauthenticated caller exactly which prerequisites
for a live payment integration are or aren't in place).
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth import require_super_admin
from app.config import Settings, get_settings
from app.schemas.auth import AuthenticatedUser
from app.schemas.common import APIResponse
from app.schemas.system import SelcomConfigStatusResponse

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/selcom-config-status", response_model=APIResponse[SelcomConfigStatusResponse])
def get_selcom_config_status(
    _admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    return APIResponse(
        data=SelcomConfigStatusResponse(
            collection_enabled=settings.selcom_collection_enabled,
            withdrawal_enabled=settings.selcom_withdrawal_enabled,
            mock_mode=settings.selcom_mode != "live",
            base_url_configured=bool(settings.selcom_base_url),
            api_key_configured=bool(settings.selcom_api_key),
            api_secret_configured=bool(settings.selcom_api_secret),
            vendor_id_configured=bool(settings.selcom_vendor_id),
            business_mode=settings.selcom_business_mode,
            business_api_key_configured=bool(settings.selcom_business_api_key),
            business_private_key_configured=bool(settings.selcom_business_private_key_base64),
            business_account_number_configured=bool(settings.selcom_business_account_number),
        )
    )
