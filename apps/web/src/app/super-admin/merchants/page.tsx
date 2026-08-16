import { AdminKpiCard } from "@/components/admin/kpi-card";
import { PageHeader } from "@/components/portal/page-header";
import { MerchantsTable } from "@/components/super-admin/merchants-table";
import { listAdminMerchants } from "@/lib/admin/live-api";

export const metadata = {
  title: "Merchants | Infinity Africa Super Admin",
};

export default async function SuperAdminMerchantsPage() {
  const merchants = await listAdminMerchants();

  const counts = {
    total: merchants.length,
    active: merchants.filter((m) => m.account_status === "active").length,
    pending: merchants.filter((m) => m.account_status === "pending").length,
    suspended: merchants.filter((m) => m.account_status === "suspended").length,
  };

  return (
    <div className="space-y-8">
      <PageHeader title="Merchant Management" description="Onboard, verify, and manage merchants on the Infinity Africa platform." />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
        <AdminKpiCard icon="store" label="Total Merchants" value={counts.total.toLocaleString()} />
        <AdminKpiCard icon="check_circle" label="Active" value={counts.active.toLocaleString()} />
        <AdminKpiCard icon="hourglass_empty" label="Pending Verification" value={counts.pending.toLocaleString()} />
        <AdminKpiCard icon="block" label="Suspended" value={counts.suspended.toLocaleString()} />
      </div>

      <MerchantsTable rows={merchants} />
    </div>
  );
}
