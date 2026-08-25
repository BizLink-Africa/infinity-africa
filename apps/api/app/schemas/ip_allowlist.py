"""Merchant-provided server IP allowlist — /v1/merchant/ip-allowlist and
/v1/admin/ip-allowlist. See app/services/ip_allowlist.py for enforcement
(live environment only, opt-in once a merchant has any active row) and
supabase/migrations/20260825020000_api_ip_allowlist.sql for the table.
"""

import ipaddress
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


def _validate_ip_or_cidr(value: str) -> str:
    candidate = value.strip()
    try:
        if "/" in candidate:
            ipaddress.ip_network(candidate, strict=False)
        else:
            ipaddress.ip_address(candidate)
    except ValueError as exc:
        raise ValueError(f"{value!r} is not a valid IP address or CIDR block") from exc
    return candidate


class IpAllowlistCreate(BaseModel):
    environment: str = Field(pattern="^(sandbox|live)$")
    label: str = Field(min_length=1, max_length=100)
    ip_address_or_cidr: str
    api_key_id: uuid.UUID | None = None
    notes: str | None = None

    @field_validator("ip_address_or_cidr")
    @classmethod
    def _check_ip(cls, value: str) -> str:
        return _validate_ip_or_cidr(value)


class IpAllowlistResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    api_key_id: uuid.UUID | None = None
    environment: str
    label: str
    ip_address_or_cidr: str
    status: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminIpAllowlistResponse(IpAllowlistResponse):
    merchant_name: str
    created_by: uuid.UUID | None = None
    approved_by: uuid.UUID | None = None
