"use client";

import { createClient } from "./client";

/**
 * Client-safe counterpart to lib/supabase/session.ts's getAccessToken() —
 * that file is marked "server-only" (Server Components/Actions only), so a
 * Client Component data-fetching function (e.g. most of lib/portal/api.ts's
 * "use client" page consumers) needs this instead. No getUser()
 * re-validation step here (unlike the server version) — apps/api verifies
 * the JWT itself on every request regardless, so a client-side re-check
 * before sending it would be redundant.
 */
export async function getAccessTokenClient(): Promise<string | null> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  return session?.access_token ?? null;
}
