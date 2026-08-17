/** Withdrawal destination providers — mobile money telcos and banks —
 * supported for a merchant pricing rule's destination_code and a
 * withdrawal's own destination_code snapshot. Mirrors
 * apps/api/app/schemas/enums.py's DestinationCode. */
export enum DestinationCode {
  SELCOM = "SELCOM",
  MPESA = "MPESA",
  AIRTELMONEY = "AIRTELMONEY",
  HALOPESA = "HALOPESA",
  MIXXBYYAS = "MIXXBYYAS",
  TTCLPESA = "TTCLPESA",
  CRDB = "CRDB",
  NMB = "NMB",
  NBC = "NBC",
  ABSA = "ABSA",
  BOA = "BOA",
  DTB = "DTB",
  EQUITY = "EQUITY",
  EXIM = "EXIM",
  KCB = "KCB",
  STANBIC = "STANBIC",
  SCB = "SCB",
  TCB = "TCB",
}

export const DESTINATION_CODE_LABELS: Record<DestinationCode, string> = {
  [DestinationCode.SELCOM]: "Selcom Pesa",
  [DestinationCode.MPESA]: "M-Pesa",
  [DestinationCode.AIRTELMONEY]: "Airtel Money",
  [DestinationCode.HALOPESA]: "HaloPesa",
  [DestinationCode.MIXXBYYAS]: "Mixx by Yas (Tigo Pesa)",
  [DestinationCode.TTCLPESA]: "TTCL Pesa",
  [DestinationCode.CRDB]: "CRDB Bank",
  [DestinationCode.NMB]: "NMB Bank",
  [DestinationCode.NBC]: "NBC Bank",
  [DestinationCode.ABSA]: "Absa Bank",
  [DestinationCode.BOA]: "Bank of Africa",
  [DestinationCode.DTB]: "Diamond Trust Bank",
  [DestinationCode.EQUITY]: "Equity Bank",
  [DestinationCode.EXIM]: "Exim Bank",
  [DestinationCode.KCB]: "KCB Bank",
  [DestinationCode.STANBIC]: "Stanbic Bank",
  [DestinationCode.SCB]: "Standard Chartered Bank",
  [DestinationCode.TCB]: "Tanzania Commercial Bank",
};

/** Which destination codes are reachable through each withdrawal channel —
 * drives the destination-provider picker in the merchant withdrawal form
 * (apps/web/src/components/merchant/withdrawals-view.tsx). */
export const DESTINATION_CODES_BY_METHOD: Record<string, DestinationCode[]> = {
  SELCOM_PESA: [DestinationCode.SELCOM],
  MOBILE_MONEY: [
    DestinationCode.MPESA,
    DestinationCode.AIRTELMONEY,
    DestinationCode.HALOPESA,
    DestinationCode.MIXXBYYAS,
    DestinationCode.TTCLPESA,
  ],
  BANK_ACCOUNT: [
    DestinationCode.CRDB,
    DestinationCode.NMB,
    DestinationCode.NBC,
    DestinationCode.ABSA,
    DestinationCode.BOA,
    DestinationCode.DTB,
    DestinationCode.EQUITY,
    DestinationCode.EXIM,
    DestinationCode.KCB,
    DestinationCode.STANBIC,
    DestinationCode.SCB,
    DestinationCode.TCB,
  ],
};
