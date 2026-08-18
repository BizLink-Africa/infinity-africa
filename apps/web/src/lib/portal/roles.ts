import { MERCHANT_ROLES, UserRole, USER_ROLE_LABELS } from "@infinity/shared";

export { MERCHANT_ROLES, UserRole, USER_ROLE_LABELS };

/**
 * Per-role portal page access, keyed by nav href. "Overview" is intentionally
 * included for every role even though it isn't listed per-role in the product
 * spec, since it's the landing page every merchant user hits after auth.
 * DEVELOPER's "integration settings" access maps to the existing Settings
 * page, since there is no separate integration-settings subsection.
 */
export const ROLE_ALLOWED_PATHS: Record<UserRole, string[] | "*"> = {
  [UserRole.SUPER_ADMIN]: "*",
  [UserRole.MERCHANT_ADMIN]: "*",
  [UserRole.MERCHANT_STAFF]: [
    "/merchant/overview",
    "/portal",
    "/portal/collections",
    "/merchant/payment-links",
    "/merchant/invoices",
    "/portal/customers",
    "/portal/transactions",
    "/portal/support",
    "/merchant/risk-monitoring",
    "/merchant/disputes",
    "/merchant/profile",
    "/merchant/settings",
  ],
  [UserRole.DEVELOPER]: [
    "/merchant/overview",
    "/portal",
    "/merchant/api-keys",
    "/merchant/developer-docs",
    "/portal/webhooks",
    "/merchant/profile",
    "/merchant/settings",
  ],
};

export function isPathAllowedForRole(role: UserRole, pathname: string): boolean {
  const allowed = ROLE_ALLOWED_PATHS[role];
  if (allowed === "*") return true;
  return allowed.some((href) =>
    href === "/portal" || href === "/merchant/overview" ? pathname === href : pathname.startsWith(href),
  );
}
