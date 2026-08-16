import { Card, tdClass, thClass } from "@/components/portal/card";
import { Icon } from "@/components/portal/icon";
import { PageHeader } from "@/components/portal/page-header";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatCurrency, formatDateTime } from "@/lib/format";
import { listAdminTransactions } from "@/lib/admin/live-api";
import type { BadgeProps } from "@/lib/portal/status-tones";
import { transactionStatusBadge } from "@/lib/portal/status-tones";
import type { AdminTransactionRow } from "@/lib/admin/types";

export const metadata = {
  title: "Transactions | Infinity Africa Super Admin",
};

function typeBadge(type: AdminTransactionRow["type"]): BadgeProps {
  switch (type) {
    case "collection":
      return { label: "Collection", tone: "positive", dot: true };
    case "disbursement":
      return { label: "Withdrawal", tone: "info" };
    case "fee":
      return { label: "Fee", tone: "neutral" };
  }
}

export default async function SuperAdminTransactionsPage() {
  const transactions = await listAdminTransactions();

  return (
    <div className="space-y-8">
      <PageHeader
        title="Transactions"
        description="The full platform ledger — every collection, withdrawal, and fee across all merchants."
        action={
          <button className="flex items-center gap-2 bg-surface border border-outline-variant text-on-surface px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-surface-container-low transition-colors">
            <Icon name="download" className="text-[18px]" />
            Export CSV
          </button>
        }
      />

      <Card>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <input className="px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm" placeholder="Search merchant..." />
          <select className="px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm">
            <option>All Types</option>
            <option>Collection</option>
            <option>Withdrawal</option>
            <option>Fee</option>
          </select>
          <select className="px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm">
            <option>All Statuses</option>
            <option>Successful</option>
            <option>Pending</option>
            <option>Failed</option>
          </select>
          <input className="px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm" type="date" />
        </div>
      </Card>

      <Card padded={false}>
        <div className="p-5 pb-3">
          <h3 className="text-2xl font-semibold text-on-background">All Transactions</h3>
        </div>
        {transactions.length === 0 ? (
          <p className="p-6 text-sm text-on-surface-variant">No transactions have been recorded yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left min-w-[900px]">
              <thead>
                <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                  <th className={thClass}>Date</th>
                  <th className={thClass}>Merchant</th>
                  <th className={thClass}>Type</th>
                  <th className={thClass}>Reference</th>
                  <th className={thClass}>Method</th>
                  <th className={thClass}>Amount</th>
                  <th className={thClass}>Status</th>
                </tr>
              </thead>
              <tbody className="text-sm">
                {transactions.map((transaction) => {
                  const positive = transaction.type === "collection";
                  return (
                    <tr key={transaction.transaction_id} className="border-t border-surface-container-highest">
                      <td className={`${tdClass} text-on-surface-variant text-xs`}>{formatDateTime(transaction.created_at)}</td>
                      <td className={`${tdClass} font-medium text-on-background`}>{transaction.merchant_name}</td>
                      <td className={tdClass}>
                        <StatusBadge {...typeBadge(transaction.type)} />
                      </td>
                      <td className={`${tdClass} font-mono text-sm text-on-background`}>{transaction.reference}</td>
                      <td className={`${tdClass} text-on-surface-variant`}>{transaction.method}</td>
                      <td className={`${tdClass} font-semibold ${positive ? "text-primary" : "text-on-background"}`}>
                        {positive ? "+" : "-"} {formatCurrency(transaction.gross_amount, transaction.currency)}
                      </td>
                      <td className={tdClass}>
                        <StatusBadge {...transactionStatusBadge(transaction.status)} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
