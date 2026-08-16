"use server";

import { redirect } from "next/navigation";

import { createClient } from "@/lib/supabase/server";
import { getOnboardingStatus } from "@/lib/onboarding/api";

import type { FormState } from "./form-state";
import { isEmail, validatePassword } from "./password";
import { createUser, findByEmail, verifyPassword } from "./mock-store";
import { setMockSession } from "./mock-session";
import { isKnownAuthRejection, isSupabaseConfigured } from "./supabase-status";

function describeSupabaseError(error: unknown): string {
  if (error && typeof error === "object" && "message" in error) {
    const message = String((error as { message?: unknown }).message ?? "");
    if (message) return message;
  }
  return "Something went wrong. Please try again.";
}

export async function createAccountAction(_prevState: FormState, formData: FormData): Promise<FormState> {
  const fullName = String(formData.get("fullName") ?? "").trim();
  const email = String(formData.get("email") ?? "").trim();
  const phone = String(formData.get("phone") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  const confirmPassword = String(formData.get("confirmPassword") ?? "");

  const errors: Record<string, string[]> = {};
  if (!fullName) errors.fullName = ["Full name is required."];
  if (!email) {
    errors.email = ["Email address is required."];
  } else if (!isEmail(email)) {
    errors.email = ["Enter a valid email address."];
  }
  if (!phone) errors.phone = ["Contact number is required."];

  const passwordErrors = validatePassword(password);
  if (passwordErrors.length > 0) errors.password = passwordErrors;

  if (!confirmPassword) {
    errors.confirmPassword = ["Please confirm your password."];
  } else if (confirmPassword !== password) {
    errors.confirmPassword = ["Passwords do not match."];
  }

  if (Object.keys(errors).length > 0) {
    return { errors, values: { fullName, email, phone } };
  }

  let userId: string | null = null;
  let usedSupabase = false;

  if (isSupabaseConfigured()) {
    try {
      const supabase = await createClient();
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: { data: { full_name: fullName, phone } },
      });
      if (error) throw error;
      usedSupabase = true;
      userId = data.user?.id ?? null;
    } catch (err) {
      if (isKnownAuthRejection(err)) {
        return { errors: {}, formError: describeSupabaseError(err), values: { fullName, email, phone } };
      }
      // Connectivity failure — fall through to the mock store below.
    }
  }

  if (!usedSupabase) {
    if (findByEmail(email)) {
      return {
        errors: {},
        formError: "An account with this email already exists.",
        values: { fullName, email, phone },
      };
    }
    const user = createUser({ fullName, email, phone, password });
    await setMockSession(user.id);
    userId = user.id;
  }

  if (!userId) {
    return {
      errors: {},
      formError: "Your account was created, but you'll need to confirm your email before continuing.",
      values: { fullName, email, phone },
    };
  }

  redirect("/onboarding");
}

export async function loginAction(_prevState: FormState, formData: FormData): Promise<FormState> {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");

  const errors: Record<string, string[]> = {};
  if (!email) errors.email = ["Email address is required."];
  if (!password) errors.password = ["Password is required."];

  if (Object.keys(errors).length > 0) {
    return { errors, values: { email } };
  }

  let userId: string | null = null;
  let usedSupabase = false;
  let isPlatformAdmin = false;
  let accessToken: string | null = null;

  if (isSupabaseConfigured()) {
    try {
      const supabase = await createClient();
      const { data, error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw error;
      usedSupabase = true;
      userId = data.user?.id ?? null;
      accessToken = data.session?.access_token ?? null;

      if (userId) {
        const { data: adminRow } = await supabase
          .from("platform_admins")
          .select("id")
          .eq("user_id", userId)
          .maybeSingle();
        isPlatformAdmin = Boolean(adminRow);
      }
    } catch (err) {
      if (isKnownAuthRejection(err)) {
        return { errors: {}, formError: "Incorrect email or password.", values: { email } };
      }
      // Connectivity failure — fall through to the mock store below.
    }
  }

  if (!usedSupabase) {
    const mockUser = findByEmail(email);
    if (!mockUser || !verifyPassword(mockUser, password)) {
      return { errors: {}, formError: "Incorrect email or password.", values: { email } };
    }
    await setMockSession(mockUser.id);
    userId = mockUser.id;
  }

  if (!userId) {
    return { errors: {}, formError: "Incorrect email or password.", values: { email } };
  }

  if (isPlatformAdmin) {
    redirect("/admin");
  }

  const onboarding = accessToken ? await getOnboardingStatus(accessToken) : null;
  redirect(onboarding?.next_path ?? "/onboarding");
}
