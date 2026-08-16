/** Services a merchant selects during onboarding — deliberately excludes
 * withdrawals, which are a merchant-portal function, not a public/onboarding
 * service selection. */
export enum ServiceNeeded {
  PAYMENT_COLLECTION = "PAYMENT_COLLECTION",
  PAYMENT_LINKS = "PAYMENT_LINKS",
  INVOICES = "INVOICES",
  DYNAMIC_QR = "DYNAMIC_QR",
  API_INTEGRATION = "API_INTEGRATION",
}

export const SERVICE_NEEDED_LABELS: Record<ServiceNeeded, string> = {
  [ServiceNeeded.PAYMENT_COLLECTION]: "Payment Collection",
  [ServiceNeeded.PAYMENT_LINKS]: "Payment Links",
  [ServiceNeeded.INVOICES]: "Invoices",
  [ServiceNeeded.DYNAMIC_QR]: "Dynamic QR",
  [ServiceNeeded.API_INTEGRATION]: "API Integration",
};
