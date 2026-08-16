"use client";

import { useEffect, useState } from "react";

import { Card, tdClass, thClass } from "@/components/portal/card";
import { Icon } from "@/components/portal/icon";
import { PageHeader } from "@/components/portal/page-header";
import { ToggleSwitch } from "@/components/portal/toggle-switch";
import { listMerchantPricingOverrides, listPlatformPricingRules, togglePricingRule } from "@/lib/admin/api";
import type { MerchantPricingOverride, PlatformPricingRule } from "@/lib/admin/types";

function initials(name: string): string {
  return name.charAt(0).toUpperCase();
}

export default function AdminPricingRulesPage() {
  const [rules, setRules] = useState<PlatformPricingRule[]>([]);
  const [overrides, setOverrides] = useState<MerchantPricingOverride[]>([]);

  useEffect(() => {
    listPlatformPricingRules().then(setRules);
    listMerchantPricingOverrides().then(setOverrides);
  }, []);

  async function handleToggle(rule: PlatformPricingRule, enabled: boolean) {
    setRules((prev) => prev.map((r) => (r.id === rule.id ? { ...r, enabled } : r)));
    await togglePricingRule(rule.id, enabled);
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="Pricing Rules"
        description="Configure platform-wide and merchant-specific fee structures."
        action={
          <button className="flex items-center gap-2 bg-primary-container text-on-primary px-4 py-2.5 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity w-fit">
            <Icon name="add" className="text-[20px]" />
            Add Pricing Rule
          </button>
        }
      />

      <Card padded={false}>
        <div className="p-5 pb-3">
          <h3 className="text-2xl font-semibold text-on-background">Platform Default Rules</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left min-w-[720px]">
            <thead>
              <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                <th className={thClass}>Transaction Type</th>
                <th className={thClass}>Fee Type</th>
                <th className={thClass}>Rate</th>
                <th className={thClass}>Applies To</th>
                <th className={thClass}>Status</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {rules.map((rule) => (
                <tr key={rule.id} className="border-t border-surface-container-highest">
                  <td className={`${tdClass} font-medium text-on-background`}>{rule.transaction_type}</td>
                  <td className={`${tdClass} text-on-surface-variant`}>{rule.fee_type}</td>
                  <td className={tdClass}>
                    {rule.free ? (
                      <span className="inline-flex items-center gap-1 bg-accent text-primary px-2.5 py-1 rounded-full text-xs font-semibold border border-primary/20 w-fit">
                        <Icon name="check" className="text-[12px] font-bold" />
                        {rule.rate} (Free)
                      </span>
                    ) : (
                      <span className="font-mono">{rule.rate}</span>
                    )}
                  </td>
                  <td className={`${tdClass} text-on-surface-variant`}>{rule.applies_to}</td>
                  <td className={tdClass}>
                    <ToggleSwitch checked={rule.enabled} onChange={(checked) => handleToggle(rule, checked)} label={rule.transaction_type} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card padded={false}>
        <div className="p-5 pb-3">
          <h3 className="text-2xl font-semibold text-on-background">Merchant-Specific Overrides</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left min-w-[720px]">
            <thead>
              <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                <th className={thClass}>Merchant</th>
                <th className={thClass}>Transaction Type</th>
                <th className={thClass}>Rate</th>
                <th className={thClass}>Reason</th>
                <th className={`${thClass} text-right`}>Actions</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {overrides.map((override) => (
                <tr key={override.id} className="border-t border-surface-container-highest">
                  <td className={tdClass}>
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-primary-container/15 text-primary flex items-center justify-center font-bold text-xs shrink-0">
                        {initials(override.merchant_name)}
                      </div>
                      <span className="font-medium text-on-background">{override.merchant_name}</span>
                    </div>
                  </td>
                  <td className={`${tdClass} text-on-surface-variant`}>{override.transaction_type}</td>
                  <td className={`${tdClass} font-mono`}>{override.rate}</td>
                  <td className={`${tdClass} text-on-surface-variant text-sm`}>{override.reason}</td>
                  <td className={`${tdClass} text-right`}>
                    <button className="p-1.5 text-on-surface-variant hover:text-primary">
                      <Icon name="edit" className="text-[18px]" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
