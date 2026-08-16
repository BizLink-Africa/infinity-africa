"use client";

import { Fragment, useState } from "react";

import { Card, tdClass, thClass } from "@/components/portal/card";
import { Icon } from "@/components/portal/icon";
import { StatusBadge, type BadgeTone } from "@/components/portal/status-badge";
import { formatDateTime } from "@/lib/format";
import {
  addRiskAlertNoteAction,
  requestDocumentsForAlertAction,
  updateRiskAlertStatusAction,
} from "@/lib/admin/live-actions";
import type { AdminFraudAlertRow, FraudRiskLevel } from "@/lib/admin/types";

const RISK_TONE: Record<FraudRiskLevel, BadgeTone> = {
  LOW: "neutral",
  MEDIUM: "pending",
  HIGH: "negative",
  CRITICAL: "negative",
};

const STATUS_OPTIONS = ["OPEN", "UNDER_REVIEW", "DOCUMENTS_REQUESTED", "CLEARED", "ESCALATED", "CLOSED"];

export function RiskMonitoringTable({ rows }: { rows: AdminFraudAlertRow[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <Card padded={false}>
      <div className="p-5 pb-3">
        <h3 className="text-2xl font-semibold text-on-background">Fraud Alerts</h3>
      </div>
      {rows.length === 0 ? (
        <p className="p-6 text-sm text-on-surface-variant">No fraud alerts have been raised.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left min-w-[1000px]">
            <thead>
              <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                <th className={thClass}>Risk</th>
                <th className={thClass}>Merchant</th>
                <th className={thClass}>Customer Phone</th>
                <th className={thClass}>Rule</th>
                <th className={thClass}>Status</th>
                <th className={thClass}>Created</th>
                <th className={`${thClass} text-right`}>Actions</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {rows.map((alert) => (
                <Fragment key={alert.alert_id}>
                  <tr className="border-t border-surface-container-highest">
                    <td className={tdClass}>
                      <StatusBadge label={alert.risk_level} tone={RISK_TONE[alert.risk_level]} dot />
                    </td>
                    <td className={`${tdClass} font-medium text-on-background`}>{alert.merchant_name ?? "—"}</td>
                    <td className={tdClass}>{alert.customer_phone ?? "—"}</td>
                    <td className={`${tdClass} font-mono text-xs`}>{alert.rule_code}</td>
                    <td className={tdClass}>
                      <StatusBadge label={alert.status.replace(/_/g, " ")} tone="neutral" />
                    </td>
                    <td className={`${tdClass} text-on-surface-variant text-xs`}>{formatDateTime(alert.created_at)}</td>
                    <td className={`${tdClass} text-right`}>
                      <button
                        onClick={() => setExpanded(expanded === alert.alert_id ? null : alert.alert_id)}
                        className="inline-flex items-center gap-1 text-primary text-xs font-semibold hover:underline"
                      >
                        {expanded === alert.alert_id ? "Hide" : "Manage"}
                        <Icon name={expanded === alert.alert_id ? "expand_less" : "expand_more"} className="text-[16px]" />
                      </button>
                    </td>
                  </tr>
                  {expanded === alert.alert_id && (
                    <tr className="border-t border-surface-container-highest">
                      <td colSpan={7} className="p-0">
                        <div className="p-5 bg-surface-container-low space-y-4">
                          <p className="text-sm text-on-surface">{alert.reason}</p>

                          <form action={updateRiskAlertStatusAction.bind(null, alert.alert_id)} className="flex flex-wrap items-center gap-2">
                            <select name="status" defaultValue={alert.status} className="px-3 py-2 bg-surface border border-surface-container-highest rounded-lg text-xs">
                              {STATUS_OPTIONS.map((option) => (
                                <option key={option} value={option}>
                                  {option.replace(/_/g, " ")}
                                </option>
                              ))}
                            </select>
                            <button type="submit" className="bg-primary-container text-on-primary text-xs font-semibold py-2 px-4 rounded-lg hover:opacity-90">
                              Update Status
                            </button>
                          </form>

                          <form action={requestDocumentsForAlertAction.bind(null, alert.alert_id)} className="flex flex-wrap items-center gap-2">
                            <input
                              name="requested_documents"
                              placeholder="receipt, proof_of_delivery"
                              className="px-3 py-2 bg-surface border border-surface-container-highest rounded-lg text-xs w-56"
                            />
                            <input
                              name="reason"
                              placeholder="Reason for request"
                              className="px-3 py-2 bg-surface border border-surface-container-highest rounded-lg text-xs w-56"
                            />
                            <button type="submit" className="bg-white border border-primary text-primary text-xs font-semibold py-2 px-4 rounded-lg hover:bg-primary-container/10">
                              Request Documents
                            </button>
                          </form>

                          <form action={addRiskAlertNoteAction.bind(null, alert.alert_id)} className="flex flex-wrap items-center gap-2">
                            <input
                              name="note"
                              placeholder="Add an internal note"
                              className="px-3 py-2 bg-surface border border-surface-container-highest rounded-lg text-xs w-72"
                            />
                            <button type="submit" className="border border-outline-variant text-on-surface-variant text-xs font-semibold py-2 px-4 rounded-lg hover:bg-surface-container-highest">
                              Add Note
                            </button>
                          </form>
                        </div>
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
