"use client";

import { useRouter } from "next/navigation";
import { Fragment, useState } from "react";
import { DESTINATION_CODE_LABELS, DISBURSEMENT_METHOD_LABELS, DisbursementMethod } from "@infinity/shared";

import { Card, tdClass, thClass } from "@/components/portal/card";
import { Icon } from "@/components/portal/icon";
import { formatCurrency } from "@/lib/format";
import {
  createMerchantPricingRuleAction,
  createPlatformFallbackPricingRuleAction,
  deactivatePricingRuleAction,
  updatePricingRuleAction,
} from "@/lib/admin/live-actions";
import type { Merchant, PricingRuleRow } from "@/lib/admin/types";

const inputClass =
  "w-full px-3 py-2 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary";
const labelClass = "block text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-1.5";

function RuleFields({ rule }: { rule?: PricingRuleRow }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
      <div>
        <label className={labelClass}>Channel (optional)</label>
        <select name="channel" defaultValue={rule?.channel ?? ""} className={inputClass}>
          <option value="">Any channel</option>
          {Object.values(DisbursementMethod).map((method) => (
            <option key={method} value={method}>
              {DISBURSEMENT_METHOD_LABELS[method]}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className={labelClass}>Destination (optional)</label>
        <select name="destination_code" defaultValue={rule?.destination_code ?? ""} className={inputClass}>
          <option value="">Any destination</option>
          {Object.entries(DESTINATION_CODE_LABELS).map(([code, label]) => (
            <option key={code} value={code}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className={labelClass}>Percentage Fee (%)</label>
        <input name="percentage_fee" type="number" step="0.001" min="0" max="100" defaultValue={rule?.percentage_fee ?? "0"} className={inputClass} />
      </div>
      <div>
        <label className={labelClass}>Flat Fee (TZS)</label>
        <input name="flat_fee" type="number" step="0.01" min="0" defaultValue={rule?.flat_fee ?? "0"} className={inputClass} />
      </div>
      <div>
        <label className={labelClass}>Minimum Fee (TZS, optional)</label>
        <input name="minimum_fee" type="number" step="0.01" min="0" defaultValue={rule?.minimum_fee ?? ""} className={inputClass} />
      </div>
      <div>
        <label className={labelClass}>Maximum Fee (TZS, optional)</label>
        <input name="maximum_fee" type="number" step="0.01" min="0" defaultValue={rule?.maximum_fee ?? ""} className={inputClass} />
      </div>
      <div>
        <label className={labelClass}>Processor Charge (TZS)</label>
        <input name="processor_fee_flat" type="number" step="0.01" min="0" defaultValue={rule?.processor_fee_flat ?? "0"} className={inputClass} />
      </div>
      <div className="flex items-end pb-2">
        <label className="flex items-center gap-2 text-sm text-on-surface">
          <input
            name="processor_fee_pass_through"
            type="checkbox"
            defaultChecked={rule?.processor_fee_pass_through ?? false}
            className="rounded"
          />
          Pass processor charge to merchant
        </label>
      </div>
      <div>
        <label className={labelClass}>Effective From (optional, defaults to now)</label>
        <input
          name="effective_from"
          type="datetime-local"
          defaultValue={toDatetimeLocalValue(rule?.effective_from)}
          className={inputClass}
        />
      </div>
      <div>
        <label className={labelClass}>Effective To (optional)</label>
        <input
          name="effective_to"
          type="datetime-local"
          defaultValue={toDatetimeLocalValue(rule?.effective_to)}
          className={inputClass}
        />
      </div>
      <div className="col-span-2 sm:col-span-4">
        <label className={labelClass}>Label (optional)</label>
        <input name="label" defaultValue={rule?.label ?? ""} placeholder="e.g. Negotiated enterprise rate" className={inputClass} />
      </div>
    </div>
  );
}

function toDatetimeLocalValue(iso: string | null | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function RuleRow({ rule, onEdit }: { rule: PricingRuleRow; onEdit: () => void }) {
  return (
    <tr className="border-t border-surface-container-highest">
      <td className={`${tdClass} text-on-surface-variant`}>{rule.label || "—"}</td>
      <td className={`${tdClass} text-on-surface-variant`}>
        {rule.channel ? DISBURSEMENT_METHOD_LABELS[rule.channel] : "Any channel"}
      </td>
      <td className={`${tdClass} text-on-surface-variant`}>
        {rule.destination_code ? DESTINATION_CODE_LABELS[rule.destination_code as keyof typeof DESTINATION_CODE_LABELS] ?? rule.destination_code : "Any destination"}
      </td>
      <td className={tdClass}>{rule.percentage_fee}%</td>
      <td className={tdClass}>{formatCurrency(rule.flat_fee, "TZS")}</td>
      <td className={`${tdClass} text-on-surface-variant text-xs`}>{rule.processor_fee_pass_through ? "Pass-through" : "Absorbed"}</td>
      <td className={tdClass}>
        {rule.is_active ? (
          <span className="inline-flex items-center gap-1 bg-accent text-primary px-2.5 py-1 rounded-full text-xs font-semibold border border-primary/20">
            <Icon name="check" className="text-[12px] font-bold" />
            Active
          </span>
        ) : (
          <span className="bg-surface-container-highest text-on-surface-variant px-2.5 py-1 rounded-full text-xs font-semibold">
            Inactive
          </span>
        )}
      </td>
      <td className={`${tdClass} text-right whitespace-nowrap`}>
        <button onClick={onEdit} className="p-1.5 text-on-surface-variant hover:text-primary mr-1" title="Edit">
          <Icon name="edit" className="text-[18px]" />
        </button>
        {rule.is_active && (
          <form action={deactivatePricingRuleAction.bind(null, rule.id)} className="inline">
            <button className="p-1.5 text-on-surface-variant hover:text-error" title="Deactivate">
              <Icon name="block" className="text-[18px]" />
            </button>
          </form>
        )}
      </td>
    </tr>
  );
}

function PricingRuleSection({
  title,
  description,
  rules,
  createAction,
}: {
  title: string;
  description: string;
  rules: PricingRuleRow[];
  createAction: (formData: FormData) => Promise<void>;
}) {
  const [showCreate, setShowCreate] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  return (
    <Card padded={false}>
      <div className="p-5 pb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-2xl font-semibold text-on-background">{title}</h3>
          <p className="text-sm text-on-surface-variant mt-0.5">{description}</p>
        </div>
        <button
          type="button"
          onClick={() => setShowCreate((v) => !v)}
          className="flex items-center gap-2 bg-primary-container text-on-primary px-4 py-2.5 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity w-fit"
        >
          <Icon name="add" className="text-[20px]" />
          Add Pricing Rule
        </button>
      </div>

      {showCreate && (
        <form action={createAction} className="p-5 border-t border-surface-container-highest space-y-4">
          <RuleFields />
          <button className="bg-primary-container text-on-primary text-sm font-medium px-6 py-2.5 rounded-lg hover:opacity-90">
            Create Rule
          </button>
        </form>
      )}

      {rules.length === 0 ? (
        <p className="p-6 text-sm text-on-surface-variant">No pricing rules yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left min-w-[780px]">
            <thead>
              <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                <th className={thClass}>Label</th>
                <th className={thClass}>Channel</th>
                <th className={thClass}>Destination</th>
                <th className={thClass}>Percentage</th>
                <th className={thClass}>Flat Fee</th>
                <th className={thClass}>Processor Charge</th>
                <th className={thClass}>Status</th>
                <th className={`${thClass} text-right`}>Actions</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {rules.map((rule) => (
                <Fragment key={rule.id}>
                  <RuleRow rule={rule} onEdit={() => setEditingId((id) => (id === rule.id ? null : rule.id))} />
                  {editingId === rule.id && (
                    <tr className="border-t border-surface-container-highest bg-surface-container-low">
                      <td className={tdClass} colSpan={8}>
                        <form action={updatePricingRuleAction.bind(null, rule.id)} className="space-y-4">
                          <RuleFields rule={rule} />
                          <button className="bg-primary-container text-on-primary text-sm font-medium px-6 py-2.5 rounded-lg hover:opacity-90">
                            Save Changes
                          </button>
                        </form>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export function PricingRulesView({
  merchants,
  platformRules,
  selectedMerchantId,
  merchantRules,
}: {
  merchants: Merchant[];
  platformRules: PricingRuleRow[];
  selectedMerchantId: string | null;
  merchantRules: PricingRuleRow[];
}) {
  const router = useRouter();

  return (
    <div className="space-y-8">
      <Card>
        <label className={labelClass}>Select a merchant to view or set their negotiated pricing</label>
        <select
          value={selectedMerchantId ?? ""}
          onChange={(event) => {
            const value = event.target.value;
            router.push(value ? `/super-admin/pricing-rules?merchant_id=${value}` : "/super-admin/pricing-rules");
          }}
          className={inputClass}
        >
          <option value="">Choose a merchant…</option>
          {merchants.map((merchant) => (
            <option key={merchant.merchant_id} value={merchant.merchant_id}>
              {merchant.business_name}
            </option>
          ))}
        </select>
      </Card>

      {selectedMerchantId && (
        <PricingRuleSection
          title="Merchant Pricing Rules"
          description="Negotiated fees for this merchant — take precedence over the platform fallback below."
          rules={merchantRules}
          createAction={createMerchantPricingRuleAction.bind(null, selectedMerchantId)}
        />
      )}

      <PricingRuleSection
        title="Platform Fallback Rules"
        description="Applied to any withdrawal with no matching merchant-specific rule."
        rules={platformRules}
        createAction={createPlatformFallbackPricingRuleAction}
      />
    </div>
  );
}
