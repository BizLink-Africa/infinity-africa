/**
 * Data-access boundary for the merchant portal.
 *
 * Payment links, invoices, collections, withdrawals (disbursements),
 * transactions, API keys, and webhooks call the real apps/api /v1/merchant/*
 * endpoints — see docs/api.md. Everything else (customers, wallet, team,
 * support) still resolves against the in-memory mock-data.ts arrays, since
 * no corresponding self-service endpoint exists yet; each section below is
 * labeled LIVE or MOCK accordingly.
 *
 * No component should import mock-data.ts directly — only this file does.
 */

import { getAccessTokenClient } from "@/lib/supabase/client-session";

import {
  mockCustomers,
  mockSupportTickets,
  mockTeamMembers,
  mockWalletAccounts,
  mockWalletLedger,
  MOCK_MERCHANT_ID,
} from "./mock-data";
import type {
  ApiEnvelope,
  ApiKey,
  AppNotification,
  Collection,
  Customer,
  Disbursement,
  Dispute,
  DisputeWithMessages,
  DocumentRequest,
  FraudAlert,
  Invoice,
  InvoiceItem,
  PaymentLink,
  Refund,
  SupportTicket,
  TeamMember,
  Transaction,
  WalletAccount,
  WalletLedgerEntry,
  WebhookConfig,
  WebhookConfigWithSecret,
  WebhookEvent,
  WebhookTestResult,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL;

/**
 * Attaches the signed-in merchant's Supabase access token as
 * `Authorization: Bearer <token>`. Every page that calls into this file is
 * a Client Component (including transactions/page.tsx, converted from a
 * Server Component specifically so this file could stay single and
 * client-only) — so the client-safe getAccessTokenClient() is the only
 * token getter this module ever needs. A "server-only"-marked getter
 * must never be imported here, even dynamically: Turbopack's production
 * build still traces a dynamic import() into the module graph for the
 * server-only check, so it fails the build the same as a static import
 * would — this file, and everything it imports, must stay client-safe.
 */
async function getAuthHeader(): Promise<Record<string, string>> {
  const token = await getAccessTokenClient();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function idempotencyKey(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `idem-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

/** Reads never throw on a network failure (backend unreachable, DNS,
 * timeout) — same "return null, let the caller decide what to show"
 * convention as lib/payment-links.ts's fetchPublicPaymentLink. */
async function apiGet<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, { headers: await getAuthHeader(), cache: "no-store" });
    if (!res.ok) return null;
    const body: ApiEnvelope<T> = await res.json();
    return body.success ? (body.data ?? null) : null;
  } catch {
    return null;
  }
}

async function apiWrite<T>(
  path: string,
  method: "POST" | "PATCH",
  input: unknown,
  { idempotent = false }: { idempotent?: boolean } = {},
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(idempotent ? { "Idempotency-Key": idempotencyKey() } : {}),
        ...(await getAuthHeader()),
      },
      body: JSON.stringify(input),
    });
  } catch {
    // Network failure (backend unreachable, DNS, timeout) — not a response
    // the backend sent, so there's no error.code to preserve.
    throw new Error("Couldn't reach Infinity Africa. Check your connection and try again.");
  }

  const body: ApiEnvelope<T> = await res.json();
  if (!res.ok || !body.success || body.data === undefined) {
    const error = new Error(body.error?.message ?? "Request failed") as Error & { code?: string };
    error.code = body.error?.code;
    throw error;
  }
  return body.data;
}

// --- Payment Links (LIVE) ---------------------------------------------------

export async function listPaymentLinks(): Promise<PaymentLink[]> {
  return (await apiGet<PaymentLink[]>("/v1/merchant/payment-links")) ?? [];
}

export async function getPaymentLink(id: string): Promise<PaymentLink | null> {
  return apiGet<PaymentLink>(`/v1/merchant/payment-links/${id}`);
}

export interface CreatePaymentLinkInput {
  amount: string;
  currency: string;
  customer_name: string | null;
  customer_phone: string | null;
  customer_email: string | null;
  description: string | null;
  allowed_payment_methods: PaymentLink["allowed_payment_methods"];
  expires_at: string | null;
  merchant_reference: string | null;
  success_redirect_url: string | null;
  failure_redirect_url: string | null;
}

export async function createPaymentLink(input: CreatePaymentLinkInput): Promise<PaymentLink> {
  return apiWrite<PaymentLink>("/v1/merchant/payment-links", "POST", input, { idempotent: true });
}

export type UpdatePaymentLinkInput = Partial<CreatePaymentLinkInput>;

export async function updatePaymentLink(id: string, input: UpdatePaymentLinkInput): Promise<PaymentLink> {
  return apiWrite<PaymentLink>(`/v1/merchant/payment-links/${id}`, "PATCH", input);
}

export async function cancelPaymentLink(id: string): Promise<PaymentLink> {
  return apiWrite<PaymentLink>(`/v1/merchant/payment-links/${id}/cancel`, "PATCH", {});
}

// --- Invoices (LIVE) ---------------------------------------------------------

export async function listInvoices(): Promise<Invoice[]> {
  return (await apiGet<Invoice[]>("/v1/merchant/invoices")) ?? [];
}

export interface CreateInvoiceInput {
  customer_name: string;
  customer_phone: string | null;
  customer_email: string | null;
  due_date: string;
  notes: string | null;
  items: Array<Pick<InvoiceItem, "description" | "quantity" | "unit_price">>;
  send_now: boolean;
}

export async function createInvoice(input: CreateInvoiceInput): Promise<Invoice> {
  const invoice = await apiWrite<Invoice>("/v1/merchant/invoices", "POST", {
    customer_name: input.customer_name,
    customer_phone: input.customer_phone,
    customer_email: input.customer_email,
    due_date: input.due_date,
    notes: input.notes,
    items: input.items.map((item) => ({ description: item.description, quantity: item.quantity, unit_price: item.unit_price })),
  });

  if (input.send_now) {
    return apiWrite<Invoice>(`/v1/merchant/invoices/${invoice.id}/send`, "POST", {});
  }
  return invoice;
}

// --- Collections (LIVE) ----------------------------------------------------

const COLLECTION_METHOD_PATHS: Record<Collection["method"], string> = {
  USSD_PUSH: "ussd-push",
  STK_PUSH: "stk-push",
  SELCOM_PESA_PUSH: "selcom-pesa-push",
  DYNAMIC_QR: "dynamic-qr",
};

export async function listCollections(): Promise<Collection[]> {
  return (await apiGet<Collection[]>("/v1/merchant/collections")) ?? [];
}

export interface CreateCollectionInput {
  customer_name: string;
  customer_phone: string;
  customer_email?: string | null;
  amount: string;
  method: Collection["method"];
  description: string | null;
  callback_url?: string | null;
  invoice_id?: string | null;
}

export async function createCollection(input: CreateCollectionInput): Promise<Collection> {
  const path = `/v1/merchant/collections/${COLLECTION_METHOD_PATHS[input.method]}`;
  return apiWrite<Collection>(
    path,
    "POST",
    {
      amount: input.amount,
      currency: "TZS",
      customer_phone: input.customer_phone,
      customer_name: input.customer_name,
      customer_email: input.customer_email ?? null,
      description: input.description,
      callback_url: input.callback_url ?? null,
      invoice_id: input.invoice_id ?? null,
    },
    { idempotent: true },
  );
}

// --- Withdrawals (LIVE — /v1/merchant/withdrawals; frontend keeps calling
// this "disbursement" internally, matching the existing Disbursement type
// and the established "Withdrawals" (UI) / "disbursement" (code) naming
// convention already used elsewhere in the portal). ------------------------

export async function listDisbursements(): Promise<Disbursement[]> {
  return (await apiGet<Disbursement[]>("/v1/merchant/withdrawals")) ?? [];
}

export async function getAvailableBalance(): Promise<string> {
  const overview = await apiGet<{ available_balance: string }>("/v1/merchant/overview");
  return overview?.available_balance ?? "0";
}

export interface CreateDisbursementInput {
  method: Disbursement["method"];
  destination_name: string;
  destination_identifier: string;
  bank_name: string | null;
  amount: string;
  network?: string | null;
  description?: string | null;
}

export class InsufficientBalanceError extends Error {}

export async function createDisbursement(input: CreateDisbursementInput): Promise<Disbursement> {
  const isBank = input.method === "BANK_ACCOUNT";
  const isMobileMoney = input.method === "MOBILE_MONEY";
  const payload = {
    method: input.method,
    amount: input.amount,
    currency: "TZS",
    destination_name: input.destination_name,
    destination_phone: isBank ? null : input.destination_identifier,
    bank_name: isBank ? input.bank_name : null,
    bank_account_number: isBank ? input.destination_identifier : null,
    bank_account_name: isBank ? input.destination_name : null,
    network: isMobileMoney ? (input.network ?? null) : null,
    description: input.description ?? null,
  };

  try {
    return await apiWrite<Disbursement>("/v1/merchant/withdrawals", "POST", payload, { idempotent: true });
  } catch (err) {
    const error = err as Error & { code?: string };
    if (error.code === "insufficient_balance") {
      throw new InsufficientBalanceError(error.message);
    }
    throw err;
  }
}

// --- Transactions (LIVE) ----------------------------------------------------

export async function listTransactions(): Promise<Transaction[]> {
  return (await apiGet<Transaction[]>("/v1/merchant/transactions")) ?? [];
}

// --- API Keys (LIVE) ---------------------------------------------------------

export async function listApiKeys(): Promise<ApiKey[]> {
  return (await apiGet<ApiKey[]>("/v1/merchant/api-keys")) ?? [];
}

export async function createApiKey(input: {
  name: string;
  environment: ApiKey["environment"];
  scopes: string[];
}): Promise<{ key: ApiKey; plaintext_key: string }> {
  const created = await apiWrite<ApiKey & { plaintext_key: string }>("/v1/merchant/api-keys", "POST", input);
  const { plaintext_key, ...key } = created;
  return { key: key as ApiKey, plaintext_key };
}

export async function revokeApiKey(apiKeyId: string): Promise<ApiKey> {
  return apiWrite<ApiKey>(`/v1/merchant/api-keys/${apiKeyId}/revoke`, "PATCH", {});
}

// --- Overview (LIVE) ---------------------------------------------------------

export interface MerchantOverview {
  merchant: { id: string; business_name: string; currency: string; status: string; kyc_status: string };
  total_collections: string;
  available_balance: string;
  pending_transactions: number;
  successful_withdrawals: number;
  active_payment_links: number;
  unpaid_invoices: number;
  total_fees_charged: string;
}

/** Returns null on any non-2xx (no real merchant yet for this user, token
 * expired, network error) — the merchant overview page falls back to the
 * onboarding-status view in that case rather than erroring. */
export async function getMerchantOverview(): Promise<MerchantOverview | null> {
  return apiGet<MerchantOverview>("/v1/merchant/overview");
}

// ============================================================================
// Everything below is still MOCK — no /v1/merchant/* endpoint exists yet for
// customers, wallet, team, support, or webhooks.
// ============================================================================

const mockStore = {
  customers: mockCustomers(),
  walletAccounts: mockWalletAccounts(),
  walletLedger: mockWalletLedger(),
  teamMembers: mockTeamMembers(),
  supportTickets: mockSupportTickets(),
};

let sequence = 1;
function generateId(prefix: string): string {
  sequence += 1;
  return `${prefix}-${Date.now().toString(36)}${sequence}`;
}

function nowIso(): string {
  return new Date().toISOString();
}

// --- Customers (MOCK) --------------------------------------------------------

export async function listCustomers(): Promise<Customer[]> {
  return mockStore.customers;
}

export interface CreateCustomerInput {
  name: string;
  phone: string | null;
  email: string | null;
}

export async function createCustomer(input: CreateCustomerInput): Promise<Customer> {
  const customer: Customer = {
    id: generateId("cus"),
    merchant_id: MOCK_MERCHANT_ID,
    name: input.name,
    phone: input.phone,
    email: input.email,
    total_spent: "0.00",
    last_transaction_at: null,
    status: "active",
    created_at: nowIso(),
  };
  mockStore.customers = [customer, ...mockStore.customers];
  return customer;
}

// --- Wallet (MOCK) ------------------------------------------------------------

export async function listWalletAccounts(): Promise<WalletAccount[]> {
  return mockStore.walletAccounts;
}

export async function listWalletLedger(): Promise<WalletLedgerEntry[]> {
  return mockStore.walletLedger;
}

// --- Team / Support (MOCK) ----------------------------------------------------

export async function listTeamMembers(): Promise<TeamMember[]> {
  return mockStore.teamMembers;
}

export async function listSupportTickets(): Promise<SupportTicket[]> {
  return mockStore.supportTickets;
}

export async function createSupportTicket(input: { subject: string; category: string }): Promise<SupportTicket> {
  const ticket: SupportTicket = {
    id: generateId("tkt"),
    subject: input.subject,
    category: input.category,
    status: "open",
    created_at: nowIso(),
  };
  mockStore.supportTickets = [ticket, ...mockStore.supportTickets];
  return ticket;
}

// --- Webhooks (LIVE) ---------------------------------------------------------

export async function getWebhookConfig(): Promise<WebhookConfig | null> {
  return apiGet<WebhookConfig>("/v1/merchant/webhook-config");
}

export interface UpdateWebhookConfigInput {
  webhook_url?: string;
  subscribed_events?: string[];
  regenerate_secret?: boolean;
}

export async function updateWebhookConfig(input: UpdateWebhookConfigInput): Promise<WebhookConfigWithSecret> {
  return apiWrite<WebhookConfigWithSecret>("/v1/merchant/webhook-config", "PATCH", input);
}

export async function sendTestWebhook(): Promise<WebhookTestResult> {
  return apiWrite<WebhookTestResult>("/v1/merchant/webhook-config/test", "POST", {});
}

export async function listWebhookEvents(): Promise<WebhookEvent[]> {
  return (await apiGet<WebhookEvent[]>("/v1/merchant/webhook-events")) ?? [];
}

// --- Risk monitoring (LIVE) --------------------------------------------------

export async function listMyRiskAlerts(): Promise<FraudAlert[]> {
  return (await apiGet<FraudAlert[]>("/v1/merchant/risk-alerts")) ?? [];
}

// --- Document requests (LIVE) ------------------------------------------------

export async function listMyDocumentRequests(): Promise<DocumentRequest[]> {
  return (await apiGet<DocumentRequest[]>("/v1/merchant/document-requests")) ?? [];
}

export async function submitDocumentRequestFile(
  requestId: string,
  documentLabel: string,
  file: File,
): Promise<DocumentRequest> {
  const formData = new FormData();
  formData.append("document_label", documentLabel);
  formData.append("file", file);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/v1/merchant/document-requests/${requestId}/submit`, {
      method: "POST",
      headers: await getAuthHeader(),
      body: formData,
    });
  } catch {
    throw new Error("Couldn't reach Infinity Africa. Check your connection and try again.");
  }
  const body: ApiEnvelope<DocumentRequest> = await res.json();
  if (!res.ok || !body.success || body.data === undefined) {
    const error = new Error(body.error?.message ?? "Request failed") as Error & { code?: string };
    error.code = body.error?.code;
    throw error;
  }
  return body.data;
}

// --- Disputes (LIVE) -----------------------------------------------------------

export async function listMyDisputes(): Promise<Dispute[]> {
  return (await apiGet<Dispute[]>("/v1/merchant/disputes")) ?? [];
}

export async function getMyDispute(disputeId: string): Promise<DisputeWithMessages | null> {
  return apiGet<DisputeWithMessages>(`/v1/merchant/disputes/${disputeId}`);
}

export async function respondToDispute(disputeId: string, body: string): Promise<DisputeWithMessages> {
  return apiWrite<DisputeWithMessages>(`/v1/merchant/disputes/${disputeId}/respond`, "POST", { body });
}

export async function acceptRefund(disputeId: string, amount: string): Promise<Refund> {
  return apiWrite<Refund>(`/v1/merchant/disputes/${disputeId}/accept-refund`, "POST", { amount });
}

// --- Notifications (LIVE) ----------------------------------------------------

export async function listMyNotifications(): Promise<AppNotification[]> {
  return (await apiGet<AppNotification[]>("/v1/merchant/notifications")) ?? [];
}
