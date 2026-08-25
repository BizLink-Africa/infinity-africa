import { Card, tdClass, thClass } from "@/components/portal/card";
import { formatCurrency, formatDateTime } from "@/lib/format";
import type { AdminCustomerPlatformRow } from "@/lib/admin/types";

function initials(name: string): string {
  return name.charAt(0).toUpperCase();
}

export function CustomersTable({ rows }: { rows: AdminCustomerPlatformRow[] }) {
  return (
    <Card padded={false}>
      <div className="p-5 pb-3">
        <h3 className="text-2xl font-semibold text-on-background">All Customers</h3>
      </div>
      {rows.length === 0 ? (
        <p className="p-6 text-sm text-on-surface-variant">No customer activity has been recorded yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left min-w-[820px]">
            <thead>
              <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                <th className={thClass}>Customer</th>
                <th className={thClass}>Phone</th>
                <th className={thClass}>Merchant</th>
                <th className={thClass}>Transactions</th>
                <th className={thClass}>Total Spent</th>
                <th className={thClass}>Last Transaction</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {rows.map((row) => (
                <tr key={row.id} className="border-t border-surface-container-highest">
                  <td className={tdClass}>
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-primary-container/15 text-primary flex items-center justify-center font-bold text-xs shrink-0">
                        {initials(row.full_name ?? row.phone)}
                      </div>
                      <span className="font-medium text-on-background">{row.full_name ?? "—"}</span>
                    </div>
                  </td>
                  <td className={`${tdClass} font-mono text-xs text-on-surface-variant`}>{row.phone}</td>
                  <td className={tdClass}>
                    <div className="text-on-surface-variant">{row.merchant_name}</div>
                    {row.merchant_code && <div className="font-mono text-xs text-on-surface-variant">{row.merchant_code}</div>}
                  </td>
                  <td className={`${tdClass} text-on-surface-variant`}>{row.transaction_count.toLocaleString()}</td>
                  <td className={`${tdClass} font-semibold text-on-background`}>
                    {formatCurrency(row.total_spent, row.currency)}
                  </td>
                  <td className={`${tdClass} text-on-surface-variant text-xs`}>
                    {row.last_transaction_at ? formatDateTime(row.last_transaction_at) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
