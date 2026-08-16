import { AdminKpiCard } from "@/components/admin/kpi-card";
import { Card, tdClass, thClass } from "@/components/portal/card";
import { PageHeader } from "@/components/portal/page-header";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatCurrency, formatDateTime } from "@/lib/format";
import { getAdminOverview, listAdminCollections } from "@/lib/admin/live-api";
import { adminCollectionBadge } from "@/lib/admin/status-tones";

export const metadata = {
  title: "Collections | Infinity Africa Super Admin",
};

export default async function SuperAdminCollectionsPage() {
  const [collections, overview] = await Promise.all([listAdminCollections(), getAdminOverview()]);
  const successful = collections.filter((c) => c.status === "successful").length;
  const pending = collections.filter((c) => c.status === "pending" || c.status === "processing").length;
  const failed = collections.filter((c) => c.status === "failed").length;

  return (
    <div className="space-y-8">
      <PageHeader title="Collections" description="Platform-wide mobile money collections across every merchant." />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
        <AdminKpiCard icon="payments" label="Collections Today" value={overview ? formatCurrency(overview.collections_today, "TZS") : "—"} />
        <AdminKpiCard icon="check_circle" label="Successful" value={successful.toLocaleString()} />
        <AdminKpiCard icon="hourglass_empty" label="Pending" value={pending.toLocaleString()} />
        <AdminKpiCard icon="error" label="Failed" value={failed.toLocaleString()} />
      </div>

      <Card>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <input className="px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm" placeholder="Search merchant..." />
          <select className="px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm">
            <option>All Methods</option>
            <option>USSD Push</option>
            <option>STK Push</option>
            <option>Selcom Pesa Push</option>
            <option>Dynamic QR</option>
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
          <h3 className="text-2xl font-semibold text-on-background">All Collections</h3>
        </div>
        {collections.length === 0 ? (
          <p className="p-6 text-sm text-on-surface-variant">No collections have been recorded yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left min-w-[760px]">
              <thead>
                <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                  <th className={thClass}>Merchant</th>
                  <th className={thClass}>Phone</th>
                  <th className={thClass}>Method</th>
                  <th className={thClass}>Amount</th>
                  <th className={thClass}>Status</th>
                  <th className={thClass}>Date</th>
                </tr>
              </thead>
              <tbody className="text-sm">
                {collections.map((row) => (
                  <tr key={row.collection_id} className="border-t border-surface-container-highest">
                    <td className={`${tdClass} text-on-background font-medium`}>{row.merchant_name}</td>
                    <td className={tdClass}>{row.phone ?? "—"}</td>
                    <td className={`${tdClass} text-on-surface-variant`}>{row.method}</td>
                    <td className={`${tdClass} font-semibold text-on-background`}>{formatCurrency(row.amount, row.currency)}</td>
                    <td className={tdClass}>
                      <StatusBadge {...adminCollectionBadge(row.status)} />
                    </td>
                    <td className={`${tdClass} text-on-surface-variant text-xs`}>{formatDateTime(row.created_at)}</td>
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
