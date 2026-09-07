"use client";

import { Fragment, useActionState, useState } from "react";
import { useFormStatus } from "react-dom";

import { Card, tdClass, thClass } from "@/components/portal/card";
import { Icon } from "@/components/portal/icon";
import { StatusBadge, type BadgeTone } from "@/components/portal/status-badge";
import { formatDateTime } from "@/lib/format";
import {
  addRiskAlertNoteAction,
  requestDocumentsForAlertAction,
  updateRiskAlertStatusAction,
  type RiskAlertActionState,
} from "@/lib/admin/live-actions";
import type { AdminFraudAlertRow, FraudRiskLevel } from "@/lib/admin/types";

/** Declared here, not in live-actions.ts: a "use server" module can only
 * export async functions, never a plain constant. */
const RISK_ALERT_ACTION_IDLE: RiskAlertActionState = { error: null, ok: false };

const RISK_TONE: Record<FraudRiskLevel, BadgeTone> = {
  LOW: "neutral",
  MEDIUM: "pending",
  HIGH: "negative",
  CRITICAL: "negative",
};

const STATUS_OPTIONS = ["OPEN", "UNDER_REVIEW", "DOCUMENTS_REQUESTED", "CLEARED", "ESCALATED", "CLOSED"];

const fieldClass = "px-3 py-2 bg-surface border border-surface-container-highest rounded-lg text-xs";

/** Must be a child of the <form>, per useFormStatus's own rule. */
function SubmitButton({ className, idleLabel, pendingLabel }: { className: string; idleLabel: string; pendingLabel: string }) {
  const { pending } = useFormStatus();
  return (
    <button type="submit" disabled={pending} className={`${className} disabled:opacity-60`}>
      {pending ? pendingLabel : idleLabel}
    </button>
  );
}

/** Inline confirmation / error for a completed submit — the piece these
 * forms were missing, so a working action looked like it did nothing. */
function ActionFeedback({ error, ok, okLabel }: { error: string | null; ok: boolean; okLabel: string }) {
  if (error) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-error">
        <Icon name="error" className="text-[14px]" />
        {error}
      </span>
    );
  }
  if (ok) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-primary">
        <Icon name="check_circle" className="text-[14px]" />
        {okLabel}
      </span>
    );
  }
  return null;
}

function UpdateStatusForm({ alert }: { alert: AdminFraudAlertRow }) {
  const [state, formAction] = useActionState<RiskAlertActionState, FormData>(
    updateRiskAlertStatusAction.bind(null, alert.alert_id),
    RISK_ALERT_ACTION_IDLE,
  );
  return (
    <form action={formAction} className="flex flex-wrap items-center gap-2">
      <select name="status" defaultValue={alert.status} className={fieldClass}>
        {STATUS_OPTIONS.map((option) => (
          <option key={option} value={option}>
            {option.replace(/_/g, " ")}
          </option>
        ))}
      </select>
      <SubmitButton
        className="bg-primary-container text-on-primary text-xs font-semibold py-2 px-4 rounded-lg hover:opacity-90"
        idleLabel="Update Status"
        pendingLabel="Updating…"
      />
      <ActionFeedback error={state.error} ok={state.ok} okLabel={`Status set to ${alert.status.replace(/_/g, " ")}`} />
    </form>
  );
}

function RequestDocumentsForm({ alert }: { alert: AdminFraudAlertRow }) {
  const [state, formAction] = useActionState<RiskAlertActionState, FormData>(
    requestDocumentsForAlertAction.bind(null, alert.alert_id),
    RISK_ALERT_ACTION_IDLE,
  );
  return (
    <form action={formAction} className="flex flex-wrap items-center gap-2">
      <input name="requested_documents" placeholder="receipt, proof_of_delivery" className={`${fieldClass} w-56`} />
      <input name="reason" placeholder="Reason for request" className={`${fieldClass} w-56`} />
      <SubmitButton
        className="bg-white border border-primary text-primary text-xs font-semibold py-2 px-4 rounded-lg hover:bg-primary-container/10"
        idleLabel="Request Documents"
        pendingLabel="Requesting…"
      />
      <ActionFeedback error={state.error} ok={state.ok} okLabel="Documents requested" />
    </form>
  );
}

function AddNoteForm({ alert }: { alert: AdminFraudAlertRow }) {
  const [state, formAction] = useActionState<RiskAlertActionState, FormData>(
    addRiskAlertNoteAction.bind(null, alert.alert_id),
    RISK_ALERT_ACTION_IDLE,
  );
  return (
    <form action={formAction} className="flex flex-wrap items-center gap-2">
      <input name="note" placeholder="Add an internal note" className={`${fieldClass} w-72`} />
      <SubmitButton
        className="border border-outline-variant text-on-surface-variant text-xs font-semibold py-2 px-4 rounded-lg hover:bg-surface-container-highest"
        idleLabel="Add Note"
        pendingLabel="Adding…"
      />
      <ActionFeedback error={state.error} ok={state.ok} okLabel="Note added" />
    </form>
  );
}

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
                    <td className={tdClass}>
                      <div className="font-medium text-on-background">{alert.merchant_name ?? "—"}</div>
                      {alert.merchant_code && (
                        <div className="font-mono text-xs text-on-surface-variant">{alert.merchant_code}</div>
                      )}
                    </td>
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
                          <UpdateStatusForm alert={alert} />
                          <RequestDocumentsForm alert={alert} />
                          <AddNoteForm alert={alert} />
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
