import { Card, tdClass, thClass } from "@/components/portal/card";
import { Icon } from "@/components/portal/icon";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatDateTime } from "@/lib/format";
import { revokeAdminApiKeyAction } from "@/lib/admin/live-actions";
import type { AdminApiKeyPlatformRow } from "@/lib/admin/types";

export function ApiKeysTable({ rows }: { rows: AdminApiKeyPlatformRow[] }) {
  return (
    <Card padded={false}>
      <div className="p-5 pb-3">
        <h3 className="text-2xl font-semibold text-on-background">All API Keys</h3>
      </div>
      {rows.length === 0 ? (
        <p className="p-6 text-sm text-on-surface-variant">No API keys have been issued yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left min-w-[900px]">
            <thead>
              <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                <th className={thClass}>Merchant</th>
                <th className={thClass}>Name</th>
                <th className={thClass}>Key</th>
                <th className={thClass}>Environment</th>
                <th className={thClass}>IP Whitelist</th>
                <th className={thClass}>Status</th>
                <th className={thClass}>Last Used</th>
                <th className={thClass}>Created</th>
                <th className={`${thClass} text-right`}>Actions</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {rows.map((row) => (
                <tr key={row.id} className="border-t border-surface-container-highest">
                  <td className={tdClass}>
                    <div className="text-on-background font-medium">{row.merchant_name}</div>
                    {row.merchant_code && (
                      <div className="font-mono text-xs text-on-surface-variant">{row.merchant_code}</div>
                    )}
                  </td>
                  <td className={tdClass}>{row.name}</td>
                  <td className={`${tdClass} text-on-surface-variant text-xs font-mono`}>
                    {row.key_prefix}••••{row.key_last4 ?? ""}
                  </td>
                  <td className={tdClass}>
                    <StatusBadge
                      label={row.environment === "live" ? "Live" : "Sandbox"}
                      tone={row.environment === "live" ? "positive" : "neutral"}
                    />
                  </td>
                  <td className={tdClass}>
                    <StatusBadge
                      label={row.ip_whitelist_enabled ? "Enabled" : "Any IP"}
                      tone={row.ip_whitelist_enabled ? "positive" : "neutral"}
                    />
                  </td>
                  <td className={tdClass}>
                    <StatusBadge
                      label={row.status === "active" ? "Active" : "Revoked"}
                      tone={row.status === "active" ? "positive" : "negative"}
                    />
                  </td>
                  <td className={`${tdClass} text-on-surface-variant text-xs`}>
                    {row.last_used_at ? formatDateTime(row.last_used_at) : "Never"}
                  </td>
                  <td className={`${tdClass} text-on-surface-variant text-xs`}>{formatDateTime(row.created_at)}</td>
                  <td className={`${tdClass} text-right`}>
                    {row.status === "active" && (
                      <form action={revokeAdminApiKeyAction.bind(null, row.id)} className="inline">
                        <button type="submit" className="p-1.5 text-on-surface-variant hover:text-error" title="Revoke">
                          <Icon name="block" className="text-[18px]" />
                        </button>
                      </form>
                    )}
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
