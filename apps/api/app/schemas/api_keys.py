import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

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


class ApiKeyCreate(BaseModel):
    name: str
    environment: str = Field(default="sandbox", pattern="^(sandbox|live)$")
    scopes: list[str] = Field(default_factory=list)
    # The merchant's Part 6 choice, made once at creation. Only one of these
    # is meaningful at a time — ip_whitelist_enabled wins if both are sent,
    # see the validator below.
    ip_whitelist_enabled: bool = False
    continue_without_ip_whitelist: bool = True

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
        return self


class ApiKeyRename(BaseModel):
    name: str = Field(min_length=1, max_length=100)


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
