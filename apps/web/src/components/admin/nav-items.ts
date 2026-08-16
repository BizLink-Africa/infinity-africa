export interface AdminNavItem {
  label: string;
  href: string;
  icon: string;
}

export const ADMIN_NAV_ITEMS: AdminNavItem[] = [
  { label: "Dashboard", href: "/super-admin", icon: "dashboard" },
  { label: "Merchants", href: "/super-admin/merchants", icon: "storefront" },
  { label: "Merchant Users", href: "/super-admin/merchant-users", icon: "manage_accounts" },
  { label: "Onboarding Requests", href: "/super-admin/onboarding", icon: "assignment_ind" },
  { label: "Collections", href: "/super-admin/collections", icon: "payments" },
  { label: "Payment Links", href: "/super-admin/payment-links", icon: "link" },
  { label: "Invoices", href: "/super-admin/invoices", icon: "receipt" },
  { label: "Customers", href: "/admin/customers", icon: "group" },
  { label: "Withdrawals", href: "/super-admin/withdrawals", icon: "receipt_long" },
  { label: "Transactions", href: "/super-admin/transactions", icon: "list_alt" },
  { label: "Risk Monitoring", href: "/super-admin/risk-monitoring", icon: "gpp_maybe" },
  { label: "Document Requests", href: "/super-admin/document-requests", icon: "folder_shared" },
  { label: "Disputes", href: "/super-admin/disputes", icon: "gavel" },
  { label: "Pricing Rules", href: "/admin/pricing-rules", icon: "sell" },
  { label: "API Keys", href: "/admin/api-keys", icon: "api" },
  { label: "Webhooks", href: "/super-admin/webhooks", icon: "webhook" },
  { label: "Reconciliation Center", href: "/admin/reconciliation-center", icon: "account_balance" },
  { label: "Settlement Accounts", href: "/admin/settlement-accounts", icon: "account_balance_wallet" },
  { label: "Compliance/KYC", href: "/admin/compliance-kyc", icon: "verified_user" },
  { label: "Provider Status", href: "/admin/provider-status", icon: "dns" },
  { label: "Audit Logs", href: "/super-admin/audit-logs", icon: "history" },
  { label: "Support Tickets", href: "/admin/support-tickets", icon: "support_agent" },
  { label: "Settings", href: "/admin/settings", icon: "settings" },
];
