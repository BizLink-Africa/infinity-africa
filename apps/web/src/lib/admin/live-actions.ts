"use server";

import { revalidatePath } from "next/cache";

import {
  addRiskAlertNote,
  approveDocumentRequest,
  approveIpAllowlistEntry,
  approveMerchantOnboarding,
  approveWithdrawal,
  createMerchantPricingRule,
  createPlatformFallbackPricingRule,
  deactivatePricingRule,
  disableProductionApiAccess,
  enableProductionApiAccess,
  rejectDocumentRequest,
  rejectIpAllowlistEntry,
  rejectWithdrawal,
  reconcilePendingWithdrawals,
  refreshWithdrawalStatus,
  requestDocumentsForAlert,
  requestInfoWithdrawal,
  requestRefundForDispute,
  revokeAdminApiKey,
  updateDisputeStatus,
  updateMerchantStatus,
  updatePricingRule,
  updateRefundStatus,
  updateRiskAlertStatus,
  type PricingRuleInput,
} from "./live-api";
import type { MerchantAccountStatus } from "./types";

export async function approveMerchantAction(merchantId: string) {
  await approveMerchantOnboarding(merchantId);
  revalidatePath("/super-admin/merchants");
}

export async function setMerchantStatusAction(merchantId: string, status: MerchantAccountStatus) {
  await updateMerchantStatus(merchantId, status);
  revalidatePath("/super-admin/merchants");
}

export async function revokeAdminApiKeyAction(apiKeyId: string) {
  await revokeAdminApiKey(apiKeyId);
  revalidatePath("/super-admin/api-keys");
}

export async function enableProductionApiAccessAction(merchantId: string) {
  await enableProductionApiAccess(merchantId);
  revalidatePath(`/super-admin/merchants/${merchantId}`);
}

export async function disableProductionApiAccessAction(merchantId: string) {
  await disableProductionApiAccess(merchantId);
  revalidatePath(`/super-admin/merchants/${merchantId}`);
}

export async function approveIpAllowlistEntryAction(entryId: string, merchantId: string) {
  await approveIpAllowlistEntry(entryId);
  revalidatePath(`/super-admin/merchants/${merchantId}`);
}

export async function rejectIpAllowlistEntryAction(entryId: string, merchantId: string) {
  await rejectIpAllowlistEntry(entryId);
  revalidatePath(`/super-admin/merchants/${merchantId}`);
}

export async function approveWithdrawalAction(withdrawalId: string) {
  await approveWithdrawal(withdrawalId);
  revalidatePath("/super-admin/withdrawals");
}

export async function rejectWithdrawalAction(withdrawalId: string, formData: FormData) {
  const rejectionReason = String(formData.get("rejection_reason") ?? "").trim();
  if (!rejectionReason) return;
  await rejectWithdrawal(withdrawalId, rejectionReason);
  revalidatePath("/super-admin/withdrawals");
}

export async function requestInfoWithdrawalAction(withdrawalId: string, formData: FormData) {
  const message = String(formData.get("message") ?? "").trim();
  if (!message) return;
  const requestedDocuments = String(formData.get("requested_documents") ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  await requestInfoWithdrawal(withdrawalId, { message, requestedDocuments });
  revalidatePath("/super-admin/withdrawals");
}

export async function refreshWithdrawalStatusAction(withdrawalId: string) {
  await refreshWithdrawalStatus(withdrawalId);
  revalidatePath("/super-admin/withdrawals");
}

export async function reconcilePendingWithdrawalsAction() {
  await reconcilePendingWithdrawals();
  revalidatePath("/super-admin/withdrawals");
}

// --- Risk monitoring ---------------------------------------------------------

export async function updateRiskAlertStatusAction(alertId: string, formData: FormData) {
  const status = String(formData.get("status") ?? "");
  if (!status) return;
  await updateRiskAlertStatus(alertId, status);
  revalidatePath("/super-admin/risk-monitoring");
}

export async function addRiskAlertNoteAction(alertId: string, formData: FormData) {
  const note = String(formData.get("note") ?? "").trim();
  if (!note) return;
  await addRiskAlertNote(alertId, note);
  revalidatePath("/super-admin/risk-monitoring");
}

export async function requestDocumentsForAlertAction(alertId: string, formData: FormData) {
  const requestedDocuments = String(formData.get("requested_documents") ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  const reason = String(formData.get("reason") ?? "").trim();
  if (requestedDocuments.length === 0 || !reason) return;
  await requestDocumentsForAlert(alertId, { requested_documents: requestedDocuments, reason });
  revalidatePath("/super-admin/risk-monitoring");
  revalidatePath("/super-admin/document-requests");
}

// --- Document requests -------------------------------------------------------

export async function approveDocumentRequestAction(requestId: string) {
  await approveDocumentRequest(requestId);
  revalidatePath("/super-admin/document-requests");
}

export async function rejectDocumentRequestAction(requestId: string) {
  await rejectDocumentRequest(requestId);
  revalidatePath("/super-admin/document-requests");
}

// --- Disputes ------------------------------------------------------------------

export async function updateDisputeStatusAction(disputeId: string, formData: FormData) {
  const status = String(formData.get("status") ?? "");
  if (!status) return;
  const note = String(formData.get("note") ?? "").trim() || undefined;
  await updateDisputeStatus(disputeId, status, note);
  revalidatePath("/super-admin/disputes");
}

export async function requestRefundForDisputeAction(disputeId: string, formData: FormData) {
  const amount = String(formData.get("amount") ?? "").trim();
  if (!amount) return;
  await requestRefundForDispute(disputeId, amount);
  revalidatePath("/super-admin/disputes");
}

export async function updateRefundStatusAction(disputeId: string, formData: FormData) {
  const status = String(formData.get("status") ?? "");
  if (!status) return;
  await updateRefundStatus(disputeId, status);
  revalidatePath("/super-admin/disputes");
}

// --- Pricing rules -------------------------------------------------------------

function pricingRuleInputFromFormData(formData: FormData): PricingRuleInput {
  const get = (key: string) => {
    const value = String(formData.get(key) ?? "").trim();
    return value ? value : undefined;
  };
  return {
    channel: get("channel") ?? null,
    destination_code: get("destination_code") ?? null,
    percentage_fee: get("percentage_fee") ?? "0",
    flat_fee: get("flat_fee") ?? "0",
    minimum_fee: get("minimum_fee") ?? null,
    maximum_fee: get("maximum_fee") ?? null,
    processor_fee_flat: get("processor_fee_flat") ?? "0",
    processor_fee_pass_through: formData.get("processor_fee_pass_through") === "on",
    effective_from: get("effective_from") ?? null,
    effective_to: get("effective_to") ?? null,
    label: get("label") ?? null,
  };
}

export async function createMerchantPricingRuleAction(merchantId: string, formData: FormData) {
  await createMerchantPricingRule(merchantId, pricingRuleInputFromFormData(formData));
  revalidatePath("/super-admin/pricing-rules");
}

export async function createPlatformFallbackPricingRuleAction(formData: FormData) {
  await createPlatformFallbackPricingRule(pricingRuleInputFromFormData(formData));
  revalidatePath("/super-admin/pricing-rules");
}

export async function updatePricingRuleAction(ruleId: string, formData: FormData) {
  await updatePricingRule(ruleId, pricingRuleInputFromFormData(formData));
  revalidatePath("/super-admin/pricing-rules");
}

export async function deactivatePricingRuleAction(ruleId: string) {
  await deactivatePricingRule(ruleId);
  revalidatePath("/super-admin/pricing-rules");
}
