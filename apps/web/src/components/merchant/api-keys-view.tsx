"use client";

import { useEffect, useState } from "react";

import { Card, tdClass, thClass } from "@/components/portal/card";
import { EmptyState } from "@/components/portal/empty-state";
import { Icon } from "@/components/portal/icon";
import { PageHeader } from "@/components/portal/page-header";
import { SegmentedControl } from "@/components/portal/segmented-control";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatDateTime } from "@/lib/format";
import { createApiKey, listApiKeys, revokeApiKey } from "@/lib/portal/api";
import { API_KEY_SCOPES, type ApiKey, type ApiKeyScope } from "@/lib/portal/types";

const SCOPE_LABELS: Record<ApiKeyScope, string> = {
  "collections:write": "Collections — create",
  "collections:read": "Collections — view",
  "payment_links:write": "Payment Links — create",
  "payment_links:read": "Payment Links — view",
  "invoices:write": "Invoices — create",
  "invoices:read": "Invoices — view",
  "transactions:read": "Transactions — view",
  "webhooks:manage": "Webhooks — manage",
};

const STEPS = [
  { step: 1, title: "Generate a key", description: "Create a sandbox key with only the scopes you need." },
  { step: 2, title: "Read the docs", description: "Explore endpoints for payment links, invoices, and payouts." },
  { step: 3, title: "Make your first request", description: "Send a test transaction and confirm the webhook fires." },
];

export function ApiKeysView() {
  const [environment, setEnvironment] = useState<"sandbox" | "live">("sandbox");
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [revealed, setRevealed] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [keyName, setKeyName] = useState("");
  const [scopes, setScopes] = useState<ApiKeyScope[]>([]);

  const visibleKeys = keys.filter((key) => key.environment === environment);

  useEffect(() => {
    listApiKeys().then(setKeys);
  }, []);

  function toggleScope(scope: ApiKeyScope) {
    setScopes((prev) => (prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]));
  }

  async function handleGenerate(event: React.FormEvent) {
    event.preventDefault();
    if (!keyName.trim() || scopes.length === 0) return;

    setGenerating(true);
    try {
      const { key, plaintext_key } = await createApiKey({ name: keyName.trim(), environment, scopes });
      setKeys((prev) => [key, ...prev]);
      setRevealed(plaintext_key);
      setCopied(false);
      setFormOpen(false);
      setKeyName("");
      setScopes([]);
    } finally {
      setGenerating(false);
    }
  }

  async function handleCopy() {
    if (!revealed) return;
    await navigator.clipboard?.writeText(revealed);
    setCopied(true);
  }

  async function handleRevoke(keyId: string) {
    setRevokingId(keyId);
    try {
      const revoked = await revokeApiKey(keyId);
      setKeys((prev) => prev.map((k) => (k.id === keyId ? revoked : k)));
    } finally {
      setRevokingId(null);
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="API Keys"
        description="Manage sandbox and live keys to integrate Infinity Africa into your app."
        action={
          <SegmentedControl
            options={[
              { value: "sandbox" as const, label: "Sandbox" },
              { value: "live" as const, label: "Live" },
            ]}
            value={environment}
            onChange={(value) => {
              setEnvironment(value);
              setRevealed(null);
            }}
          />
        }
      />

      {revealed && (
        <Card className="border-primary">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <h3 className="text-lg font-semibold text-on-background mb-1">Your new API key</h3>
              <p className="text-sm text-error font-medium mb-3">
                Copy this key now. You will not be able to view it again.
              </p>
              <code className="block bg-on-surface text-primary-fixed text-sm px-4 py-3 rounded-lg font-mono break-all">
                {revealed}
              </code>
            </div>
            <button
              type="button"
              onClick={handleCopy}
              className="shrink-0 p-2.5 bg-primary-container/10 text-primary rounded-lg hover:bg-primary-container/20 transition-colors"
              title="Copy key"
            >
              <Icon name={copied ? "check" : "content_copy"} className="text-[20px]" />
            </button>
          </div>
        </Card>
      )}

      {formOpen && (
        <Card>
          <form onSubmit={handleGenerate} className="space-y-5">
            <h3 className="text-2xl font-semibold text-on-background">
              Generate {environment === "sandbox" ? "Sandbox" : "Live"} Key
            </h3>
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1.5">Key Name</label>
              <input
                className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary text-sm"
                placeholder="e.g. Website checkout integration"
                type="text"
                value={keyName}
                onChange={(event) => setKeyName(event.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-2">Scopes</label>
              <div className="grid sm:grid-cols-2 gap-2.5">
                {API_KEY_SCOPES.map((scope) => (
                  <label
                    key={scope}
                    className="flex items-center gap-2.5 px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg cursor-pointer"
                  >
                    <input
                      checked={scopes.includes(scope)}
                      onChange={() => toggleScope(scope)}
                      className="rounded border-outline-variant text-primary-container focus:ring-primary"
                      type="checkbox"
                    />
                    <span className="text-sm font-medium text-on-surface">{SCOPE_LABELS[scope]}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button
                type="submit"
                disabled={generating || !keyName.trim() || scopes.length === 0}
                className="bg-primary-container text-on-primary text-sm font-medium py-2.5 px-5 rounded-lg hover:opacity-90 transition-opacity disabled:opacity-60"
              >
                {generating ? "Generating…" : "Generate API Key"}
              </button>
              <button
                type="button"
                onClick={() => setFormOpen(false)}
                className="text-sm font-medium text-on-surface-variant hover:text-on-background"
              >
                Cancel
              </button>
            </div>
          </form>
        </Card>
      )}

      {visibleKeys.length === 0 ? (
        <Card>
          <EmptyState
            icon="vpn_key"
            heading="No API keys yet"
            body="Generate your first sandbox key to start testing the Infinity Africa API — switch to Live once you're ready to go into production."
            actionLabel="Generate API Key"
            onAction={() => setFormOpen(true)}
          />
        </Card>
      ) : (
        <Card padded={false}>
          <div className="flex items-center justify-between p-5 pb-3">
            <h3 className="text-2xl font-semibold text-on-background">{environment === "sandbox" ? "Sandbox" : "Live"} Keys</h3>
            {!formOpen && (
              <button
                type="button"
                onClick={() => setFormOpen(true)}
                className="bg-primary-container text-on-primary text-sm font-medium py-2 px-4 rounded-lg hover:opacity-90 transition-opacity"
              >
                Generate API Key
              </button>
            )}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left min-w-[900px]">
              <thead>
                <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                  <th className={thClass}>Name</th>
                  <th className={thClass}>Key Prefix</th>
                  <th className={thClass}>Scopes</th>
                  <th className={thClass}>Created</th>
                  <th className={thClass}>Last Used</th>
                  <th className={thClass}>Status</th>
                  <th className={`${thClass} text-right`}>Actions</th>
                </tr>
              </thead>
              <tbody className="text-sm">
                {visibleKeys.map((key) => (
                  <tr key={key.id} className="border-t border-surface-container-highest">
                    <td className={`${tdClass} font-medium text-on-background`}>{key.name}</td>
                    <td className={`${tdClass} font-mono text-xs`}>{key.key_prefix}••••••••</td>
                    <td className={tdClass}>
                      <div className="flex flex-wrap gap-1 max-w-[220px]">
                        {key.scopes.length === 0 ? (
                          <span className="text-xs text-on-surface-variant">No scopes</span>
                        ) : (
                          key.scopes.map((scope) => (
                            <span
                              key={scope}
                              className="text-[11px] font-medium bg-surface-container-low border border-surface-container-highest rounded px-1.5 py-0.5"
                            >
                              {scope}
                            </span>
                          ))
                        )}
                      </div>
                    </td>
                    <td className={`${tdClass} text-on-surface-variant text-xs`}>{formatDateTime(key.created_at)}</td>
                    <td className={`${tdClass} text-on-surface-variant text-xs`}>
                      {key.last_used_at ? formatDateTime(key.last_used_at) : "Never"}
                    </td>
                    <td className={tdClass}>
                      <StatusBadge
                        label={key.status === "active" ? "Active" : "Revoked"}
                        tone={key.status === "active" ? "positive" : "negative"}
                        dot
                      />
                    </td>
                    <td className={`${tdClass} text-right`}>
                      {key.status === "active" && (
                        <button
                          type="button"
                          onClick={() => handleRevoke(key.id)}
                          disabled={revokingId === key.id}
                          className="text-error text-xs font-semibold hover:underline disabled:opacity-60"
                        >
                          {revokingId === key.id ? "Revoking…" : "Revoke"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Card>
        <h3 className="text-2xl font-semibold text-on-background mb-5">Quick Start</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-5 mb-6">
          {STEPS.map((item) => (
            <div key={item.step}>
              <div className="w-8 h-8 rounded-full bg-primary-container/15 text-primary flex items-center justify-center font-bold text-sm mb-3">
                {item.step}
              </div>
              <h4 className="font-semibold text-on-background text-sm mb-1">{item.title}</h4>
              <p className="text-sm text-on-surface-variant">{item.description}</p>
            </div>
          ))}
        </div>
        <pre className="bg-on-surface text-primary-fixed text-xs sm:text-sm rounded-lg p-4 overflow-x-auto">
          <span className="text-white/40">curl</span> https://api.infinityafrica.net/v1/payment-links \{"\n"}
          {"  "}-H &quot;Authorization: Bearer inf_live_••••••••&quot; \{"\n"}
          {"  "}-H &quot;Content-Type: application/json&quot;
        </pre>
      </Card>
    </div>
  );
}
