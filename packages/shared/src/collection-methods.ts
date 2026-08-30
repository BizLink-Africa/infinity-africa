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

/** How a collection was initiated — matches collections.source in the DB
 * schema (app/schemas/enums.py::CollectionSource on the backend). Distinct
 * from CollectionMethod (how the customer paid): a Super Admin uses this to
 * see which product surface brought in the payment. */
export enum CollectionSource {
  DASHBOARD_REQUEST = "DASHBOARD_REQUEST",
  PAYMENT_LINK = "PAYMENT_LINK",
  INVOICE = "INVOICE",
  API_PAYMENT_PAGE = "API_PAYMENT_PAGE",
  API_WALLET_PUSH = "API_WALLET_PUSH",
  API_SELCOM_PESA = "API_SELCOM_PESA",
  API_TANQR = "API_TANQR",
  PAY_BY_LINK = "PAY_BY_LINK",
}

export const COLLECTION_SOURCE_LABELS: Record<CollectionSource, string> = {
  [CollectionSource.DASHBOARD_REQUEST]: "Dashboard Request",
  [CollectionSource.PAYMENT_LINK]: "Payment Link",
  [CollectionSource.INVOICE]: "Invoice",
  [CollectionSource.API_PAYMENT_PAGE]: "API Payment Page",
  [CollectionSource.API_WALLET_PUSH]: "API Wallet Push",
  [CollectionSource.API_SELCOM_PESA]: "API Selcom Pesa",
  [CollectionSource.API_TANQR]: "API TanQR",
  [CollectionSource.PAY_BY_LINK]: "Pay by Link",
};
