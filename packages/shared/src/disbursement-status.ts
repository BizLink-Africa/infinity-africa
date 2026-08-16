/** Lifecycle status of a payout. */
export enum DisbursementStatus {
  PENDING = "PENDING",
  PROCESSING = "PROCESSING",
  SUCCESS = "SUCCESS",
  FAILED = "FAILED",
  REVERSED = "REVERSED",
}

export const DISBURSEMENT_STATUS_LABELS: Record<DisbursementStatus, string> = {
  [DisbursementStatus.PENDING]: "Pending",
  [DisbursementStatus.PROCESSING]: "Processing",
  [DisbursementStatus.SUCCESS]: "Success",
  [DisbursementStatus.FAILED]: "Failed",
  [DisbursementStatus.REVERSED]: "Reversed",
};
