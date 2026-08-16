import "server-only";

import { cookies } from "next/headers";

/**
 * Session cookie for the mock-auth fallback path. Holds the mock user id
 * directly (unsigned) — trivially forgeable client-side, which is fine for
 * a local fallback demo path but must never be treated as equivalent to a
 * real Supabase session for anything security-sensitive.
 */
const COOKIE_NAME = "infinity_mock_session";

export async function setMockSession(userId: string) {
  const cookieStore = await cookies();
  cookieStore.set(COOKIE_NAME, userId, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
}

export async function clearMockSession() {
  const cookieStore = await cookies();
  cookieStore.delete(COOKIE_NAME);
}

export async function getMockSession(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get(COOKIE_NAME)?.value ?? null;
}
