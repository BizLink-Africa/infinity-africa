/**
 * Mirrors apps/api's Pydantic response schemas field-for-field (snake_case,
 * amounts as strings, ISO timestamps as strings) so the mock data layer and
 * the real FastAPI responses are interchangeable without a translation
 * layer — see lib/portal/api.ts.
 */

import type {
  CollectionMethod,
  DisbursementMethod,
  DisbursementStatus,
  InvoiceStatus,
  PaymentLinkStatus,
} from "@infinity/shared";

/** Mirrors apps/api's {success, data} / {success, error} envelope. */
export interface ApiEnvelope<T> {
  success: boolean;
  data?: T;
  error?: { code: string; message: string };
  meta?: { page: number; page_size: number; total: number; total_pages: number } | null;
}

export interface PaymentLink {
  id: string;
  merchant_id: string;
  customer_id: string | null;
  amount: string;
  currency: string;
  customer_name: string | null;
  customer_phone: string | null;
  customer_email: string | null;
  description: string | null;
  allowed_payment_methods: CollectionMethod[];
  expires_at: string | null;
  status: PaymentLinkStatus;
  public_slug: string;
  public_url: string;
  merchant_reference: string | null;
  success_redirect_url: string | null;
  failure_redirect_url: string | null;
  paid_at: string | null;
  attempt_count: number;
  created_at: string;
  updated_at: string;
}

export interface InvoiceItem {
  id: string;
  description: string;
  quantity: string;
  unit_price: string;
  line_total: string;
  sort_order: number;
}

export interface Invoice {
  id: string;
  merchant_id: string;
  customer_id: string | null;
  invoice_number: string;
  customer_name: string | null;
  customer_email: string | null;
  customer_phone: string | null;
  due_date: string;
  currency: string;
  subtotal: string;
  tax_amount: string;
  discount_amount: string;
  total_amount: string;
  amount_paid: string;
  status: InvoiceStatus;
  payment_link_id: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  items: InvoiceItem[];
}

/** collections.status — a 3-state in-flight/resolved lifecycle, distinct
 * from the uppercase DisbursementStatus / TS-shared TransactionStatus. */
export type CollectionStatus = "processing" | "successful" | "failed";

export interface Collection {
  id: string;
  merchant_id: string;
  customer_id: string | null;
  payment_link_id: string | null;
  invoice_id: string | null;
  merchant_reference: string | null;
  method: CollectionMethod;
  amount: string;
  currency: string;
  customer_phone: string | null;
  status: CollectionStatus;
  provider: string | null;
  provider_reference: string | null;
  transaction_reference: string | null;
  message: string | null;
  expires_at: string | null;
  initiated_at: string;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Disbursement {
  id: string;
  merchant_id: string;
  settlement_account_id: string | null;
  method: DisbursementMethod;
  amount: string;
  currency: string;
  destination_name: string;
  destination_identifier: string;
  bank_name: string | null;
  status: DisbursementStatus;
  requires_approval: boolean;
  approved_by: string | null;
  approved_at: string | null;
  provider_reference: string | null;
  transaction_reference: string | null;
  fee_amount: string | null;
  net_amount: string | null;
  initiated_at: string;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export type TransactionType = "collection" | "disbursement" | "fee" | "refund" | "reversal" | "adjustment";
export type TransactionStatus = "pending" | "processing" | "successful" | "failed" | "reversed" | "cancelled";

export interface Transaction {
  id: string;
  merchant_id: string;
  reference: string;
  provider_reference: string | null;
  type: TransactionType;
  method: string;
  collection_id: string | null;
  disbursement_id: string | null;
  gross_amount: string;
  fee_amount: string;
  net_amount: string;
  currency: string;
  status: TransactionStatus;
  created_at: string;
}

export interface Customer {
  id: string;
  merchant_id: string;
  name: string;
  phone: string | null;
  email: string | null;
  total_spent: string;
  last_transaction_at: string | null;
  status: "active" | "inactive";
  created_at: string;
}

export interface ApiKey {
  id: string;
  merchant_id: string;
  name: string;
  environment: "sandbox" | "live";
  key_prefix: string;
  scopes: string[];
  status: "active" | "revoked";
  last_used_at: string | null;
  revoked_at: string | null;
  created_at: string;
  updated_at: string;
}

/** The 8 scopes a merchant can grant an API key — mirrors
 * app.schemas.api_keys.API_KEY_SCOPES. */
export const API_KEY_SCOPES = [
  "collections:write",
  "collections:read",
  "payment_links:write",
  "payment_links:read",
  "invoices:write",
  "invoices:read",
  "transactions:read",
  "webhooks:manage",
] as const;

export type ApiKeyScope = (typeof API_KEY_SCOPES)[number];

export interface WalletAccount {
  id: string;
  method: DisbursementMethod;
  label: string;
  masked_identifier: string;
  is_default: boolean;
}

export interface WalletLedgerEntry {
  id: string;
  date: string;
  description: string;
  direction: "credit" | "debit";
  amount: string;
  balance_after: string;
}

export interface TeamMember {
  id: string;
  name: string;
  email: string;
  role: "Owner" | "Admin" | "Finance";
  status: "active" | "pending";
}

export interface SupportTicket {
  id: string;
  subject: string;
  category: string;
  status: "open" | "resolved";
  created_at: string;
}

/** The events services/webhooks.py can enqueue — mirrors the
 * webhook_events.event_name CHECK constraint. */
export const WEBHOOK_EVENT_NAMES = [
  "collection.pending",
  "collection.success",
  "collection.failed",
  "disbursement.success",
  "disbursement.failed",
  "invoice.paid",
  "invoice.overdue",
  "payment_link.created",
  "payment_link.paid",
  "payment_link.expired",
  "refund.succeeded",
  "refund.failed",
  "chargeback.opened",
  "chargeback.resolved",
] as const;

export interface WebhookLastDelivery {
  event_name: string;
  status: string;
  created_at: string;
}

export interface WebhookConfig {
  webhook_url: string | null;
  subscribed_events: string[] | null;
  has_secret: boolean;
  last_delivery: WebhookLastDelivery | null;
}

/** Only present once, immediately after regenerate_secret: true. */
export interface WebhookConfigWithSecret extends WebhookConfig {
  secret: string | null;
}

export interface WebhookTestResult {
  delivered: boolean;
  http_status: number | null;
  latency_ms: number;
}

/** Mirrors app.schemas.webhook_config.WebhookEventResponse — a row from the
 * outbound delivery queue (webhook_events), not yet auto-delivered by a
 * worker (see docs/api.md's Webhooks page for the current state of that). */
export interface WebhookEvent {
  id: string;
  event_name: string;
  payload: Record<string, unknown>;
  target_url: string;
  status: "pending" | "delivered" | "failed" | "retrying";
  attempts: number;
  last_attempted_at: string | null;
  delivered_at: string | null;
  response_status_code: number | null;
  created_at: string;
}

// --- Risk monitoring / disputes / refunds -----------------------------------

export type FraudRiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type FraudAlertStatus = "OPEN" | "UNDER_REVIEW" | "DOCUMENTS_REQUESTED" | "CLEARED" | "ESCALATED" | "CLOSED";

export interface FraudAlert {
  id: string;
  merchant_id: string;
  transaction_id: string | null;
  customer_phone: string | null;
  rule_code: string;
  risk_level: FraudRiskLevel;
  reason: string;
  status: FraudAlertStatus;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export type DocumentRequestStatus = "PENDING" | "SUBMITTED" | "APPROVED" | "REJECTED";

export interface DocumentRequestFile {
  id: string;
  request_id: string;
  document_label: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  created_at: string;
}

export interface DocumentRequest {
  id: string;
  merchant_id: string;
  transaction_id: string | null;
  alert_id: string | null;
  requested_documents: string[];
  reason: string;
  status: DocumentRequestStatus;
  due_date: string | null;
  created_at: string;
  updated_at: string;
  files: DocumentRequestFile[];
}

export const DISPUTE_REASON_CATEGORIES = [
  "PRODUCT_NOT_RECEIVED",
  "SERVICE_NOT_DELIVERED",
  "WRONG_PRODUCT_OR_SERVICE",
  "DUPLICATE_PAYMENT",
  "UNAUTHORIZED_PAYMENT",
  "REFUND_REQUESTED",
  "OTHER",
] as const;
export type DisputeReasonCategory = (typeof DISPUTE_REASON_CATEGORIES)[number];

export type DisputeStatus =
  | "SUBMITTED"
  | "MERCHANT_NOTIFIED"
  | "UNDER_REVIEW"
  | "REFUND_REQUESTED"
  | "REFUNDED"
  | "REJECTED"
  | "CLOSED";

export interface DisputeMessage {
  id: string;
  dispute_id: string;
  sender_type: "merchant" | "admin" | "system";
  sender_id: string | null;
  body: string;
  attachment_files: Array<{ file_path: string; original_filename: string }>;
  created_at: string;
}

export interface Dispute {
  id: string;
  merchant_id: string | null;
  transaction_id: string | null;
  customer_name: string;
  customer_phone: string;
  customer_email: string | null;
  transaction_reference: string | null;
  amount: string | null;
  reason_category: DisputeReasonCategory;
  description: string;
  status: DisputeStatus;
  evidence_files: Array<{ file_path: string; original_filename: string }>;
  created_at: string;
  updated_at: string;
}

export interface DisputeWithMessages extends Dispute {
  messages: DisputeMessage[];
}

export type RefundStatus = "REQUESTED" | "APPROVED" | "PROCESSING" | "SUCCESS" | "FAILED" | "CANCELLED";

export interface Refund {
  id: string;
  dispute_id: string;
  transaction_id: string;
  merchant_id: string;
  amount: string;
  currency: string;
  status: RefundStatus;
  requested_by: "merchant" | "admin";
  evidence_files: Array<{ file_path: string; original_filename: string }>;
  provider_reference: string | null;
  created_at: string;
  updated_at: string;
}

export interface AppNotification {
  id: string;
  recipient_type: "merchant" | "admin";
  merchant_id: string | null;
  notification_type: "fraud_alert" | "document_request" | "dispute_received" | "refund_requested" | "dispute_status_updated";
  title: string;
  body: string;
  related_resource_type: string | null;
  related_resource_id: string | null;
  is_read: boolean;
  created_at: string;
}
