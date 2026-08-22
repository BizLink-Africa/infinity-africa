import { AdminKpiCard } from "@/components/admin/kpi-card";
import { Card } from "@/components/portal/card";
import { PageHeader } from "@/components/portal/page-header";
import { CollectionsTable } from "@/components/super-admin/collections-table";
import { formatCurrency } from "@/lib/format";
import { getAdminOverview, listAdminCollections } from "@/lib/admin/live-api";

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

      <CollectionsTable collections={collections} />
    </div>
  );
}
