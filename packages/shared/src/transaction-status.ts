/** Lifecycle status of any ledger movement (collection, disbursement, fee, refund). */
export enum TransactionStatus {
  PENDING = "pending",
  PROCESSING = "processing",
  SUCCESSFUL = "successful",
  FAILED = "failed",
  REVERSED = "reversed",
  CANCELLED = "cancelled",
}

export const TRANSACTION_STATUS_LABELS: Record<TransactionStatus, string> = {
  [TransactionStatus.PENDING]: "Pending",
  [TransactionStatus.PROCESSING]: "Processing",
  [TransactionStatus.SUCCESSFUL]: "Successful",
  [TransactionStatus.FAILED]: "Failed",
  [TransactionStatus.REVERSED]: "Reversed",
  [TransactionStatus.CANCELLED]: "Cancelled",
};
