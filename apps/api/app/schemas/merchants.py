import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class MerchantCreate(BaseModel):
    business_name: str
    legal_name: str | None = None
    country: str = "TZ"
    currency: str = "TZS"
    contact_email: str
    contact_phone: str | None = None


class MerchantProfileUpdate(BaseModel):
    """Fields a MERCHANT_ADMIN may change about their own merchant."""

    business_name: str | None = None
    legal_name: str | None = None
    contact_phone: str | None = None
    webhook_url: str | None = None


class MerchantStatusUpdate(BaseModel):
    """Fields only a super admin may change (onboarding/compliance decisions)."""

    status: str | None = Field(None, pattern="^(pending|active|suspended|closed)$")
    kyc_status: str | None = Field(None, pattern="^(unverified|pending|verified|rejected)$")


class MerchantResponse(BaseModel):
    id: uuid.UUID
    business_name: str
    legal_name: str | None = None
    country: str
    currency: str
    contact_email: str
    contact_phone: str | None = None
    status: str
    kyc_status: str
    api_production_enabled: bool = False
    webhook_url: str | None = None
    created_at: datetime
    updated_at: datetime
