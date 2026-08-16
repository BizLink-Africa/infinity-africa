from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    # Supabase
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # JWT verification — a Supabase project uses EITHER a legacy shared HS256
    # secret (supabase_jwt_secret) OR JWKS-based asymmetric signing keys
    # (supabase_jwks_url/supabase_jwt_issuer), never both as the *current*
    # key. See app/auth/jwt.py: JWKS is tried first when configured, HS256
    # is the fallback (and what the test suite's fake tokens always use).
    supabase_jwt_secret: str = ""
    supabase_jwks_url: str = ""
    supabase_jwt_issuer: str = ""

    # Database (Supabase Postgres connection string)
    database_url: str = ""

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Base URL of apps/web, used to build the public payment link URL
    # (public_slug -> {public_app_url}/pay/{public_slug}).
    public_app_url: str = "http://localhost:3000"

    # Mock Selcom client (see app.services.selcom.mock_client) — the default
    # client (SELCOM_MODE=mock below) every collection/disbursement runs
    # through until Selcom whitelisting is done (see
    # docs/selcom-live-go-live.md).
    mock_provider_failure_rate: float = 0.1
    mock_provider_latency_seconds: float = 0.3
    dynamic_qr_expiry_seconds: int = 300

    # Shared secret for verifying the (mock) HMAC signature on incoming
    # POST /v1/webhooks/selcom deliveries — see app/services/selcom/webhooks.py.
    selcom_webhook_secret: str = ""

    # Selcom production integration (Railway) — see docs/selcom-live-go-live.md
    # for the full deploy/whitelist/go-live procedure. All blank/default
    # until Selcom confirms IP whitelisting and issues live credentials.
    # Backend/Railway env vars only — NEVER set any of these in
    # apps/web/Vercel.
    selcom_base_url: str = ""
    selcom_api_key: str = ""
    selcom_api_secret: str = ""
    selcom_vendor_id: str = ""
    selcom_collection_enabled: bool = False
    selcom_withdrawal_enabled: bool = False
    # Informational only — the real route is registered at this fixed path
    # in app/main.py regardless of this value; it exists so the path Selcom
    # needs for callback configuration is documented alongside the rest of
    # the Selcom config rather than only in code.
    selcom_webhook_path: str = "/v1/webhooks/selcom"
    # "mock" (default) -> app.services.selcom.mock_client.MockSelcomClient,
    # simulated responses only, no network call ever reaches Selcom. "live"
    # -> app.services.selcom.live_client.LiveSelcomClient, real HTTP calls
    # to SELCOM_BASE_URL. See app/services/selcom/client.py::get_selcom_client()
    # and docs/selcom-live-go-live.md before ever setting this to "live" in
    # a deployed environment.
    selcom_mode: str = "mock"

    # Platform economics — simple placeholders until real pricing rules exist.
    platform_fee_percentage: Decimal = Decimal("1.5")
    disbursement_approval_threshold: Decimal = Decimal(1000000)  # TZS


@lru_cache
def get_settings() -> Settings:
    return Settings()
