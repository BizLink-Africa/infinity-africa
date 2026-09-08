"use server";

import { headers } from "next/headers";
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

/**
 * True when a Supabase Auth sign-in was rejected specifically because the
 * account's email is not confirmed yet — as opposed to a genuinely wrong
 * password. supabase-js reports this as `code: "email_not_confirmed"` (and
 * message "Email not confirmed") on a 400. Kept separate so login can show
 * an accurate "verify your email" message instead of the misleading
 * "Incorrect email or password."
 */
function isEmailNotConfirmed(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  const code = "code" in error ? String((error as { code?: unknown }).code ?? "") : "";
  const message = "message" in error ? String((error as { message?: unknown }).message ?? "") : "";
  return code === "email_not_confirmed" || /email not confirmed/i.test(message);
}

/**
 * Absolute URL Supabase should send the merchant back to after they click
 * the confirmation link in their email. Must be an allow-listed redirect
 * URL in the Supabase dashboard (Auth > URL Configuration) — see
 * docs/supabase-auth-settings.md. Prefers the explicit NEXT_PUBLIC_SITE_URL
 * (set to https://infinityafrica.net in production) and falls back to the
 * request's own forwarded host so local dev works with no extra config.
 */
async function authCallbackUrl(next: string): Promise<string> {
  let base = process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/+$/, "");
  if (!base) {
    const h = await headers();
    const host = h.get("x-forwarded-host") ?? h.get("host");
    const proto = h.get("x-forwarded-proto") ?? "https";
    base = host ? `${proto}://${host}` : "http://localhost:3000";
  }
  return `${base}/auth/callback?next=${encodeURIComponent(next)}`;
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
        options: {
          data: { full_name: fullName, phone },
          emailRedirectTo: await authCallbackUrl("/onboarding"),
        },
      });
      if (error) throw error;
      usedSupabase = true;
      userId = data.user?.id ?? null;

      // Supabase returns a populated `user` but a null `session` when the
      // project requires email confirmation — the account exists but is
      // not usable yet. This path previously still fell through to
      // `redirect("/onboarding")`, where the auth guard found no session
      // and bounced the merchant to /merchant/login: that is exactly the
      // "returned to login right after signup" bug. Stop here and tell
      // them to check their email instead.
      //
      // This branch also covers Supabase's account-enumeration protection
      // (an already-registered email returns an obfuscated user with a
      // null session and no error) — showing the same "check your email"
      // copy is the correct, non-revealing response there too.
      if (!data.session) {
        return {
          errors: {},
          values: { fullName, email, phone },
          awaitingEmailVerification: true,
          notice:
            "Account created. Check your email to verify your account, then continue your merchant verification.",
        };
      }
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
      values: { fullName, email, phone },
      awaitingEmailVerification: true,
      notice:
        "Account created. Check your email to verify your account, then continue your merchant verification.",
    };
  }

  // Reached only with a real session in hand (mock path, or a Supabase
  // project with email confirmation disabled). Send them straight to
  // document/business verification.
  redirect("/onboarding");
}

/**
 * Re-send the sign-up confirmation email. Always returns the same generic
 * confirmation regardless of whether the address actually needs
 * verification (or exists at all) — account-enumeration protection, same
 * as the forgot-password flow.
 */
export async function resendVerificationAction(_prevState: FormState, formData: FormData): Promise<FormState> {
  const email = String(formData.get("email") ?? "").trim();

  if (!email || !isEmail(email)) {
    return {
      errors: {},
      formError: "Enter the email address you signed up with to resend the verification link.",
      values: { email },
      awaitingEmailVerification: true,
    };
  }

  if (isSupabaseConfigured()) {
    try {
      const supabase = await createClient();
      await supabase.auth.resend({
        type: "signup",
        email,
        options: { emailRedirectTo: await authCallbackUrl("/onboarding") },
      });
    } catch {
      // Swallow — still show the generic confirmation below so a
      // connectivity blip or an unknown address is indistinguishable.
    }
  }

  return {
    errors: {},
    values: { email },
    awaitingEmailVerification: true,
    notice: "If that account still needs verification, we've sent a fresh link. Check your inbox and spam folder.",
  };
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
      if (isEmailNotConfirmed(err)) {
        return {
          errors: {},
          formError:
            "Please verify your email before logging in. Check your inbox for the verification link.",
          values: { email },
          awaitingEmailVerification: true,
        };
      }
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
