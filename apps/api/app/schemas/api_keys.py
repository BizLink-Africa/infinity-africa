import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

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

    @field_validator("scopes")
    @classmethod
    def _validate_scopes(cls, scopes: list[str]) -> list[str]:
        unknown = set(scopes) - set(API_KEY_SCOPES)
        if unknown:
            raise ValueError(f"Unknown scope(s): {', '.join(sorted(unknown))}")
        return scopes


class ApiKeyCreateResponse(BaseModel):
    """Returned exactly once, at creation — the plaintext key is never
    retrievable again afterward (only its hash is stored)."""

    id: uuid.UUID
    name: str
    environment: str
    key_prefix: str
    scopes: list[str]
    plaintext_key: str
    created_at: datetime


class ApiKeyResponse(BaseModel):
    id: uuid.UUID
    name: str
    environment: str
    key_prefix: str
    scopes: list[str]
    status: str
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
