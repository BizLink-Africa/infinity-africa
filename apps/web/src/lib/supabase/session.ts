import "server-only";

import { createClient } from "./server";

/**
 * The current request's authenticated user, or null.
 *
 * Deliberately calls `auth.getUser()`, not `auth.getSession()`: getSession()
 * just reads the (possibly stale, unverified) session cookie, while
 * getUser() re-validates the JWT against Supabase Auth. Any server-side
 * authorization decision must use this, not the raw cookie contents.
 */
export async function getSession() {
  const supabase = await createClient();
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();

  if (error || !user) {
    return null;
  }

  return { user, supabase };
}

/**
 * The current request's Supabase access token, for attaching to
 * `Authorization: Bearer <token>` when calling apps/api from a Server
 * Component or Server Action. Reads the (already-cookie-validated) session
 * rather than re-running getUser(), since the caller already knows there's
 * a signed-in user by this point.
 */
export async function getAccessToken(): Promise<string | null> {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  return session?.access_token ?? null;
}
