import "server-only";

import type { DocumentType } from "@infinity/shared";

import { getAccessToken } from "@/lib/supabase/session";

import type {
  OnboardingDocument,
  OnboardingMerchantAccountInput,
  OnboardingMerchantAccountResult,
  OnboardingStatus,
  OnboardingSubmission,
} from "./types";

/**
 * Data-access boundary for the real /v1/onboarding/* and
 * /v1/admin/onboarding/* endpoints — replaces lib/onboarding/store.ts's
 * mock, same shape as lib/portal/api.ts but server-only: every caller here
 * is a Server Component or Server Action (submitOnboardingAction, the
 * onboarding/status pages, the super-admin onboarding review pages), so
 * this can safely use the cookie-based getAccessToken() with no
 * Turbopack client/server bundling conflict.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL;

interface ApiEnvelope<T> {
  success: boolean;
  data?: T;
  // `details` is only ever populated on a 422 (app/core/errors.py's
  // RequestValidationError handler) — the raw list of Pydantic field
  // errors. `message` alone is always the generic "Invalid request" for
  // that case, which tells the merchant nothing about what to fix — see
  // firstValidationMessage below.
  error?: { code: string; message: string; details?: unknown };
}

export class OnboardingApiError extends Error {
  code?: string;
  constructor(message: string, code?: string) {
    super(message);
    this.code = code;
  }
}

// Pulls the actual reason out of a 422's field-level error list, so the
// merchant sees e.g. "must be a valid Tanzanian phone number..." instead
// of a bare "Invalid request" with no indication of what to fix.
function firstValidationMessage(details: unknown): string | null {
  if (!Array.isArray(details) || details.length === 0) return null;
  const first = details[0];
  if (!first || typeof first !== "object" || typeof (first as { msg?: unknown }).msg !== "string") return null;
  // Pydantic v2 prefixes a field_validator's raised ValueError with
  // "Value error, " — strip it, it's an implementation detail no
  // merchant should see.
  return (first as { msg: string }).msg.replace(/^Value error,\s*/, "");
}

/** `accessToken` is only ever passed explicitly right after a fresh
 * signInWithPassword/signUp call, where reading it back via getAccessToken()
 * would race the cookies the same request just wrote. Every other caller
 * omits it and relies on the already-established session cookie. */
async function authHeader(accessToken?: string): Promise<Record<string, string>> {
  const token = accessToken ?? (await getAccessToken());
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function parseEnvelope<T>(res: Response): Promise<T> {
  const body: ApiEnvelope<T> = await res.json();
  if (!res.ok || !body.success || body.data === undefined) {
    const message = firstValidationMessage(body.error?.details) ?? body.error?.message ?? "Request failed";
    throw new OnboardingApiError(message, body.error?.code);
  }
  return body.data;
}

// --- Self-service (merchant) -------------------------------------------

/** Returns null on no session, network failure, or a non-2xx response —
 * every caller treats "status unknown" the same as "start onboarding". */
export async function getOnboardingStatus(accessToken?: string): Promise<OnboardingStatus | null> {
  try {
    const res = await fetch(`${API_BASE}/v1/onboarding/status`, {
      headers: await authHeader(accessToken),
      cache: "no-store",
    });
    if (!res.ok) return null;
    return await parseEnvelope<OnboardingStatus>(res);
  } catch {
    return null;
  }
}

export async function submitOnboardingAccount(
  input: OnboardingMerchantAccountInput,
): Promise<OnboardingMerchantAccountResult> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/v1/onboarding/merchant-account`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(await authHeader()) },
      body: JSON.stringify(input),
    });
  } catch {
    throw new OnboardingApiError("Couldn't reach Infinity Africa. Check your connection and try again.");
  }
  return parseEnvelope<OnboardingMerchantAccountResult>(res);
}

export async function uploadOnboardingDocument(documentType: DocumentType, file: File): Promise<OnboardingDocument> {
  const formData = new FormData();
  formData.append("document_type", documentType);
  formData.append("file", file);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/v1/onboarding/documents`, {
      method: "POST",
      headers: await authHeader(),
      body: formData,
    });
  } catch {
    throw new OnboardingApiError("Couldn't reach Infinity Africa. Check your connection and try again.");
  }
  return parseEnvelope<OnboardingDocument>(res);
}

// --- Super-admin review --------------------------------------------------

export async function listOnboardingSubmissions(): Promise<OnboardingSubmission[]> {
  try {
    const res = await fetch(`${API_BASE}/v1/admin/onboarding`, {
      headers: await authHeader(),
      cache: "no-store",
    });
    if (!res.ok) return [];
    return await parseEnvelope<OnboardingSubmission[]>(res);
  } catch {
    return [];
  }
}

export async function getOnboardingSubmission(id: string): Promise<OnboardingSubmission | null> {
  try {
    const res = await fetch(`${API_BASE}/v1/admin/onboarding/${id}`, {
      headers: await authHeader(),
      cache: "no-store",
    });
    if (!res.ok) return null;
    return await parseEnvelope<OnboardingSubmission>(res);
  } catch {
    return null;
  }
}

export async function approveOnboardingSubmission(id: string): Promise<OnboardingSubmission> {
  const res = await fetch(`${API_BASE}/v1/admin/onboarding/${id}/approve`, {
    method: "POST",
    headers: await authHeader(),
  });
  return parseEnvelope<OnboardingSubmission>(res);
}

export async function rejectOnboardingSubmission(id: string, note: string | null): Promise<OnboardingSubmission> {
  const res = await fetch(`${API_BASE}/v1/admin/onboarding/${id}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeader()) },
    body: JSON.stringify({ review_note: note }),
  });
  return parseEnvelope<OnboardingSubmission>(res);
}

export async function requestMoreInfoOnboardingSubmission(id: string, note: string | null): Promise<OnboardingSubmission> {
  const res = await fetch(`${API_BASE}/v1/admin/onboarding/${id}/request-more-info`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeader()) },
    body: JSON.stringify({ review_note: note }),
  });
  return parseEnvelope<OnboardingSubmission>(res);
}
