/** How a customer pays a merchant (collections) — matches collections.method in the DB schema.
 * HOSTED_CHECKOUT (added 2026-08-23) is now the default for every new
 * collection/payment-link; the other four remain valid for old rows. */
export enum CollectionMethod {
  USSD_PUSH = "USSD_PUSH",
  STK_PUSH = "STK_PUSH",
  SELCOM_PESA_PUSH = "SELCOM_PESA_PUSH",
  DYNAMIC_QR = "DYNAMIC_QR",
  HOSTED_CHECKOUT = "HOSTED_CHECKOUT",
}

export const COLLECTION_METHOD_LABELS: Record<CollectionMethod, string> = {
  [CollectionMethod.USSD_PUSH]: "USSD Push",
  [CollectionMethod.STK_PUSH]: "STK Push",
  [CollectionMethod.SELCOM_PESA_PUSH]: "Selcom Pesa Push",
  [CollectionMethod.DYNAMIC_QR]: "Dynamic QR",
  [CollectionMethod.HOSTED_CHECKOUT]: "Selcom Hosted Checkout",
};
