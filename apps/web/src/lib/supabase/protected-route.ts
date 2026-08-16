import "server-only";

import { redirect } from "next/navigation";
import type { UserRole } from "@infinity/shared";

import { getSession } from "./session";

/**
 * Require an authenticated user for a Server Component route (layout or
 * page). Redirects to /login if there's no valid session.
 */
export async function requireUser(redirectTo = "/login") {
  const session = await getSession();

  if (!session) {
    redirect(redirectTo);
  }

  return session;
}

/**
 * Require the current user to be a platform super admin (platform_admins
 * membership — never user_metadata/app_metadata). Redirects non-admins to
 * the merchant portal rather than exposing a 403 page.
 */
export async function requireSuperAdmin() {
  const { user, supabase } = await requireUser("/admin-login");

  const { data } = await supabase
    .from("platform_admins")
    .select("id")
    .eq("user_id", user.id)
    .maybeSingle();

  if (!data) {
    redirect("/portal");
  }

  return user;
}

/**
 * Require the current user to be an active member of the given merchant,
 * looked up from merchant_users (never user_metadata/app_metadata).
 * Returns their role so the caller can further gate by it if needed.
 */
export async function requireMerchantAccess(merchantId: string) {
  const { user, supabase } = await requireUser();

  const { data } = await supabase
    .from("merchant_users")
    .select("role")
    .eq("merchant_id", merchantId)
    .eq("user_id", user.id)
    .eq("status", "active")
    .maybeSingle();

  if (!data) {
    redirect("/portal");
  }

  return { user, role: data.role as UserRole };
}
