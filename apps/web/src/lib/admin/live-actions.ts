"use server";

import { revalidatePath } from "next/cache";

import {
  addRiskAlertNote,
  approveDocumentRequest,
  approveMerchantOnboarding,
  approveWithdrawal,
  rejectDocumentRequest,
  rejectWithdrawal,
  requestDocumentsForAlert,
  requestRefundForDispute,
  updateDisputeStatus,
  updateMerchantStatus,
  updateRefundStatus,
  updateRiskAlertStatus,
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

export async function approveWithdrawalAction(withdrawalId: string) {
  await approveWithdrawal(withdrawalId);
  revalidatePath("/super-admin/withdrawals");
}

export async function rejectWithdrawalAction(withdrawalId: string) {
  await rejectWithdrawal(withdrawalId);
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
