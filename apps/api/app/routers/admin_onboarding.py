"""Super-admin onboarding review — /v1/admin/onboarding/*.

Not in the original self-service endpoint list, but required for the
Super Admin "Onboarding Requests" page (View/Approve/Reject/Request More
Info) to act on real data instead of the retired mock store.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from supabase import Client

from app.auth import require_super_admin
from app.core.errors import NotFoundError
from app.database.session import get_supabase_admin
from app.schemas.auth import AuthenticatedUser
from app.schemas.common import APIResponse
from app.schemas.onboarding import OnboardingReviewAction, OnboardingSubmissionResponse
from app.services.crud import execute_maybe_single, get_by_id
from app.services.onboarding import (
    approve_onboarding_submission,
    get_onboarding_submission,
    list_onboarding_submissions,
    reject_onboarding_submission,
    request_more_info_onboarding_submission,
)

router = APIRouter(prefix="/admin/onboarding", tags=["admin-onboarding"])


def _resolve_submission_id(client: Client, id: uuid.UUID) -> uuid.UUID:
    """The Merchants dashboard only knows a merchant_id, not a submission_id
    — but onboarding_submissions.merchant_id is UNIQUE (1:1), so `id` is
    accepted as either. Tries it as a submission id first (the primary key),
    falling back to treating it as a merchant_id."""
    if get_by_id(client, "onboarding_submissions", id):
        return id

    row = execute_maybe_single(
        client.table("onboarding_submissions").select("id").eq("merchant_id", str(id)).maybe_single()
    )
    if not row:
        raise NotFoundError("Onboarding submission not found")
    return uuid.UUID(row["id"])


@router.get("", response_model=APIResponse[list[OnboardingSubmissionResponse]])
def list_submissions(_admin: Annotated[AuthenticatedUser, Depends(require_super_admin)]):
    client = get_supabase_admin()
    rows = list_onboarding_submissions(client)
    return APIResponse(data=[OnboardingSubmissionResponse(**row) for row in rows])


@router.get("/{submission_id}", response_model=APIResponse[OnboardingSubmissionResponse])
def get_submission(
    submission_id: uuid.UUID, _admin: Annotated[AuthenticatedUser, Depends(require_super_admin)]
):
    client = get_supabase_admin()
    row = get_onboarding_submission(client, submission_id)
    return APIResponse(data=OnboardingSubmissionResponse(**row))


@router.post("/{submission_id}/approve", response_model=APIResponse[OnboardingSubmissionResponse])
def approve(submission_id: uuid.UUID, admin: Annotated[AuthenticatedUser, Depends(require_super_admin)]):
    client = get_supabase_admin()
    row = approve_onboarding_submission(client, submission_id=submission_id, reviewer_id=admin.id)
    return APIResponse(data=OnboardingSubmissionResponse(**row))


@router.post("/{submission_id}/reject", response_model=APIResponse[OnboardingSubmissionResponse])
def reject(
    submission_id: uuid.UUID,
    payload: OnboardingReviewAction,
    admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
):
    client = get_supabase_admin()
    row = reject_onboarding_submission(
        client, submission_id=submission_id, reviewer_id=admin.id, note=payload.review_note
    )
    return APIResponse(data=OnboardingSubmissionResponse(**row))


@router.post("/{submission_id}/request-more-info", response_model=APIResponse[OnboardingSubmissionResponse])
def request_more_info(
    submission_id: uuid.UUID,
    payload: OnboardingReviewAction,
    admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
):
    client = get_supabase_admin()
    row = request_more_info_onboarding_submission(
        client, submission_id=submission_id, reviewer_id=admin.id, note=payload.review_note
    )
    return APIResponse(data=OnboardingSubmissionResponse(**row))


# --- PATCH variants, id = submission_id OR merchant_id -----------------------
# Additional routes (same paths as the POST ones above, different method) for
# callers that only know a merchant_id — the Merchants dashboard, notably.


@router.patch("/{id}/approve", response_model=APIResponse[OnboardingSubmissionResponse])
def approve_by_id(id: uuid.UUID, admin: Annotated[AuthenticatedUser, Depends(require_super_admin)]):
    client = get_supabase_admin()
    submission_id = _resolve_submission_id(client, id)
    row = approve_onboarding_submission(client, submission_id=submission_id, reviewer_id=admin.id)
    return APIResponse(data=OnboardingSubmissionResponse(**row))


@router.patch("/{id}/reject", response_model=APIResponse[OnboardingSubmissionResponse])
def reject_by_id(
    id: uuid.UUID,
    payload: OnboardingReviewAction,
    admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
):
    client = get_supabase_admin()
    submission_id = _resolve_submission_id(client, id)
    row = reject_onboarding_submission(
        client, submission_id=submission_id, reviewer_id=admin.id, note=payload.review_note
    )
    return APIResponse(data=OnboardingSubmissionResponse(**row))


@router.patch("/{id}/request-more-info", response_model=APIResponse[OnboardingSubmissionResponse])
def request_more_info_by_id(
    id: uuid.UUID,
    payload: OnboardingReviewAction,
    admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
):
    client = get_supabase_admin()
    submission_id = _resolve_submission_id(client, id)
    row = request_more_info_onboarding_submission(
        client, submission_id=submission_id, reviewer_id=admin.id, note=payload.review_note
    )
    return APIResponse(data=OnboardingSubmissionResponse(**row))
