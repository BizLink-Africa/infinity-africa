import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.core.phone import validate_and_normalize_phone

# Same pattern app/schemas/auth.py's _EMAIL_PATTERN / app/schemas/merchant_portal.py's
# _EMAIL_PATTERN use — deliberately not pydantic's EmailStr, which needs
# the email-validator package this codebase doesn't otherwise depend on.
_EMAIL_PATTERN = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"


class PayByLinkCreate(BaseModel):
    """POST /v1/merchant/pay-by-link — creates the caller's merchant's one
    permanent Pay by Link page. display_name/slug are both optional: the
    router defaults display_name to the merchant's own business_name and
    generates a slug from it (app/services/pay_by_link.py::generate_default_slug)
    when omitted, matching the feature brief's "Default slug: generate
    from merchant/business/contact name" requirement."""

    display_name: str | None = Field(default=None, max_length=200)
    slug: str | None = None
    description: str | None = Field(default=None, max_length=500)

    @field_validator("display_name")
    @classmethod
    def _strip_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("slug")
    @classmethod
    def _normalize_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower()


class PayByLinkUpdate(BaseModel):
    """PATCH /v1/merchant/pay-by-link — every field optional; only the
    ones provided are changed. Changing `slug` is deliberately allowed
    here (the router doesn't block it), but breaks any copy of the old
    URL already shared — the frontend is expected to show a clear
    warning before submitting a slug change (feature brief Part 4)."""

    display_name: str | None = Field(default=None, max_length=200)
    slug: str | None = None
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None

    @field_validator("display_name")
    @classmethod
    def _strip_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("display_name cannot be blank")
        return stripped

    @field_validator("slug")
    @classmethod
    def _normalize_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower()


class PayByLinkResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    slug: str
    public_url: str
    display_name: str
    description: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_used_at: datetime | None = None


class PublicPayByLinkResponse(BaseModel):
    """What a customer sees before filling in the checkout form — no
    merchant-internal fields (no id, merchant_id, created_at, ...),
    mirroring PublicPaymentLinkResponse's own "only safe public
    information" rule. `is_active` IS included: the frontend needs it to
    decide whether to render the form or an "unavailable" state."""

    display_name: str
    description: str | None = None
    is_active: bool


class PayByLinkCheckoutRequest(BaseModel):
    """POST /public/pay-by-link/{slug}/checkout — the customer's own
    details and chosen amount, submitted from the permanent Pay by Link
    page. merchant_id is never part of this request: the router resolves
    it exclusively from the slug (see app/routers/pay_by_link.py), never
    from client input."""

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str = Field(pattern=_EMAIL_PATTERN, max_length=254)
    phone: str
    amount: Decimal = Field(gt=0)
    currency: str = "TZS"
    description: str | None = Field(default=None, max_length=500)

    @field_validator("first_name", "last_name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("cannot be blank")
        return stripped

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, value: str) -> str:
        return validate_and_normalize_phone(value)

    @field_validator("currency")
    @classmethod
    def _check_currency(cls, value: str) -> str:
        # Multi-currency doesn't exist anywhere else in this codebase yet
        # (every other amount field defaults to, and every provider
        # integration only ever handles, TZS) — reject anything else now
        # rather than silently accept a value nothing downstream can act
        # on correctly.
        if value != "TZS":
            raise ValueError("Only TZS is supported at this time")
        return value


class PayByLinkCheckoutResponse(BaseModel):
    """What the customer's browser gets back — it does a full-page
    redirect to redirect_url next, landing on the existing Infinity
    Africa "Choose how you want to pay" checkout page for the fresh
    payment_links row this request just created."""

    payment_link_id: uuid.UUID
    redirect_url: str
