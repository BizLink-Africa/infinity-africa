/** Lifecycle status of a withdrawal (payout). Every withdrawal starts at
 * PENDING_ADMIN_APPROVAL — there is no amount-based auto-processing.
 * REJECTED (a Super Admin's deliberate decision, nothing was ever
 * reserved) is distinct from FAILED (a reserved payout the provider
 * declined, reversed). REVERSED is for reversing an already-SUCCESS
 * payout after the fact. */
export enum DisbursementStatus {
  PENDING_ADMIN_APPROVAL = "PENDING_ADMIN_APPROVAL",
  INFO_REQUESTED = "INFO_REQUESTED",
  PROCESSING = "PROCESSING",
  SUCCESS = "SUCCESS",
  FAILED = "FAILED",
  REJECTED = "REJECTED",
  NEEDS_ADMIN_ATTENTION = "NEEDS_ADMIN_ATTENTION",
  NEEDS_RECONCILIATION = "NEEDS_RECONCILIATION",
  BLOCKED_IP_WHITELIST = "BLOCKED_IP_WHITELIST",
  REVERSED = "REVERSED",
}

export const DISBURSEMENT_STATUS_LABELS: Record<DisbursementStatus, string> = {
  [DisbursementStatus.PENDING_ADMIN_APPROVAL]: "Pending Approval",
  [DisbursementStatus.INFO_REQUESTED]: "Information Requested",
  [DisbursementStatus.PROCESSING]: "Processing",
  [DisbursementStatus.SUCCESS]: "Completed",
  [DisbursementStatus.FAILED]: "Failed",
  [DisbursementStatus.REJECTED]: "Rejected",
  [DisbursementStatus.NEEDS_ADMIN_ATTENTION]: "Needs Admin Attention",
  [DisbursementStatus.NEEDS_RECONCILIATION]: "Needs Reconciliation",
  [DisbursementStatus.BLOCKED_IP_WHITELIST]: "Blocked (IP Whitelist)",
  [DisbursementStatus.REVERSED]: "Reversed",
};
