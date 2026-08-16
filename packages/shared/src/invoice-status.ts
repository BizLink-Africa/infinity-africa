/** Lifecycle status of a merchant-issued invoice. */
export enum InvoiceStatus {
  DRAFT = "DRAFT",
  SENT = "SENT",
  PAID = "PAID",
  PARTIALLY_PAID = "PARTIALLY_PAID",
  OVERDUE = "OVERDUE",
  CANCELLED = "CANCELLED",
}

export const INVOICE_STATUS_LABELS: Record<InvoiceStatus, string> = {
  [InvoiceStatus.DRAFT]: "Draft",
  [InvoiceStatus.SENT]: "Sent",
  [InvoiceStatus.PAID]: "Paid",
  [InvoiceStatus.PARTIALLY_PAID]: "Partially Paid",
  [InvoiceStatus.OVERDUE]: "Overdue",
  [InvoiceStatus.CANCELLED]: "Cancelled",
};
