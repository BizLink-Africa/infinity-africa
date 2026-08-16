import { AdminKpiCard } from "@/components/admin/kpi-card";
import { Card, tdClass, thClass } from "@/components/portal/card";
import { PageHeader } from "@/components/portal/page-header";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatDateTime } from "@/lib/format";
import { listAdminWebhookEvents } from "@/lib/admin/live-api";
import { adminWebhookEventBadge } from "@/lib/admin/status-tones";

export const metadata = {
  title: "Webhooks | Infinity Africa Super Admin",
};

export default async function SuperAdminWebhooksPage() {
  const events = await listAdminWebhookEvents();
  const processed = events.filter((e) => e.status === "processed").length;
  const failed = events.filter((e) => e.status === "failed").length;
  const received = events.filter((e) => e.status === "received").length;

  return (
    <div className="space-y-8">
      <PageHeader title="Webhooks" description="Inbound payment provider callbacks received by the platform." />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        <AdminKpiCard icon="check_circle" label="Processed" value={processed.toLocaleString()} />
        <AdminKpiCard icon="hourglass_empty" label="Received (Unprocessed)" value={received.toLocaleString()} />
        <AdminKpiCard icon="error" label="Failed" value={failed.toLocaleString()} />
      </div>

      <Card padded={false}>
        <div className="p-5 pb-3">
          <h3 className="text-2xl font-semibold text-on-background">Provider Callback Log</h3>
        </div>
        {events.length === 0 ? (
          <p className="p-6 text-sm text-on-surface-variant">No provider callbacks have been received yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left min-w-[820px]">
              <thead>
                <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                  <th className={thClass}>Provider</th>
                  <th className={thClass}>Event Type</th>
                  <th className={thClass}>Reference</th>
                  <th className={thClass}>Received</th>
                  <th className={thClass}>Processed</th>
                  <th className={thClass}>Status</th>
                </tr>
              </thead>
              <tbody className="text-sm">
                {events.map((event) => (
                  <tr key={event.webhook_event_id} className="border-t border-surface-container-highest">
                    <td className={`${tdClass} font-medium text-on-background capitalize`}>{event.provider}</td>
                    <td className={`${tdClass} font-mono text-xs`}>{event.event_type}</td>
                    <td className={`${tdClass} font-mono text-xs text-on-surface-variant`}>{event.reference}</td>
                    <td className={`${tdClass} text-on-surface-variant text-xs`}>{formatDateTime(event.created_at)}</td>
                    <td className={`${tdClass} text-on-surface-variant text-xs`}>{event.processed_at ? formatDateTime(event.processed_at) : "—"}</td>
                    <td className={tdClass}>
                      <StatusBadge {...adminWebhookEventBadge(event.status)} />
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
