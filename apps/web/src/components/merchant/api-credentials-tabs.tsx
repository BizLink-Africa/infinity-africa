"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { Icon } from "@/components/portal/icon";
import { PageHeader } from "@/components/portal/page-header";

import { ApiCredentialsOverview } from "./api-credentials-overview";
import { ApiKeysView } from "./api-keys-view";
import { ApiLogsView } from "./api-logs-view";
import { DeveloperDocsView } from "./developer-docs-view";
import { IpAllowlistView } from "./ip-allowlist-view";
import { WebhooksView } from "./webhooks-view";

export type ApiCredentialsTab = "overview" | "keys" | "webhooks" | "ip-allowlist" | "logs" | "docs";

const TABS: { value: ApiCredentialsTab; label: string; icon: string }[] = [
  { value: "overview", label: "Overview", icon: "space_dashboard" },
  { value: "keys", label: "API Keys", icon: "vpn_key" },
  { value: "webhooks", label: "Webhooks", icon: "webhook" },
  { value: "ip-allowlist", label: "IP Allowlist", icon: "shield_lock" },
  { value: "logs", label: "API Logs", icon: "history_toggle_off" },
  { value: "docs", label: "Developer Docs", icon: "menu_book" },
];

function isValidTab(value: string | null): value is ApiCredentialsTab {
  return TABS.some((tab) => tab.value === value);
}

export function ApiCredentialsTabs({ initialTab }: { initialTab?: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const fromUrl = searchParams.get("tab");
  const [activeTab, setActiveTab] = useState<ApiCredentialsTab>(
    isValidTab(fromUrl) ? fromUrl : isValidTab(initialTab ?? null) ? (initialTab as ApiCredentialsTab) : "overview",
  );

  function selectTab(tab: ApiCredentialsTab) {
    setActiveTab(tab);
    router.replace(`/portal/api-credentials?tab=${tab}`, { scroll: false });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="API Credentials"
        description="Everything for integrating your website, mobile app, or backend with Infinity Africa — in one place."
      />

      <div className="flex flex-nowrap gap-0.5 rounded-lg border border-surface-container-highest bg-surface-container-low p-1 overflow-x-auto md:overflow-visible">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.value}
            onClick={() => selectTab(tab.value)}
            className={`flex items-center gap-1 px-2.5 py-1.5 rounded-md text-sm font-medium whitespace-nowrap shrink-0 transition-colors ${
              activeTab === tab.value
                ? "bg-primary-container text-on-primary"
                : "text-on-surface-variant hover:bg-surface-container-highest"
            }`}
          >
            <Icon name={tab.icon} className="text-[16px]" />
            {tab.label}
          </button>
        ))}
      </div>

      <div role="tabpanel">
        {activeTab === "overview" && <ApiCredentialsOverview onSelectTab={selectTab} />}
        {activeTab === "keys" && <ApiKeysView />}
        {activeTab === "webhooks" && <WebhooksView />}
        {activeTab === "ip-allowlist" && <IpAllowlistView />}
        {activeTab === "logs" && <ApiLogsView />}
        {activeTab === "docs" && <DeveloperDocsView />}
      </div>
    </div>
  );
}
