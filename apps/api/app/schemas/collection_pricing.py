"""Super Admin collection-pricing-rule management
(merchant_collection_pricing_rules) — mirrors app/schemas/withdrawals.py's
PricingRuleCreate/Update/Response shapes, minus destination_code/
processor_fee_flat/processor_fee_pass_through (no destination or
processor-pass-through concept for collections) plus `notes` (a
commercial-agreement reference, which collection pricing asked for and
withdrawal pricing never had).
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.schemas.enums import CollectionMethod


class CollectionPricingRuleCreate(BaseModel):
    channel: CollectionMethod | None = None
    # Not hardcoded to any business-specific range (e.g. 0.4%-2.0%) — the
    # commercial rate is negotiated per merchant/customer and can fall
    # anywhere Super Admin sets it; ge=0/le=100 is a sanity bound only,
    # not a business policy.
    percentage_fee: Decimal = Field(default=Decimal(0), ge=0, le=100)
    flat_fee: Decimal = Field(default=Decimal(0), ge=0)
    minimum_fee: Decimal | None = Field(default=None, ge=0)
    maximum_fee: Decimal | None = Field(default=None, ge=0)
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    is_active: bool = True
    label: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _check_fee_range(self) -> "CollectionPricingRuleCreate":
        if self.minimum_fee is not None and self.maximum_fee is not None and self.maximum_fee < self.minimum_fee:
            raise ValueError("maximum_fee must be greater than or equal to minimum_fee")
        if self.effective_to is not None and self.effective_from is not None and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be after effective_from")
        return self


class CollectionPricingRuleUpdate(BaseModel):
    """Every field optional — only what's set is applied
    (model_dump(exclude_unset=True), same convention as
    PricingRuleUpdate)."""

    channel: CollectionMethod | None = None
    percentage_fee: Decimal | None = Field(default=None, ge=0, le=100)
    flat_fee: Decimal | None = Field(default=None, ge=0)
    minimum_fee: Decimal | None = Field(default=None, ge=0)
    maximum_fee: Decimal | None = Field(default=None, ge=0)
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    is_active: bool | None = None
    label: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _check_fee_range(self) -> "CollectionPricingRuleUpdate":
        if self.minimum_fee is not None and self.maximum_fee is not None and self.maximum_fee < self.minimum_fee:
            raise ValueError("maximum_fee must be greater than or equal to minimum_fee")
        if self.effective_to is not None and self.effective_from is not None and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be after effective_from")
        return self


class CollectionPricingRuleResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID | None = None
    channel: str | None = None
    percentage_fee: Decimal
    flat_fee: Decimal
    minimum_fee: Decimal | None = None
    maximum_fee: Decimal | None = None
    effective_from: datetime
    effective_to: datetime | None = None
    is_active: bool
    label: str | None = None
    notes: str | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
