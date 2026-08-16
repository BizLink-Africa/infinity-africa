import { Card, tdClass, thClass } from "@/components/portal/card";
import { Icon } from "@/components/portal/icon";
import { KpiCard } from "@/components/portal/kpi-card";
import { PageHeader } from "@/components/portal/page-header";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatCurrency, formatDateTime } from "@/lib/format";
import { listWalletAccounts, listWalletLedger } from "@/lib/portal/api";

export const metadata = {
  title: "Wallet | Infinity Africa Merchant Portal",
};

export default async function WalletPage() {
  const [accounts, ledger] = await Promise.all([listWalletAccounts(), listWalletLedger()]);

  return (
    <div className="space-y-8">
      <PageHeader title="Wallet" description="Your balances and linked withdrawal accounts." />

      <section className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <KpiCard icon="account_balance_wallet" label="Available Balance" value={formatCurrency("4820000", "TZS")} caption="Ready to withdraw" />
        <KpiCard icon="hourglass_empty" label="Pending Clearance" value={formatCurrency("610000", "TZS")} caption="Settles within 1-2 business days" />
        <KpiCard icon="lock" label="Reserved Funds" value={formatCurrency("250000", "TZS")} caption="Held for chargebacks" />
      </section>

      <Card>
        <h3 className="text-2xl font-semibold text-on-background mb-4">Linked Withdrawal Accounts</h3>
        <div className="divide-y divide-surface-container-highest">
          {accounts.map((account) => (
            <div key={account.id} className="flex items-center justify-between py-3.5 first:pt-0 last:pb-0">
              <div className="flex items-center gap-3">
                <div className="w-11 h-11 rounded-lg bg-primary-container/10 text-primary flex items-center justify-center shrink-0">
                  <Icon name={account.method === "SELCOM_PESA" ? "bolt" : account.method === "MOBILE_MONEY" ? "phone_iphone" : "account_balance"} />
                </div>
                <div>
                  <div className="font-medium text-on-background text-sm">{account.label}</div>
                  <div className="text-xs text-on-surface-variant">{account.masked_identifier}</div>
                </div>
              </div>
              {account.is_default ? (
                <StatusBadge label="Default" tone="positive" dot />
              ) : (
                <button className="text-xs font-semibold text-error hover:underline">Remove</button>
              )}
            </div>
          ))}
        </div>
        <button className="mt-4 w-full sm:w-auto border border-outline-variant text-on-surface text-sm font-medium py-2.5 px-5 rounded-lg hover:bg-surface-container-low transition-colors">
          + Add Account
        </button>
      </Card>

      <Card padded={false}>
        <div className="p-5 pb-3">
          <h3 className="text-2xl font-semibold text-on-background">Wallet Ledger</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left min-w-[760px]">
            <thead>
              <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                <th className={thClass}>Date</th>
                <th className={thClass}>Description</th>
                <th className={thClass}>Type</th>
                <th className={thClass}>Amount</th>
                <th className={thClass}>Balance After</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {ledger.map((entry) => (
                <tr key={entry.id} className="border-t border-surface-container-highest">
                  <td className={`${tdClass} text-on-surface-variant text-xs`}>{formatDateTime(entry.date)}</td>
                  <td className={tdClass}>{entry.description}</td>
                  <td className={tdClass}>
                    {entry.direction === "credit" ? (
                      <StatusBadge label="Credit" tone="positive" dot />
                    ) : (
                      <StatusBadge label="Debit" tone="neutral" />
                    )}
                  </td>
                  <td className={`${tdClass} font-semibold ${entry.direction === "credit" ? "text-primary" : "text-on-background"}`}>
                    {entry.direction === "credit" ? "+" : "-"}
                    {formatCurrency(entry.amount, "TZS")}
                  </td>
                  <td className={`${tdClass} font-semibold`}>{formatCurrency(entry.balance_after, "TZS")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
