import json
from decimal import Decimal
from functools import lru_cache

from pydantic import Field, model_validator
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

    # CORS — origins allowed to call this API (allow_credentials=True in
    # app/main.py, so this can never be "*" — the CORS spec disallows
    # combining a wildcard origin with credentialed requests, and a browser
    # will reject it). Read as a plain string here (not list[str]) so both
    # a JSON array (CORS_ORIGINS=["https://infinityafrica.net"]) and a
    # plain comma-separated value
    # (CORS_ORIGINS=https://infinityafrica.net,https://www.infinityafrica.net)
    # work — pydantic-settings would otherwise hard-require valid JSON for
    # any list-typed field and reject a bare comma-separated value outright
    # (Railway's env var UI makes typing JSON-with-quotes error-prone). Use
    # the `cors_origins` property below, never this field, to read the
    # parsed list.
    cors_origins_raw: str = Field(
        default='["http://localhost:3000"]', validation_alias="CORS_ORIGINS"
    )

    @property
    def cors_origins(self) -> list[str]:
        stripped = self.cors_origins_raw.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            return json.loads(stripped)
        return [origin.strip() for origin in stripped.split(",") if origin.strip()]

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

    # Selcom Business Disbursement API (developer.selcom.business) — the
    # real, documented API withdrawals are approved against, distinct from
    # the checkout/collections API above (different product, different
    # RSA-SHA256 signing scheme — see app/services/selcom_business/).
    # "mock" is local-development-only; the shipped default here is
    # "sandbox", never "mock" — a real withdrawal approval must never
    # silently no-op against a fake client. Backend/Railway env vars only,
    # NEVER set any of these in apps/web/Vercel.
    selcom_business_mode: str = "sandbox"
    selcom_business_sandbox_base_url: str = "https://sandbox.selcom.business"
    selcom_business_production_base_url: str = "https://api.selcom.business/v1"
    selcom_business_api_key: str = ""
    selcom_business_private_key_base64: str = ""
    selcom_business_account_number: str = ""
    selcom_business_timeout_seconds: int = 30
    selcom_business_require_ip_whitelist: bool = False

    # Selcom Checkout/Collections API (https://developers.selcommobile.com/)
    # — the real, documented reference for USSD/STK/wallet push, Selcom
    # Pesa push, and dynamic QR collections, superseding the earlier
    # unconfirmed app/services/selcom/ placeholder. Distinct product/
    # signing scheme from selcom_business above (RSA-only, different
    # header names). Backend/Railway env vars only, NEVER set any of
    # these in apps/web/Vercel. See app/services/selcom_checkout/.
    selcom_checkout_mode: str = "mock"
    selcom_checkout_base_url: str = ""
    selcom_checkout_api_key: str = ""
    selcom_checkout_api_secret: str = ""
    selcom_checkout_digest_method: str = "HS256"
    selcom_checkout_vendor: str = ""
    selcom_checkout_timeout_seconds: int = 30
    # Only needed if Selcom confirms this account requires RS256 instead
    # of HS256 — see app/services/selcom_checkout/signer.py.
    selcom_checkout_private_key_base64: str = ""
    # Our own webhook callback URL (not a secret — it's a public endpoint
    # of ours), e.g. https://<api-domain>/v1/webhooks/selcom/checkout.
    # Sent on every create-order-minimal call so Selcom knows where to
    # deliver payment_status updates — see
    # app/services/checkout_orders.py::create_checkout_order_minimal().
    # Left blank, no webhook field is sent at all (Selcom never calls
    # back; reconciliation still works via the manual refresh endpoints).
    selcom_checkout_webhook_url: str = ""

    # Platform economics — simple placeholders until real pricing rules exist.
    platform_fee_percentage: Decimal = Decimal("1.5")
    disbursement_approval_threshold: Decimal = Decimal(1000000)  # TZS

    # Controlled production pilot guardrail (docs/withdrawal-production-pilot-checklist.md)
    # — a temporary, extra amount cap on top of the platform's normal
    # withdrawal validation, active only while WITHDRAWAL_PILOT_MODE=true.
    # Rejects any merchant withdrawal request above the configured amount
    # with a clear, distinct error rather than a generic validation
    # failure. Turn WITHDRAWAL_PILOT_MODE off (the default) once the pilot
    # is reconciled and approved to expand — never leave this on
    # permanently as a substitute for real per-merchant pricing/limits.
    withdrawal_pilot_mode: bool = False
    withdrawal_pilot_max_amount_tzs: Decimal = Decimal(1000)

    # Collection clearance (docs/ledger-reconciliation.md) — reserved
    # config for a future delayed-settlement gate. Not yet wired to a
    # background worker (none exists in this codebase); the active
    # safety nets today are reverse_successful_collection() (real
    # reversal after credit) and the SELF_PAYMENT_OWN_TILL fraud rule
    # (pending_review hold before credit). Left False/unused rather than
    # half-wired, so it does nothing until a real recheck mechanism backs
    # it — see the docs file for why.
    collection_auto_settle_enabled: bool = False
    collection_clearance_delay_minutes: int = 10

    @model_validator(mode="after")
    def _reject_wildcard_cors_outside_development(self) -> "Settings":
        """allow_credentials=True in app/main.py's CORSMiddleware makes a
        "*" origin both a browser-rejected combination and a real security
        hole (any site could call this API with a signed-in merchant's
        cookies/credentials) — refuse it outright anywhere that isn't local
        development, the same guardrail pattern as
        SelcomBusinessMisconfiguredError below for SELCOM_BUSINESS_MODE."""
        if self.environment != "development" and "*" in self.cors_origins:
            raise ValueError(
                'CORS_ORIGINS must not contain "*" when ENVIRONMENT is not "development" '
                "(allow_credentials=True makes a wildcard origin unsafe and browsers reject it "
                "anyway) — list explicit deployed frontend origins instead."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
