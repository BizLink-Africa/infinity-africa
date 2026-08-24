export interface AdminNavItem {
  label: string;
  href: string;
  icon: string;
}

// The following once linked here but were removed 2026-08-25: Customers,
// Reconciliation Center, Settlement Accounts, Compliance/KYC, Provider
// Status, Support Tickets — all backed by /admin/* pages that are entirely
// hardcoded mock data (see lib/admin/api.ts's own docstring), never wired to
// a real backend. Rather than show fabricated numbers (e.g. a "1,158
// Verified Merchants" count on a platform with 2 real merchants), they're
// unlinked until each one has a real implementation behind it — API Keys
// was the first to get one (GET/PATCH /v1/admin/api-keys*, real data, added
// back below). The other pages' files still exist, just no longer reachable
// from here.
export const ADMIN_NAV_ITEMS: AdminNavItem[] = [
  { label: "Dashboard", href: "/super-admin", icon: "dashboard" },
  { label: "Merchants", href: "/super-admin/merchants", icon: "storefront" },
  { label: "Merchant Users", href: "/super-admin/merchant-users", icon: "manage_accounts" },
  { label: "Onboarding Requests", href: "/super-admin/onboarding", icon: "assignment_ind" },
  { label: "Collections", href: "/super-admin/collections", icon: "payments" },
  { label: "Payment Links", href: "/super-admin/payment-links", icon: "link" },
  { label: "Invoices", href: "/super-admin/invoices", icon: "receipt" },
  { label: "Withdrawals", href: "/super-admin/withdrawals", icon: "receipt_long" },
  { label: "Transactions", href: "/super-admin/transactions", icon: "list_alt" },
  { label: "Risk Monitoring", href: "/super-admin/risk-monitoring", icon: "gpp_maybe" },
  { label: "Document Requests", href: "/super-admin/document-requests", icon: "folder_shared" },
  { label: "Disputes", href: "/super-admin/disputes", icon: "gavel" },
  { label: "Pricing Rules", href: "/super-admin/pricing-rules", icon: "sell" },
  { label: "API Keys", href: "/super-admin/api-keys", icon: "api" },
  { label: "Webhooks", href: "/super-admin/webhooks", icon: "webhook" },
  { label: "Audit Logs", href: "/super-admin/audit-logs", icon: "history" },
  { label: "Settings", href: "/admin/settings", icon: "settings" },
];
