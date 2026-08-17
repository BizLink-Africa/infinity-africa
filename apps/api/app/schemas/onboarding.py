import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.phone import validate_and_normalize_phone
from app.schemas.enums import (
    AccountStatus,
    DocumentType,
    DocumentUploadStatus,
    ServiceNeeded,
)
from app.schemas.merchants import MerchantResponse


class OnboardingMerchantAccountCreate(BaseModel):
    """No merchant_id, no contact_email — the caller's identity comes from
    their verified JWT (app.auth.get_current_user), never the request body."""

    business_name: str
    nature_of_business: str
    business_category: str
    physical_address: str
    region_city: str
    website_url: str | None = None
    contact_phone: str
    services_needed: list[ServiceNeeded] = Field(min_length=1)
    accepted_terms: bool
    accepted_privacy: bool

    @field_validator("contact_phone")
    @classmethod
    def _check_phone(cls, value: str) -> str:
        return validate_and_normalize_phone(value)


class OnboardingMerchantAccountResponse(BaseModel):
    merchant: MerchantResponse
    account_status: AccountStatus
    next_path: str = "/merchant/overview"


class OnboardingStatusResponse(BaseModel):
    has_account: bool
    onboarding_completed: bool
    merchant_id: uuid.UUID | None = None
    account_status: AccountStatus | None = None
    next_path: str


class OnboardingDocumentResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    document_type: DocumentType
    original_filename: str
    mime_type: str
    size_bytes: int
    upload_status: DocumentUploadStatus
    uploaded_at: datetime
    signed_url: str | None = None


class OnboardingSubmissionResponse(BaseModel):
    """Super-admin list/detail view — joins the merchant's own profile
    fields onto its onboarding_submissions row."""

    id: uuid.UUID
    merchant_id: uuid.UUID
    business_name: str
    owner_email: str
    contact_phone: str | None = None
    nature_of_business: str
    business_category: str
    physical_address: str
    region_city: str
    website_url: str | None = None
    services_needed: list[ServiceNeeded]
    review_status: AccountStatus
    review_note: str | None = None
    document_status: DocumentUploadStatus
    submitted_at: datetime
    updated_at: datetime
    documents: list[OnboardingDocumentResponse] = Field(default_factory=list)


class OnboardingReviewAction(BaseModel):
    review_note: str | None = None
