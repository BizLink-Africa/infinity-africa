"""Result types the Selcom Business client (client.py) returns — the
vocabulary app/services/disbursements.py is written against, mirroring the
shape app/services/selcom/schemas.py's DisbursementResult already had so
the withdrawal approval state machine (successful/processing/ambiguous/
failed/blocked branches) didn't need to change when the provider
underneath it did.
"""

from typing import Literal

from pydantic import BaseModel

SelcomBusinessStatus = Literal["successful", "failed", "processing", "ambiguous"]


class SelcomBusinessResult(BaseModel):
    provider: str = "selcom_business"
    transaction_id: str
    status: SelcomBusinessStatus
    receipt: str | None = None
    failure_reason: str | None = None
    raw_status: str | None = None
