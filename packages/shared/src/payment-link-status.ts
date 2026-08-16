/** Lifecycle status of a reusable or one-off payment link. */
export enum PaymentLinkStatus {
  ACTIVE = "ACTIVE",
  PAID = "PAID",
  EXPIRED = "EXPIRED",
  CANCELLED = "CANCELLED",
}

export const PAYMENT_LINK_STATUS_LABELS: Record<PaymentLinkStatus, string> = {
  [PaymentLinkStatus.ACTIVE]: "Active",
  [PaymentLinkStatus.PAID]: "Paid",
  [PaymentLinkStatus.EXPIRED]: "Expired",
  [PaymentLinkStatus.CANCELLED]: "Cancelled",
};
