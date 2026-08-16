/** Event names delivered to merchant webhook endpoints. */
export enum WebhookEvent {
  COLLECTION_PENDING = "collection.pending",
  COLLECTION_SUCCESS = "collection.success",
  COLLECTION_FAILED = "collection.failed",
  DISBURSEMENT_SUCCESS = "disbursement.success",
  DISBURSEMENT_FAILED = "disbursement.failed",
  INVOICE_PAID = "invoice.paid",
  INVOICE_OVERDUE = "invoice.overdue",
  PAYMENT_LINK_CREATED = "payment_link.created",
  PAYMENT_LINK_PAID = "payment_link.paid",
  PAYMENT_LINK_EXPIRED = "payment_link.expired",
  REFUND_SUCCEEDED = "refund.succeeded",
  REFUND_FAILED = "refund.failed",
  CHARGEBACK_OPENED = "chargeback.opened",
  CHARGEBACK_RESOLVED = "chargeback.resolved",
}

export const WEBHOOK_EVENTS: WebhookEvent[] = Object.values(WebhookEvent);
