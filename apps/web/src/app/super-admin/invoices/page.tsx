import { AdminKpiCard } from "@/components/admin/kpi-card";
import { Card, tdClass, thClass } from "@/components/portal/card";
import { Icon } from "@/components/portal/icon";
import { PageHeader } from "@/components/portal/page-header";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatCurrency, formatDateTime } from "@/lib/format";
import { getAdminOverview, listAdminInvoices } from "@/lib/admin/live-api";
import { adminInvoiceBadge } from "@/lib/admin/status-tones";

export const metadata = {
  title: "Invoices | Infinity Africa Super Admin",
};

export default async function SuperAdminInvoicesPage() {
  const [invoices, overview] = await Promise.all([listAdminInvoices(), getAdminOverview()]);
  const paidToday = invoices.filter((i) => i.status === "PAID").length;
  const overdue = invoices.filter((i) => i.status === "OVERDUE").length;

  return (
    <div className="space-y-8">
      <PageHeader title="Invoice Management" description="Track every invoice issued across all merchants on the platform." />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
        <AdminKpiCard icon="receipt" label="Total Invoices" value={invoices.length.toLocaleString()} />
        <AdminKpiCard icon="check_circle" label="Paid Today" value={paidToday.toLocaleString()} />
        <AdminKpiCard icon="error" label="Overdue" value={overdue.toLocaleString()} />
        <AdminKpiCard icon="payments" label="Value Outstanding" value={overview ? formatCurrency(overview.outstanding_invoice_value, "TZS") : "—"} />
      </div>

      <Card>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <input className="sm:col-span-2 px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm" placeholder="Invoice number, merchant, or customer" />
          <select className="px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm">
            <option>All Statuses</option>
            <option>Draft</option>
            <option>Sent</option>
            <option>Paid</option>
            <option>Partially Paid</option>
            <option>Overdue</option>
            <option>Cancelled</option>
          </select>
          <input className="px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm" type="date" />
        </div>
      </Card>

      <Card padded={false}>
        <div className="p-5 pb-3">
          <h3 className="text-2xl font-semibold text-on-background">All Invoices</h3>
        </div>
        {invoices.length === 0 ? (
          <p className="p-6 text-sm text-on-surface-variant">No invoices have been issued yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left min-w-[900px]">
              <thead>
                <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                  <th className={thClass}>Invoice No</th>
                  <th className={thClass}>Merchant</th>
                  <th className={thClass}>Customer</th>
                  <th className={thClass}>Amount</th>
                  <th className={thClass}>Due Date</th>
                  <th className={thClass}>Status</th>
                  <th className={`${thClass} text-right`}>Actions</th>
                </tr>
              </thead>
              <tbody className="text-sm">
                {invoices.map((invoice) => (
                  <tr key={invoice.invoice_id} className={`border-t border-surface-container-highest ${invoice.status === "CANCELLED" ? "opacity-60" : ""}`}>
                    <td className={`${tdClass} font-mono text-on-background`}>{invoice.invoice_number}</td>
                    <td className={tdClass}>{invoice.merchant_name}</td>
                    <td className={tdClass}>{invoice.customer_name ?? invoice.customer_phone ?? "—"}</td>
                    <td className={`${tdClass} font-semibold text-on-background`}>{formatCurrency(invoice.total_amount, "TZS")}</td>
                    <td className={`${tdClass} text-xs ${invoice.status === "OVERDUE" ? "text-error font-semibold" : "text-on-surface-variant"}`}>
                      {formatDateTime(invoice.due_date)}
                    </td>
                    <td className={tdClass}>
                      <StatusBadge {...adminInvoiceBadge(invoice.status)} />
                    </td>
                    <td className={`${tdClass} text-right`}>
                      <button className="p-1.5 text-on-surface-variant hover:text-primary" title="View">
                        <Icon name="visibility" className="text-[18px]" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
