export interface PortalNavItem {
  label: string;
  href: string;
  icon: string;
}

export const PORTAL_NAV_ITEMS: PortalNavItem[] = [
  { label: "Overview", href: "/merchant/overview", icon: "dashboard" },
  { label: "Wallet", href: "/portal/wallet", icon: "account_balance" },
  { label: "Collections", href: "/portal/collections", icon: "payments" },
  { label: "Payment Links", href: "/merchant/payment-links", icon: "link" },
  { label: "Withdrawals", href: "/merchant/withdrawals", icon: "account_balance_wallet" },
  { label: "Transactions", href: "/portal/transactions", icon: "receipt_long" },
  { label: "Customers", href: "/portal/customers", icon: "group" },
  { label: "Invoices", href: "/merchant/invoices", icon: "description" },
  { label: "Risk Monitoring", href: "/merchant/risk-monitoring", icon: "gpp_maybe" },
  { label: "Disputes", href: "/merchant/disputes", icon: "gavel" },
  { label: "Team", href: "/merchant/users", icon: "group_add" },
  { label: "Pricing", href: "/portal/pricing", icon: "sell" },
  { label: "API Keys", href: "/merchant/api-keys", icon: "api" },
  { label: "Developer Docs", href: "/merchant/developer-docs", icon: "menu_book" },
  { label: "Webhooks", href: "/portal/webhooks", icon: "webhook" },
  { label: "IP Allowlist", href: "/portal/ip-allowlist", icon: "shield_lock" },
  { label: "API Logs", href: "/portal/api-logs", icon: "history_toggle_off" },
  { label: "Reports", href: "/portal/reports", icon: "bar_chart" },
  { label: "Settings", href: "/merchant/settings", icon: "settings" },
  { label: "Support", href: "/portal/support", icon: "help" },
];
