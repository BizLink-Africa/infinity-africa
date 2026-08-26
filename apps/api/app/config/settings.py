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

    # Encryption-at-rest key for merchants.webhook_secret_encrypted (see
    # app/core/secret_box.py) — a merchant's OUTBOUND webhook signing secret,
    # the one secret in this codebase that must be recoverable in full after
    # creation (HMAC signing needs the raw value, not a hash). Backend/Railway
    # only, NEVER set in apps/web/Vercel, NEVER logged. Blank falls back to a
    # key derived from supabase_service_role_key — fine for local dev/test,
    # not for production (set a real Fernet key there).
    webhook_secret_encryption_key: str = ""

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

    # Hosted checkout (payment_gateway_url from create-order-minimal) —
    # confirmed broken on Selcom's own side as of 2026-08-23 (returns
    # "Page Not Found" for every order tested — see
    # docs/selcom-checkout-collections.md, "Known issue" section).
    # Active customer payment methods are wallet-push/Selcom Pesa/TanQR
    # instead (app/services/collection_payment.py). This flag is the
    # explicit, backend-level guard keeping hosted checkout inactive —
    # POST /public/payment-links/{slug}/pay/checkout refuses to run
    # while this is False (the default), even though no current frontend
    # calls it either. Flip only once Selcom confirms hosted checkout is
    # fixed; the endpoint/service code itself is untouched and ready.
    hosted_checkout_enabled: bool = False

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

    # Transactional email (Resend) — see app/services/email.py and
    # docs/email-delivery.md. Backend/Railway only, NEVER set
    # RESEND_API_KEY in apps/web/Vercel. Blank RESEND_API_KEY means email
    # sending is not configured — send_email() raises EmailDeliveryError
    # rather than silently no-op'ing, since a caller (e.g. "send invoice")
    # needs to know delivery didn't happen.
    resend_api_key: str = ""
    # Default sender for every transactional email EXCEPT invoice payment
    # requests (staff invites, password resets, payment receipts, welcome
    # emails, inquiry notifications) — see invoice_email_from below for why
    # invoices use a visually distinct address.
    email_from: str = "Infinity Africa <notification@infinityafrica.net>"
    # Sender for invoice payment-request emails specifically — a customer
    # should be able to tell "someone wants to be paid" apart from
    # ordinary account/notification mail at a glance. Falls back to
    # email_from when blank (see the invoice_email_from property) so a
    # deployment that forgets to set this still sends *something* sane
    # rather than failing outright.
    invoice_email_from_raw: str = Field(default="", validation_alias="INVOICE_EMAIL_FROM")
    # Reply-to for every transactional email — currently only consumed by
    # send_invoice_email, so this is effectively "who a customer's reply
    # about a bill reaches" today (finance, not general support).
    email_reply_to: str = "finance@infinityafrica.net"
    # Where a "contact us" / report-transaction inquiry notification goes
    # — not yet wired to a sender (no such flow exists in this codebase
    # yet), reserved here so the env var exists ahead of that feature.
    ceo_email: str = ""
    # General site base URL for links inside emails (distinct from
    # public_app_url, which specifically builds the /pay/{slug} payment
    # link — see app/services/payment_links.py::build_public_url). Falls
    # back to public_app_url when blank.
    app_url_raw: str = Field(default="", validation_alias="APP_URL")

    @property
    def invoice_email_from(self) -> str:
        return self.invoice_email_from_raw or self.email_from

    @property
    def app_url(self) -> str:
        return self.app_url_raw or self.public_app_url

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
