"use server";

import { revalidatePath } from "next/cache";

import { approveOnboardingSubmission, rejectOnboardingSubmission, requestMoreInfoOnboardingSubmission } from "./api";

function revalidateOnboarding(id: string) {
  revalidatePath("/super-admin/onboarding");
  revalidatePath(`/super-admin/onboarding/${id}`);
}

export async function approveOnboardingAction(id: string) {
  await approveOnboardingSubmission(id);
  revalidateOnboarding(id);
}

export async function rejectOnboardingAction(id: string, formData: FormData) {
  const note = String(formData.get("note") ?? "").trim() || null;
  await rejectOnboardingSubmission(id, note);
  revalidateOnboarding(id);
}

export async function requestInfoOnboardingAction(id: string, formData: FormData) {
  const note = String(formData.get("note") ?? "").trim() || null;
  await requestMoreInfoOnboardingSubmission(id, note);
  revalidateOnboarding(id);
}
