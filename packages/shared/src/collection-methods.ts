/** How a customer pays a merchant (collections) — matches collections.method in the DB schema. */
export enum CollectionMethod {
  USSD_PUSH = "USSD_PUSH",
  STK_PUSH = "STK_PUSH",
  SELCOM_PESA_PUSH = "SELCOM_PESA_PUSH",
  DYNAMIC_QR = "DYNAMIC_QR",
}

export const COLLECTION_METHOD_LABELS: Record<CollectionMethod, string> = {
  [CollectionMethod.USSD_PUSH]: "USSD Push",
  [CollectionMethod.STK_PUSH]: "STK Push",
  [CollectionMethod.SELCOM_PESA_PUSH]: "Selcom Pesa Push",
  [CollectionMethod.DYNAMIC_QR]: "Dynamic QR",
};
