"use server";

import { redirect } from "next/navigation";

import { clearMockSession } from "@/lib/auth/mock-session";

import { createClient } from "./server";

export async function logout() {
  try {
    const supabase = await createClient();
    await supabase.auth.signOut();
  } catch {
    // Supabase unreachable (mock-auth fallback environment) — the mock
    // session cookie cleared below is the actual source of truth there.
  }
  await clearMockSession();
  redirect("/login");
}
