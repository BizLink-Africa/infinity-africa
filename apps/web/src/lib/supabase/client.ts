"use client";

import { createBrowserClient } from "@supabase/ssr";

/**
 * Supabase client for use in Client Components. Uses the public anon key
 * only — every query still goes through RLS as the signed-in user (or as
 * `anon`), so this is safe to ship to the browser. Never import the
 * service_role key here or anywhere under apps/web.
 *
 * detectSessionInUrl is explicitly off: createBrowserClient hardcodes
 * flowType: "pkce" (unconditionally, it can't be overridden — see
 * node_modules/@supabase/ssr's own createBrowserClient), but every
 * recovery/invite link this app generates (auth.admin.generate_link(),
 * server-side, in app/services/email.py) is implicit-style, never PKCE.
 * With auto-detection on, auth-js's own session-from-URL logic rejects
 * that mismatch on page load — silently, before any of this app's code
 * runs — which is why reset/invite links appeared to fail instantly, on
 * every link, regardless of real expiry (confirmed live 2026-08-29).
 * apps/web/src/lib/auth/recovery-link.ts is what actually establishes the
 * session now, deliberately and exactly once, from the reset-password and
 * invite-accept pages themselves. No other page in this app depends on
 * automatic session-from-URL detection (no OAuth/magic-link sign-in
 * exists here) — confirmed before disabling this globally.
 */
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    { auth: { detectSessionInUrl: false } },
  );
}
