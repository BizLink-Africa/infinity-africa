"""Self-service merchant onboarding — /v1/onboarding/*.

No merchant_id anywhere in these routes: /merchant-account creates one from
the caller's own verified JWT identity (app.auth.get_current_user);
/documents and /status resolve it the same way the merchant-portal routes
do (app.auth.get_own_merchant / get_current_user + a null-safe lookup).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.auth import get_current_user, get_own_merchant
from app.core.rate_limit import rate_limit
from app.database.session import get_supabase_admin
from app.schemas.auth import AuthenticatedUser, MerchantMembership
from app.schemas.common import APIResponse
from app.schemas.enums import AccountStatus, DocumentType
from app.schemas.merchants import MerchantResponse
from app.schemas.onboarding import (
    OnboardingDocumentResponse,
    OnboardingMerchantAccountCreate,
    OnboardingMerchantAccountResponse,
    OnboardingSignupCreate,
    OnboardingSignupResponse,
    OnboardingStatusResponse,
)
from app.services.onboarding import (
    create_merchant_onboarding,
    get_onboarding_status,
    register_onboarding_document,
    signup_merchant,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post(
    "/signup",
    response_model=APIResponse[OnboardingSignupResponse],
    status_code=status.HTTP_201_CREATED,
)
def merchant_signup(
    payload: OnboardingSignupCreate,
    _rate_limit: Annotated[
        None, Depends(rate_limit(scope="merchant_signup", limit=5, window_seconds=300))
    ],
):
    """Combined signup: account credentials + business details in one call.
    Unauthenticated — the backend creates the Supabase Auth user itself
    (service_role) so the frontend never touches Supabase Auth for this
    flow. The merchant is created PENDING_VERIFICATION; it is NOT
    auto-approved and no welcome/approval email is sent here (that only
    happens on Super Admin approval). NIDA is mandatory — a missing value
    returns `nida_required`, a malformed one `nida_invalid`."""
    client = get_supabase_admin()
    result = signup_merchant(client, payload=payload)
    merchant = result["merchant"]
    return APIResponse(
        data=OnboardingSignupResponse(
            merchant_id=merchant["id"],
            merchant_code=merchant.get("merchant_code"),
            account_status=AccountStatus.PENDING_VERIFICATION,
            email_confirmation_required=result["email_confirmation_required"],
        )
    )


@router.post(
    "/merchant-account",
    response_model=APIResponse[OnboardingMerchantAccountResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_merchant_account(
    payload: OnboardingMerchantAccountCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _rate_limit: Annotated[None, Depends(rate_limit(scope="merchant_onboarding_submit", limit=5, window_seconds=60))],
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
