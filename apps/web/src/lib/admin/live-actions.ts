"use server";

import { revalidatePath } from "next/cache";

import {
  activateCollectionPricingRule,
  addRiskAlertNote,
  approveDocumentRequest,
  approveIpAllowlistEntry,
  approveMerchantOnboarding,
  approveWithdrawal,
  createMerchantCollectionPricingRule,
  createMerchantPricingRule,
  createPlatformFallbackCollectionPricingRule,
  createPlatformFallbackPricingRule,
  deactivateCollectionPricingRule,
  deactivatePricingRule,
  reconcilePendingWithdrawals,
  refreshWithdrawalStatus,
  reinstateMerchantApiAccess,
  rejectDocumentRequest,
  rejectIpAllowlistEntry,
  rejectWithdrawal,
  requestDocumentsForAlert,
  requestInfoWithdrawal,
  requestRefundForDispute,
  revokeAdminApiKey,
  suspendMerchantApiAccess,
  updateAdminMerchantNotificationSettings,
  updateCollectionPricingRule,
  updateDisputeStatus,
  updateMerchantStatus,
  updatePricingRule,
  updateRefundStatus,
  updateRiskAlertStatus,
  type CollectionPricingRuleInput,
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

export async function suspendMerchantApiAccessAction(merchantId: string) {
  await suspendMerchantApiAccess(merchantId);
  revalidatePath(`/super-admin/merchants/${merchantId}`);
}

export async function reinstateMerchantApiAccessAction(merchantId: string) {
  await reinstateMerchantApiAccess(merchantId);
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

export interface PricingRuleActionState {
  error: string | null;
}

/** A failed create/save previously threw straight out of the form
 * action with nothing to show for it — apiWrite's error still reaches
 * the browser console, but the form itself just sits there looking like
 * the button did nothing (reported: "Save Changes is not clickable").
 * Catching here and returning the message via useActionState (see
 * pricing-rules-view.tsx's RuleEditForm/RuleCreateForm) makes a real
 * failure (a validation rule like maximum_fee < minimum_fee, a network
 * error, ...) visible instead of silent. */
async function runPricingRuleAction(run: () => Promise<unknown>): Promise<PricingRuleActionState> {
  try {
    await run();
  } catch (err) {
    return { error: err instanceof Error ? err.message : "Couldn't save this pricing rule. Try again." };
  }
  revalidatePath("/super-admin/pricing-rules");
  return { error: null };
}

export async function createMerchantPricingRuleAction(
  merchantId: string,
  _prevState: PricingRuleActionState | null,
  formData: FormData,
): Promise<PricingRuleActionState> {
  return runPricingRuleAction(() => createMerchantPricingRule(merchantId, pricingRuleInputFromFormData(formData)));
}

export async function createPlatformFallbackPricingRuleAction(
  _prevState: PricingRuleActionState | null,
  formData: FormData,
): Promise<PricingRuleActionState> {
  return runPricingRuleAction(() => createPlatformFallbackPricingRule(pricingRuleInputFromFormData(formData)));
}

export async function updatePricingRuleAction(
  ruleId: string,
  _prevState: PricingRuleActionState | null,
  formData: FormData,
): Promise<PricingRuleActionState> {
  return runPricingRuleAction(() => updatePricingRule(ruleId, pricingRuleInputFromFormData(formData)));
}

export async function deactivatePricingRuleAction(ruleId: string) {
  await deactivatePricingRule(ruleId);
  revalidatePath("/super-admin/pricing-rules");
}

// --- Collection pricing rules ---------------------------------------------------

function collectionPricingRuleInputFromFormData(formData: FormData): CollectionPricingRuleInput {
  const get = (key: string) => {
    const value = String(formData.get(key) ?? "").trim();
    return value ? value : undefined;
  };
  return {
    channel: get("channel") ?? null,
    percentage_fee: get("percentage_fee") ?? "0",
    // flat_fee/minimum_fee/maximum_fee have no input in RuleFields
    // anymore (collection-pricing-rules-view.tsx) — left as `undefined`
    // (not defaulted to "0"/null) so JSON.stringify drops them from the
    // request body entirely. On create, the backend's own Pydantic
    // defaults apply (flat_fee=0, min/max=null); on update, PATCH's
    // exclude_unset=True then leaves whatever a rule already has
    // untouched, rather than silently resetting it to 0/null on every
    // edit through this simplified form.
    flat_fee: get("flat_fee"),
    minimum_fee: get("minimum_fee"),
    maximum_fee: get("maximum_fee"),
    effective_from: get("effective_from") ?? null,
    effective_to: get("effective_to") ?? null,
    label: get("label") ?? null,
    notes: get("notes") ?? null,
  };
}

export type CollectionPricingRuleActionState = PricingRuleActionState;

async function runCollectionPricingRuleAction(run: () => Promise<unknown>): Promise<CollectionPricingRuleActionState> {
  try {
    await run();
  } catch (err) {
    return { error: err instanceof Error ? err.message : "Couldn't save this collection pricing rule. Try again." };
  }
  revalidatePath("/super-admin/pricing-rules");
  return { error: null };
}

export async function createMerchantCollectionPricingRuleAction(
  merchantId: string,
  _prevState: CollectionPricingRuleActionState | null,
  formData: FormData,
): Promise<CollectionPricingRuleActionState> {
  return runCollectionPricingRuleAction(() =>
    createMerchantCollectionPricingRule(merchantId, collectionPricingRuleInputFromFormData(formData)),
  );
}

export async function createPlatformFallbackCollectionPricingRuleAction(
  _prevState: CollectionPricingRuleActionState | null,
  formData: FormData,
): Promise<CollectionPricingRuleActionState> {
  return runCollectionPricingRuleAction(() =>
    createPlatformFallbackCollectionPricingRule(collectionPricingRuleInputFromFormData(formData)),
  );
}

export async function updateCollectionPricingRuleAction(
  ruleId: string,
  _prevState: CollectionPricingRuleActionState | null,
  formData: FormData,
): Promise<CollectionPricingRuleActionState> {
  return runCollectionPricingRuleAction(() =>
    updateCollectionPricingRule(ruleId, collectionPricingRuleInputFromFormData(formData)),
  );
}

export async function deactivateCollectionPricingRuleAction(ruleId: string) {
  await deactivateCollectionPricingRule(ruleId);
  revalidatePath("/super-admin/pricing-rules");
}

export async function activateCollectionPricingRuleAction(ruleId: string) {
  await activateCollectionPricingRule(ruleId);
  revalidatePath("/super-admin/pricing-rules");
}

// --- Notification settings (Super Admin editing a merchant's own) --------------

export type NotificationSettingsActionState = PricingRuleActionState;

export async function updateAdminMerchantNotificationSettingsAction(
  merchantId: string,
  _prevState: NotificationSettingsActionState | null,
  formData: FormData,
): Promise<NotificationSettingsActionState> {
  const get = (key: string) => {
    const value = String(formData.get(key) ?? "").trim();
    return value ? value : null;
  };
  try {
    await updateAdminMerchantNotificationSettings(merchantId, {
      primary_notification_email: get("primary_notification_email"),
      secondary_notification_email: get("secondary_notification_email"),
      collection_notifications_enabled: formData.get("collection_notifications_enabled") === "on",
    });
  } catch (err) {
    return { error: err instanceof Error ? err.message : "Couldn't save notification settings. Try again." };
  }
  revalidatePath(`/super-admin/merchants/${merchantId}`);
  return { error: null };
}
