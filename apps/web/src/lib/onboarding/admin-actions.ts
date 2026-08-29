"use server";

import { revalidatePath } from "next/cache";

import { approveOnboardingSubmission, rejectOnboardingSubmission, requestMoreInfoOnboardingSubmission } from "./api";

function revalidateOnboarding(id: string) {
  revalidatePath("/super-admin/onboarding");
  revalidatePath(`/super-admin/onboarding/${id}`);
}

export async function approveOnboardingAction(id: string): Promise<{ welcomeEmailWarning: string | null }> {
  const result = await approveOnboardingSubmission(id);
  revalidateOnboarding(id);
  return { welcomeEmailWarning: result.welcome_email_warning ?? null };
}

export async function rejectOnboardingAction(id: string, note: string | null) {
  await rejectOnboardingSubmission(id, note);
  revalidateOnboarding(id);
}

export async function requestInfoOnboardingAction(id: string, note: string | null) {
  await requestMoreInfoOnboardingSubmission(id, note);
  revalidateOnboarding(id);
}
