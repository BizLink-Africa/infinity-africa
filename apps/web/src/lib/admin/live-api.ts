import "server-only";

import { getAccessToken } from "@/lib/supabase/session";

import type {
  AdminCollectionRow,
  AdminDisputeRow,
  AdminDocumentRequestRow,
  AdminFraudAlertRow,
  AdminInvoiceRow,
  AdminNotificationRow,
  AdminOverview,
  AdminPaymentLinkRow,
  AdminRefundRow,
  AdminTransactionRow,
  AdminWebhookEventRow,
  AdminWithdrawalRow,
  AuditLogRow,
  Merchant,
  MerchantAccountStatus,
  MerchantUserRow,
} from "./types";

/**
 * Live data-access boundary for the 10 in-scope Super Admin dashboard
 * resources (Command Center, Merchants, Merchant Users, Payment Links,
 * Invoices, Collections, Withdrawals, Transactions, Webhooks, Audit Logs) —
 * calls the real apps/api /v1/admin/* endpoints. Server-only, same shape as
 * lib/onboarding/api.ts: every caller is a Server Component or Server
 * Action under app/super-admin/*, so this can safely use the cookie-based
 * getAccessToken() with no Turbopack client/server bundling conflict.
 *
 * The remaining ~15 out-of-scope resources (customers, pricing, api-keys,
 * reconciliation, settlement, compliance-kyc, provider-status,
 * support-tickets, admin-team) stay in lib/admin/api.ts, still mock — that
 * file is still imported by 5 "use client" pages, so it deliberately has no
 * "server-only" marker and must not gain one.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL;
const LIST_ALL_PARAMS = "page=1&page_size=100";

interface ApiEnvelope<T> {
  success: boolean;
  data?: T;
  error?: { code: string; message: string };
}

export class AdminApiError extends Error {
  code?: string;
  constructor(message: string, code?: string) {
    super(message);
    this.code = code;
  }
}

async function authHeader(): Promise<Record<string, string>> {
  const token = await getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Reads never throw — network failure, no session, or a non-2xx all
 * degrade to null/[]/error-state-in-the-UI, matching lib/onboarding/api.ts
 * and lib/portal/api.ts's established convention. */
async function apiGet<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, { headers: await authHeader(), cache: "no-store" });
    if (!res.ok) return null;
    const body: ApiEnvelope<T> = await res.json();
    return body.success ? (body.data ?? null) : null;
  } catch {
    return null;
  }
}

async function apiList<T>(path: string): Promise<T[]> {
  return (await apiGet<T[]>(path)) ?? [];
}

async function apiWrite<T>(path: string, method: "POST" | "PATCH", input?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers: { "Content-Type": "application/json", ...(await authHeader()) },
      body: input !== undefined ? JSON.stringify(input) : undefined,
    });
  } catch {
    throw new AdminApiError("Couldn't reach Infinity Africa. Check your connection and try again.");
  }

  const body: ApiEnvelope<T> = await res.json();
  if (!res.ok || !body.success || body.data === undefined) {
    const error = new AdminApiError(body.error?.message ?? "Request failed", body.error?.code);
    throw error;
  }
  return body.data;
}

// --- Command Center ----------------------------------------------------

export async function getAdminOverview(): Promise<AdminOverview | null> {
  return apiGet<AdminOverview>("/v1/admin/overview");
}

// --- Merchants -----------------------------------------------------------

export async function listAdminMerchants(): Promise<Merchant[]> {
  return apiList<Merchant>(`/v1/admin/merchants?${LIST_ALL_PARAMS}`);
}

export async function updateMerchantStatus(merchantId: string, status: MerchantAccountStatus): Promise<void> {
  await apiWrite(`/v1/merchants/${merchantId}/status`, "PATCH", { status });
}

export async function approveMerchantOnboarding(merchantId: string): Promise<void> {
  await apiWrite(`/v1/admin/onboarding/${merchantId}/approve`, "PATCH");
}

// --- Merchant Users (read-only — no mutation endpoint requested) ---------

export async function listAdminMerchantUsers(): Promise<MerchantUserRow[]> {
  return apiList<MerchantUserRow>(`/v1/admin/merchant-users?${LIST_ALL_PARAMS}`);
}

// --- Payment Links / Invoices / Collections (read-only) -------------------

export async function listAdminPaymentLinks(): Promise<AdminPaymentLinkRow[]> {
  return apiList<AdminPaymentLinkRow>(`/v1/admin/payment-links?${LIST_ALL_PARAMS}`);
}

export async function listAdminInvoices(): Promise<AdminInvoiceRow[]> {
  return apiList<AdminInvoiceRow>(`/v1/admin/invoices?${LIST_ALL_PARAMS}`);
}

export async function listAdminCollections(): Promise<AdminCollectionRow[]> {
  return apiList<AdminCollectionRow>(`/v1/admin/collections?${LIST_ALL_PARAMS}`);
}

// --- Withdrawals -----------------------------------------------------------

export async function listAdminWithdrawals(filters?: {
  status?: string;
  requiresApproval?: boolean;
}): Promise<AdminWithdrawalRow[]> {
  const params = new URLSearchParams(LIST_ALL_PARAMS);
  if (filters?.status) params.set("status", filters.status);
  if (filters?.requiresApproval !== undefined) params.set("requires_approval", String(filters.requiresApproval));
  return apiList<AdminWithdrawalRow>(`/v1/admin/withdrawals?${params.toString()}`);
}

export async function approveWithdrawal(disbursementId: string): Promise<void> {
  await apiWrite(`/v1/disbursements/${disbursementId}/approve`, "POST");
}

export async function rejectWithdrawal(disbursementId: string): Promise<void> {
  await apiWrite(`/v1/disbursements/${disbursementId}/reject`, "POST");
}

// --- Transactions / Webhooks / Audit Logs (read-only) ----------------------

export async function listAdminTransactions(): Promise<AdminTransactionRow[]> {
  return apiList<AdminTransactionRow>(`/v1/admin/transactions?${LIST_ALL_PARAMS}`);
}

export async function listAdminWebhookEvents(): Promise<AdminWebhookEventRow[]> {
  return apiList<AdminWebhookEventRow>(`/v1/admin/webhooks?${LIST_ALL_PARAMS}`);
}

export async function listAdminAuditLogs(): Promise<AuditLogRow[]> {
  return apiList<AuditLogRow>(`/v1/admin/audit-logs?${LIST_ALL_PARAMS}`);
}

// --- Risk monitoring -------------------------------------------------------

export async function listAdminRiskAlerts(): Promise<AdminFraudAlertRow[]> {
  return apiList<AdminFraudAlertRow>(`/v1/admin/risk-alerts?${LIST_ALL_PARAMS}`);
}

export async function updateRiskAlertStatus(alertId: string, status: string, note?: string): Promise<void> {
  await apiWrite(`/v1/admin/risk-alerts/${alertId}/status`, "PATCH", { status, note });
}

export async function addRiskAlertNote(alertId: string, note: string): Promise<void> {
  await apiWrite(`/v1/admin/risk-alerts/${alertId}/notes`, "POST", { note });
}

export async function requestDocumentsForAlert(
  alertId: string,
  input: { requested_documents: string[]; reason: string; due_date?: string },
): Promise<void> {
  await apiWrite(`/v1/admin/risk-alerts/${alertId}/request-documents`, "POST", input);
}

// --- Document requests -----------------------------------------------------

export async function listAdminDocumentRequests(): Promise<AdminDocumentRequestRow[]> {
  return apiList<AdminDocumentRequestRow>("/v1/admin/document-requests");
}

export async function approveDocumentRequest(requestId: string): Promise<void> {
  await apiWrite(`/v1/admin/document-requests/${requestId}/approve`, "PATCH");
}

export async function rejectDocumentRequest(requestId: string): Promise<void> {
  await apiWrite(`/v1/admin/document-requests/${requestId}/reject`, "PATCH");
}

// --- Disputes ----------------------------------------------------------------

export async function listAdminDisputes(): Promise<AdminDisputeRow[]> {
  return apiList<AdminDisputeRow>("/v1/admin/disputes");
}

export async function updateDisputeStatus(disputeId: string, status: string, note?: string): Promise<void> {
  await apiWrite(`/v1/admin/disputes/${disputeId}/status`, "PATCH", { status, note });
}

export async function requestRefundForDispute(disputeId: string, amount: string): Promise<AdminRefundRow> {
  return apiWrite<AdminRefundRow>(`/v1/admin/disputes/${disputeId}/request-refund`, "POST", { amount });
}

export async function updateRefundStatus(
  disputeId: string,
  status: string,
  providerReference?: string,
): Promise<AdminRefundRow> {
  return apiWrite<AdminRefundRow>(`/v1/admin/disputes/${disputeId}/refund-status`, "PATCH", {
    status,
    provider_reference: providerReference,
  });
}

// --- Notifications -----------------------------------------------------------

export async function listAdminNotifications(): Promise<AdminNotificationRow[]> {
  return apiList<AdminNotificationRow>("/v1/admin/notifications");
}
