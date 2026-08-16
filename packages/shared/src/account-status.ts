/** Onboarding review lifecycle for a merchant account — independent of the
 * backend's merchants.status/kyc_status columns (see
 * onboarding_submissions.review_status in supabase/migrations). */
export enum AccountStatus {
  PENDING_VERIFICATION = "PENDING_VERIFICATION",
  VERIFIED = "VERIFIED",
  REJECTED = "REJECTED",
  INFO_REQUESTED = "INFO_REQUESTED",
}

export const ACCOUNT_STATUS_LABELS: Record<AccountStatus, string> = {
  [AccountStatus.PENDING_VERIFICATION]: "Pending Verification",
  [AccountStatus.VERIFIED]: "Verified",
  [AccountStatus.REJECTED]: "Rejected",
  [AccountStatus.INFO_REQUESTED]: "More Info Requested",
};
