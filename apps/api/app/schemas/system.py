from pydantic import BaseModel


class SelcomConfigStatusResponse(BaseModel):
    """Safe booleans only — never the actual configured values. See
    GET /v1/system/selcom-config-status."""

    collection_enabled: bool
    withdrawal_enabled: bool
    mock_mode: bool
    base_url_configured: bool
    api_key_configured: bool
    api_secret_configured: bool
    vendor_id_configured: bool
    # Selcom Business Disbursement API — a separate product/client from the
    # checkout fields above (see app/services/selcom_business/); its own
    # mode, own credentials, never mixed with the collections config.
    business_mode: str
    business_api_key_configured: bool
    business_private_key_configured: bool
    business_account_number_configured: bool
