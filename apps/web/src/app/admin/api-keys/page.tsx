"use client";

import { useEffect, useState } from "react";

import { AdminKpiCard } from "@/components/admin/kpi-card";
import { Card, tdClass, thClass } from "@/components/portal/card";
import { Icon } from "@/components/portal/icon";
import { PageHeader } from "@/components/portal/page-header";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatDateTime } from "@/lib/format";
import { listPlatformApiKeys, revokeApiKey } from "@/lib/admin/api";
import { apiKeyEnvironmentBadge, apiKeyStatusBadge } from "@/lib/admin/status-tones";
import type { PlatformApiKeyRow } from "@/lib/admin/types";

function initials(name: string): string {
  return name.charAt(0).toUpperCase();
}

export default function AdminApiKeysPage() {
  const [keys, setKeys] = useState<PlatformApiKeyRow[]>([]);

  useEffect(() => {
    listPlatformApiKeys().then(setKeys);
  }, []);

  async function handleRevoke(key: PlatformApiKeyRow) {
    setKeys((prev) => prev.map((k) => (k.id === key.id ? { ...k, status: "Revoked" } : k)));
    await revokeApiKey(key.id);
  }

  const live = keys.filter((k) => k.environment === "Live" && k.status === "Active").length;
  const revoked = keys.filter((k) => k.status === "Revoked").length;

  return (
    <div className="space-y-8">
      <PageHeader
        title="API Keys"
        description="Oversee sandbox and live API keys issued to every merchant on the platform."
        action={
          <button className="flex items-center gap-2 bg-primary-container text-on-primary px-4 py-2.5 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity w-fit">
            <Icon name="add" className="text-[20px]" />
            Issue Platform Key
          </button>
        }
      />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        <AdminKpiCard icon="vpn_key" label="Total Active Keys" value={keys.filter((k) => k.status === "Active").length.toLocaleString()} />
        <AdminKpiCard icon="bolt" label="Live Keys" value={live.toLocaleString()} />
        <AdminKpiCard icon="block" label="Revoked This Month" value={revoked.toLocaleString()} />
      </div>

      <Card padded={false}>
        <div className="p-5 pb-3">
          <h3 className="text-2xl font-semibold text-on-background">Merchant API Keys</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left min-w-[760px]">
            <thead>
              <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                <th className={thClass}>Merchant</th>
                <th className={thClass}>Key</th>
                <th className={thClass}>Environment</th>
                <th className={thClass}>Last Used</th>
                <th className={thClass}>Status</th>
                <th className={`${thClass} text-right`}>Actions</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {keys.map((key) => (
                <tr key={key.id} className="border-t border-surface-container-highest">
                  <td className={tdClass}>
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-primary-container/15 text-primary flex items-center justify-center font-bold text-xs shrink-0">
                        {initials(key.merchant_name)}
                      </div>
                      <span className="font-medium text-on-background">{key.merchant_name}</span>
                    </div>
                  </td>
                  <td className={`${tdClass} font-mono text-xs`}>{key.key_masked}</td>
                  <td className={tdClass}>
                    <StatusBadge {...apiKeyEnvironmentBadge(key.environment)} />
                  </td>
                  <td className={`${tdClass} text-on-surface-variant text-xs`}>{formatDateTime(key.last_used_at)}</td>
                  <td className={tdClass}>
                    <StatusBadge {...apiKeyStatusBadge(key.status)} />
                  </td>
                  <td className={`${tdClass} text-right whitespace-nowrap`}>
                    <button className="p-1.5 text-on-surface-variant hover:text-primary" title="View">
                      <Icon name="visibility" className="text-[18px]" />
                    </button>
                    <button
                      disabled={key.status === "Revoked"}
                      onClick={() => handleRevoke(key)}
                      className="p-1.5 text-on-surface-variant hover:text-error disabled:opacity-40 disabled:hover:text-on-surface-variant"
                      title="Revoke"
                    >
                      <Icon name="block" className="text-[18px]" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <h3 className="text-xl font-semibold text-on-background mb-4">Platform Rate Limits</h3>
        <div className="divide-y divide-surface-container-highest">
          <div className="flex items-center justify-between py-3.5 first:pt-0">
            <div>
              <p className="font-semibold text-sm text-on-background">Default requests/minute</p>
              <p className="text-xs text-on-surface-variant">Maximum API requests allowed per minute, per merchant key.</p>
            </div>
            <input className="w-20 text-right px-3 py-1.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm" defaultValue="120" />
          </div>
          <div className="flex items-center justify-between py-3.5">
            <div>
              <p className="font-semibold text-sm text-on-background">Webhook retry attempts</p>
              <p className="text-xs text-on-surface-variant">Number of retries before a failed webhook delivery is abandoned.</p>
            </div>
            <input className="w-20 text-right px-3 py-1.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm" defaultValue="5" />
          </div>
          <div className="flex items-center justify-between py-3.5 last:pb-0">
            <div>
              <p className="font-semibold text-sm text-on-background">Sandbox key expiry</p>
              <p className="text-xs text-on-surface-variant">Sandbox keys never expire unless manually revoked.</p>
            </div>
            <span className="text-sm text-on-surface-variant">Never</span>
          </div>
        </div>
      </Card>
    </div>
  );
}
