import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.ip_allowlist import _validate_ip_or_cidr

# Permission scopes a merchant can grant to an API key. Dashboard JWT
# sessions are never scope-checked — only API-key callers are (see
# app.auth.dependencies.require_api_key_scope).
API_KEY_SCOPES: tuple[str, ...] = (
    "collections:write",
    "collections:read",
    "payment_links:write",
    "payment_links:read",
    "invoices:write",
    "invoices:read",
    "transactions:read",
    "webhooks:manage",
)


class InlineIpAllowlistEntry(BaseModel):
    """One row of the "Enable IP whitelisting" form's inline IP list —
    submitted alongside ApiKeyCreate, not a separate POST /ip-allowlist
    call. label is optional (falls back to the IP itself for display)."""

    ip_address_or_cidr: str
    label: str | None = None

    @field_validator("ip_address_or_cidr")
    @classmethod
    def _check_ip(cls, value: str) -> str:
        return _validate_ip_or_cidr(value)


class ApiKeyCreate(BaseModel):
    name: str
    environment: str = Field(default="sandbox", pattern="^(sandbox|live)$")
    scopes: list[str] = Field(default_factory=list)
    # The merchant's Part 6 choice, made once at creation. Only one of these
    # is meaningful at a time — ip_whitelist_enabled wins if both are sent,
    # see the validator below.
    ip_whitelist_enabled: bool = False
    continue_without_ip_whitelist: bool = True
    # Required (min 1) when ip_whitelist_enabled=true — the inline "Allowed
    # server IPs" list on the same form, so a merchant enabling whitelisting
    # doesn't have to leave and come back from the separate IP Allowlist
    # page before the key is even usable.
    allowed_ips: list[InlineIpAllowlistEntry] = Field(default_factory=list)

    @field_validator("scopes")
    @classmethod
    def _validate_scopes(cls, scopes: list[str]) -> list[str]:
        unknown = set(scopes) - set(API_KEY_SCOPES)
        if unknown:
            raise ValueError(f"Unknown scope(s): {', '.join(sorted(unknown))}")
        return scopes

    @model_validator(mode="after")
    def _reconcile_ip_whitelist_choice(self) -> "ApiKeyCreate":
        if self.ip_whitelist_enabled:
            self.continue_without_ip_whitelist = False
        else:
            self.continue_without_ip_whitelist = True
            self.allowed_ips = []
        return self

    @model_validator(mode="after")
    def _require_at_least_one_ip_when_enabled(self) -> "ApiKeyCreate":
        if self.ip_whitelist_enabled and not self.allowed_ips:
            raise ValueError(
                "Add at least one allowed server IP or choose Continue without IP whitelisting."
            )
        return self

    @model_validator(mode="after")
    def _reject_duplicate_ips(self) -> "ApiKeyCreate":
        seen: set[str] = set()
        for entry in self.allowed_ips:
            normalized = entry.ip_address_or_cidr.strip().lower()
            if normalized in seen:
                raise ValueError(f"Duplicate IP/CIDR in the list: {entry.ip_address_or_cidr}")
            seen.add(normalized)
        return self


class ApiKeyRename(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ApiKeyIpWhitelistUpdate(BaseModel):
    """Switch an existing key's IP-whitelisting choice after creation
    (Merchant Portal API key detail panel). Switching TO enabled requires
    the key to already have at least one non-rejected linked allowlist
    entry — add IPs first via POST /v1/merchant/ip-allowlist with this
    key's id, then flip this."""

    ip_whitelist_enabled: bool


class ApiKeyCreateResponse(BaseModel):
    """Returned exactly once, at creation — the plaintext key is never
    retrievable again afterward (only its hash is stored)."""

    id: uuid.UUID
    name: str
    environment: str
    key_prefix: str
    key_last4: str | None = None
    scopes: list[str]
    ip_whitelist_enabled: bool = False
    continue_without_ip_whitelist: bool = True
    plaintext_key: str
    created_at: datetime


class ApiKeyResponse(BaseModel):
    id: uuid.UUID
    name: str
    environment: str
    key_prefix: str
    key_last4: str | None = None
    scopes: list[str]
    status: str
    ip_whitelist_enabled: bool = False
    continue_without_ip_whitelist: bool = True
    last_used_at: datetime | None = None
    last_used_ip: str | None = None
    revoked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
