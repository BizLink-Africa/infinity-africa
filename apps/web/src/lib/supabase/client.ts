"use client";

import { createBrowserClient } from "@supabase/ssr";

/**
 * Supabase client for use in Client Components. Uses the public anon key
 * only — every query still goes through RLS as the signed-in user (or as
 * `anon`), so this is safe to ship to the browser. Never import the
 * service_role key here or anywhere under apps/web.
 */
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}
