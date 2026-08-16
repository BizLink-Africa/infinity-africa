"""Self-service merchant onboarding — /v1/onboarding/*.

No merchant_id anywhere in these routes: /merchant-account creates one from
the caller's own verified JWT identity (app.auth.get_current_user);
/documents and /status resolve it the same way the merchant-portal routes
do (app.auth.get_own_merchant / get_current_user + a null-safe lookup).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.auth import get_current_user, get_own_merchant
from app.database.session import get_supabase_admin
from app.schemas.auth import AuthenticatedUser, MerchantMembership
from app.schemas.common import APIResponse
from app.schemas.enums import AccountStatus, DocumentType
from app.schemas.merchants import MerchantResponse
from app.schemas.onboarding import (
    OnboardingDocumentResponse,
    OnboardingMerchantAccountCreate,
    OnboardingMerchantAccountResponse,
    OnboardingStatusResponse,
)
from app.services.onboarding import (
    create_merchant_onboarding,
    get_onboarding_status,
    register_onboarding_document,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post(
    "/merchant-account",
    response_model=APIResponse[OnboardingMerchantAccountResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_merchant_account(
    payload: OnboardingMerchantAccountCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
):
    client = get_supabase_admin()
    merchant = create_merchant_onboarding(client, user=user, payload=payload)
    return APIResponse(
        data=OnboardingMerchantAccountResponse(
            merchant=MerchantResponse(**merchant), account_status=AccountStatus.PENDING_VERIFICATION
        )
    )


@router.post("/documents", response_model=APIResponse[OnboardingDocumentResponse])
async def upload_document(
    membership: Annotated[MerchantMembership, Depends(get_own_merchant)],
    document_type: Annotated[DocumentType, Form()],
    file: Annotated[UploadFile, File()],
):
    client = get_supabase_admin()
    document = await register_onboarding_document(
        client,
        merchant_id=membership.merchant_id,
        document_type=document_type,
        file=file,
        uploaded_by=membership.user_id,
    )
    return APIResponse(data=OnboardingDocumentResponse(**document))


@router.get("/status", response_model=APIResponse[OnboardingStatusResponse])
def read_onboarding_status(user: Annotated[AuthenticatedUser, Depends(get_current_user)]):
    client = get_supabase_admin()
    result = get_onboarding_status(client, user=user)
    return APIResponse(data=OnboardingStatusResponse(**result))
