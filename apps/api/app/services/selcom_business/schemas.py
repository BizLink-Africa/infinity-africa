"""Result types the Selcom Business client (client.py) returns — the
vocabulary app/services/disbursements.py is written against, mirroring the
shape app/services/selcom/schemas.py's DisbursementResult already had so
the withdrawal approval state machine (successful/processing/ambiguous/
failed/blocked branches) didn't need to change when the provider
underneath it did.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

SelcomBusinessStatus = Literal["successful", "failed", "processing", "ambiguous"]


class SelcomBusinessResult(BaseModel):
    provider: str = "selcom_business"
    transaction_id: str
    status: SelcomBusinessStatus
    receipt: str | None = None
    failure_reason: str | None = None
    raw_status: str | None = None
    # The full, unparsed response body — stored alongside the parsed fields
    # above onto disbursements.selcom_raw_response for support/reconciliation
    # debugging. Empty for the mock client (there's no real response to keep).
    raw_response: dict[str, Any] = Field(default_factory=dict)
