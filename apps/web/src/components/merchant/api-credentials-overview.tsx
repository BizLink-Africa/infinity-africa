"use client";

import { useEffect, useState } from "react";

import { Card } from "@/components/portal/card";
import { Icon } from "@/components/portal/icon";
import { PageHeader } from "@/components/portal/page-header";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatDateTime } from "@/lib/format";
import { getMyMerchant, getWebhookConfig, listApiKeys, listApiLogs, listIpAllowlist } from "@/lib/portal/api";
import type { ApiKey, ApiRequestLog, IpAllowlistEntry, WebhookConfig } from "@/lib/portal/types";

import type { ApiCredentialsTab } from "./api-credentials-tabs";

interface ChecklistItem {
  label: string;
  description: string;
  done: boolean;
  tab: ApiCredentialsTab;
}

export function ApiCredentialsOverview({ onSelectTab }: { onSelectTab: (tab: ApiCredentialsTab) => void }) {
  const [keys, setKeys] = useState<ApiKey[] | null>(null);
  const [webhookConfig, setWebhookConfig] = useState<WebhookConfig | null>(null);
  const [ipEntries, setIpEntries] = useState<IpAllowlistEntry[]>([]);
  const [logs, setLogs] = useState<ApiRequestLog[]>([]);
  const [docsVisited, setDocsVisited] = useState(false);

  useEffect(() => {
    listApiKeys().then(setKeys);
    getWebhookConfig().then(setWebhookConfig);
    listIpAllowlist().then(setIpEntries);
    listApiLogs().then(setLogs);
    getMyMerchant();
  }, []);

  const loading = keys === null;
  const activeKeys = keys?.filter((k) => k.status === "active") ?? [];
  const sandboxCount = activeKeys.filter((k) => k.environment === "sandbox").length;
  const productionCount = activeKeys.filter((k) => k.environment === "live").length;
  const anyIpWhitelistEnabled = activeKeys.some((k) => k.ip_whitelist_enabled);
  const anySandboxUsed = activeKeys.some((k) => k.environment === "sandbox" && k.last_used_at);
  const anyLiveKey = productionCount > 0;
  const lastRequest = logs[0] ?? null;

  const integrationStatus = loading
    ? null
    : productionCount > 0
      ? { label: "Live", tone: "positive" as const }
      : sandboxCount > 0
        ? { label: "Sandbox only", tone: "pending" as const }
        : { label: "Not started", tone: "neutral" as const };

  const checklist: ChecklistItem[] = [
    {
      label: "Create API key",
      description: "Generate a sandbox key to start building, or a live key once approved.",
      done: (keys?.length ?? 0) > 0,
      tab: "keys",
    },
    {
      label: "Add webhook URL",
      description: "Tell Infinity Africa where to send payment and payout events.",
      done: Boolean(webhookConfig?.webhook_url),
      tab: "webhooks",
    },
    {
      label: "Add IP allowlist or continue without whitelist",
      description: "Restrict which server IPs can use a key, or explicitly allow any IP.",
      done: (keys?.length ?? 0) > 0,
      tab: "ip-allowlist",
    },
    {
      label: "Read developer docs",
      description: "Authentication, endpoints, webhooks, and idempotency in one place.",
      done: docsVisited,
      tab: "docs",
    },
    {
      label: "Test sandbox integration",
      description: "Make at least one real request with a sandbox key.",
      done: anySandboxUsed,
      tab: "keys",
    },
    {
      label: "Go live",
      description: "Create a production key once your account is approved.",
      done: anyLiveKey,
      tab: "keys",
    },
  ];
  const completedCount = checklist.filter((item) => item.done).length;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Overview"
        description="Your API integration at a glance — keys, webhooks, IP protection, and what's left to set up."
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-1.5">
            Integration Status
          </p>
          {integrationStatus ? (
            <StatusBadge label={integrationStatus.label} tone={integrationStatus.tone} dot />
          ) : (
            <p className="text-sm text-on-surface-variant">Loading…</p>
          )}
        </Card>
        <Card>
          <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-1.5">Sandbox Keys</p>
          <p className="text-2xl font-bold text-on-background">{loading ? "—" : sandboxCount}</p>
        </Card>
        <Card>
          <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-1.5">
            Production Keys
          </p>
          <p className="text-2xl font-bold text-on-background">{loading ? "—" : productionCount}</p>
        </Card>
        <Card>
          <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-1.5">
            Webhook Status
          </p>
          <StatusBadge
            label={webhookConfig?.webhook_url ? "Configured" : "Not set up"}
            tone={webhookConfig?.webhook_url ? "positive" : "neutral"}
            dot
          />
        </Card>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Card>
          <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-1.5">
            IP Whitelist Status
          </p>
          <StatusBadge
            label={anyIpWhitelistEnabled ? "Enabled on at least one key" : "Continue without IP whitelisting"}
            tone={anyIpWhitelistEnabled ? "positive" : "neutral"}
            dot
          />
          <p className="text-xs text-on-surface-variant mt-2">
            {ipEntries.length} IP{ipEntries.length === 1 ? "" : "s"} configured across all keys.
          </p>
        </Card>
        <Card>
          <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-1.5">
            Last API Request
          </p>
          {lastRequest ? (
            <>
              <p className="text-sm font-mono text-on-background">
                {lastRequest.method} {lastRequest.path}
              </p>
              <p className="text-xs text-on-surface-variant mt-1">{formatDateTime(lastRequest.created_at)}</p>
            </>
          ) : (
            <p className="text-sm text-on-surface-variant">No API requests yet.</p>
          )}
        </Card>
      </div>

      <Card>
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-2xl font-semibold text-on-background">Quick Setup Checklist</h3>
          <span className="text-sm text-on-surface-variant">
            {completedCount} of {checklist.length} complete
          </span>
        </div>
        <div className="space-y-2.5">
          {checklist.map((item, index) => (
            <button
              key={item.label}
              type="button"
              onClick={() => {
                if (item.tab === "docs") setDocsVisited(true);
                onSelectTab(item.tab);
              }}
              className="w-full flex items-start gap-3.5 px-4 py-3.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-left hover:border-primary transition-colors"
            >
              <div
                className={`shrink-0 w-6 h-6 rounded-full flex items-center justify-center mt-0.5 ${
                  item.done ? "bg-primary-container text-on-primary" : "bg-surface-container-highest text-on-surface-variant"
                }`}
              >
                {item.done ? <Icon name="check" className="text-[16px]" /> : <span className="text-xs font-semibold">{index + 1}</span>}
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium text-on-background">{item.label}</p>
                <p className="text-xs text-on-surface-variant mt-0.5">{item.description}</p>
              </div>
            </button>
          ))}
        </div>
      </Card>
    </div>
  );
}
