"use client";

import { Fragment, useMemo, useState } from "react";
import { DISBURSEMENT_METHOD_LABELS } from "@infinity/shared";

import { Card, tdClass, thClass } from "@/components/portal/card";
import { Icon } from "@/components/portal/icon";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatCurrency, formatDateTime, maskAccountIdentifier } from "@/lib/format";
import {
  approveWithdrawalAction,
  reconcilePendingWithdrawalsAction,
  refreshWithdrawalStatusAction,
  rejectWithdrawalAction,
  requestInfoWithdrawalAction,
} from "@/lib/admin/live-actions";
import { adminWithdrawalBadge } from "@/lib/admin/status-tones";
import type { AdminWithdrawalRow } from "@/lib/admin/types";

const STATUS_FILTERS = [
  "All",
  "Pending Approval",
  "Info Requested",
  "Processing",
  "Successful",
  "Failed",
  "Rejected",
  "Needs Attention",
  "Needs Reconciliation",
  "Blocked",
  "Reversed",
] as const;

const STATUS_FILTER_MAP: Record<(typeof STATUS_FILTERS)[number], AdminWithdrawalRow["status"] | null> = {
  All: null,
  "Pending Approval": "PENDING_ADMIN_APPROVAL",
  "Info Requested": "INFO_REQUESTED",
  Processing: "PROCESSING",
  Successful: "SUCCESS",
  Failed: "FAILED",
  Rejected: "REJECTED",
  "Needs Attention": "NEEDS_ADMIN_ATTENTION",
  "Needs Reconciliation": "NEEDS_RECONCILIATION",
  Blocked: "BLOCKED_IP_WHITELIST",
  Reversed: "REVERSED",
};

const inputClass =
  "w-full px-2.5 py-1.5 bg-surface-container-low border border-surface-container-highest rounded-md text-xs focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary";

export function WithdrawalsTable({ rows, queue }: { rows: AdminWithdrawalRow[]; queue: AdminWithdrawalRow[] }) {
  const [statusFilter, setStatusFilter] = useState<(typeof STATUS_FILTERS)[number]>("All");
  const [expandedRejectId, setExpandedRejectId] = useState<string | null>(null);
  const [expandedInfoId, setExpandedInfoId] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const target = STATUS_FILTER_MAP[statusFilter];
    if (!target) return rows;
    return rows.filter((row) => row.status === target);
  }, [rows, statusFilter]);

  return (
    <>
      {queue.length > 0 && (
        <Card className="border-amber-200" padded={false}>
          <div className="p-5 pb-3 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Icon name="warning" className="text-amber-600" />
              <div>
                <h3 className="text-xl font-semibold text-on-background">Withdrawal Approval Queue</h3>
                <p className="text-sm text-on-surface-variant mt-0.5">
                  Every withdrawal request needs Super Admin approval before it&apos;s sent to the provider.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="bg-amber-100 text-amber-700 px-2.5 py-1 rounded-full text-xs font-semibold">
                {queue.length} pending
              </span>
              <form action={reconcilePendingWithdrawalsAction}>
                <button className="px-3 py-1.5 rounded-lg border border-outline-variant text-on-surface-variant text-xs font-semibold hover:bg-surface-container-low">
                  Reconcile Pending
                </button>
              </form>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left min-w-[960px]">
              <thead>
                <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                  <th className={thClass}>Merchant</th>
                  <th className={thClass}>Destination</th>
                  <th className={thClass}>Method</th>
                  <th className={thClass}>Amount</th>
                  <th className={thClass}>Fees</th>
                  <th className={thClass}>Total Reserved</th>
                  <th className={thClass}>Recipient Receives</th>
                  <th className={thClass}>Requested</th>
                  <th className={`${thClass} text-right`}>Approval</th>
                </tr>
              </thead>
              <tbody className="text-sm">
                {queue.map((request) => (
                  <Fragment key={request.withdrawal_id}>
                    <tr className="border-t border-surface-container-highest">
                      <td className={`${tdClass} font-medium text-on-background`}>{request.merchant_name}</td>
                      <td className={tdClass}>
                        <div>{request.destination}</div>
                        <div className="text-xs text-on-surface-variant font-mono">
                          {maskAccountIdentifier(request.destination_identifier)}
                        </div>
                      </td>
                      <td className={`${tdClass} text-on-surface-variant`}>{DISBURSEMENT_METHOD_LABELS[request.method]}</td>
                      <td className={`${tdClass} font-semibold text-on-background`}>{formatCurrency(request.amount, request.currency)}</td>
                      <td className={`${tdClass} text-on-surface-variant`}>{formatCurrency(request.total_charges, request.currency)}</td>
                      <td className={tdClass}>{formatCurrency(request.total_reserved_amount ?? request.amount, request.currency)}</td>
                      <td className={tdClass}>{formatCurrency(request.recipient_net_amount ?? request.amount, request.currency)}</td>
                      <td className={`${tdClass} text-on-surface-variant text-xs`}>{formatDateTime(request.created_at)}</td>
                      <td className={`${tdClass} text-right whitespace-nowrap`}>
                        <form action={approveWithdrawalAction.bind(null, request.withdrawal_id)} className="inline">
                          <button className="px-3 py-1.5 rounded-lg bg-primary-container text-on-primary text-xs font-semibold hover:opacity-90 mr-2">
                            Approve
                          </button>
                        </form>
                        <button
                          type="button"
                          onClick={() => setExpandedRejectId((id) => (id === request.withdrawal_id ? null : request.withdrawal_id))}
                          className="px-3 py-1.5 rounded-lg border border-outline-variant text-on-surface-variant text-xs font-semibold hover:bg-surface-container-low mr-2"
                        >
                          Reject
                        </button>
                        <button
                          type="button"
                          onClick={() => setExpandedInfoId((id) => (id === request.withdrawal_id ? null : request.withdrawal_id))}
                          className="px-3 py-1.5 rounded-lg border border-outline-variant text-on-surface-variant text-xs font-semibold hover:bg-surface-container-low"
                        >
                          Request Info
                        </button>
                      </td>
                    </tr>
                    {expandedRejectId === request.withdrawal_id && (
                      <tr className="border-t border-surface-container-highest bg-surface-container-low">
                        <td className={tdClass} colSpan={9}>
                          <form
                            action={rejectWithdrawalAction.bind(null, request.withdrawal_id)}
                            className="flex items-center gap-2"
                          >
                            <input
                              name="rejection_reason"
                              required
                              placeholder="Reason for rejecting this withdrawal (required)"
                              className={`${inputClass} max-w-md`}
                            />
                            <button className="px-3 py-1.5 rounded-lg bg-error text-white text-xs font-semibold shrink-0">
                              Confirm Reject
                            </button>
                          </form>
                        </td>
                      </tr>
                    )}
                    {expandedInfoId === request.withdrawal_id && (
                      <tr className="border-t border-surface-container-highest bg-surface-container-low">
                        <td className={tdClass} colSpan={9}>
                          <form
                            action={requestInfoWithdrawalAction.bind(null, request.withdrawal_id)}
                            className="flex items-center gap-2"
                          >
                            <input
                              name="message"
                              required
                              placeholder="What do you need from the merchant?"
                              className={`${inputClass} max-w-md`}
                            />
                            <input
                              name="requested_documents"
                              placeholder="Requested documents (comma-separated, optional)"
                              className={`${inputClass} max-w-xs`}
                            />
                            <button className="px-3 py-1.5 rounded-lg bg-primary-container text-on-primary text-xs font-semibold shrink-0">
                              Send Request
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
        </Card>
      )}

      <div className="flex flex-wrap gap-2">
        {STATUS_FILTERS.map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => setStatusFilter(option)}
            className={
              statusFilter === option
                ? "px-3.5 py-2 rounded-full bg-primary-container/10 text-primary text-sm font-semibold"
                : "px-3.5 py-2 rounded-full bg-surface-container-low text-on-surface-variant text-sm font-semibold hover:bg-surface-container-highest"
            }
          >
            {option}
          </button>
        ))}
      </div>

      <Card padded={false}>
        <div className="p-5 pb-3">
          <h3 className="text-2xl font-semibold text-on-background">All Withdrawals</h3>
        </div>
        {filtered.length === 0 ? (
          <p className="p-6 text-sm text-on-surface-variant">No withdrawals match this filter.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left min-w-[920px]">
              <thead>
                <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                  <th className={thClass}>Date</th>
                  <th className={thClass}>Merchant</th>
                  <th className={thClass}>Destination</th>
                  <th className={thClass}>Method</th>
                  <th className={thClass}>Amount</th>
                  <th className={thClass}>Fees</th>
                  <th className={thClass}>Provider Ref</th>
                  <th className={thClass}>Status</th>
                  <th className={`${thClass} text-right`}>Actions</th>
                </tr>
              </thead>
              <tbody className="text-sm">
                {filtered.map((row) => {
                  const needsRefresh = row.status === "PROCESSING" || row.status === "NEEDS_RECONCILIATION";
                  return (
                    <tr key={row.withdrawal_id} className="border-t border-surface-container-highest">
                      <td className={`${tdClass} text-on-surface-variant text-xs`}>{formatDateTime(row.created_at)}</td>
                      <td className={`${tdClass} font-medium text-on-background`}>{row.merchant_name}</td>
                      <td className={tdClass}>
                        <div>{row.destination}</div>
                        <div className="text-xs text-on-surface-variant font-mono">
                          {maskAccountIdentifier(row.destination_identifier)}
                        </div>
                      </td>
                      <td className={`${tdClass} text-on-surface-variant`}>{DISBURSEMENT_METHOD_LABELS[row.method]}</td>
                      <td className={`${tdClass} font-semibold text-on-background`}>{formatCurrency(row.amount, row.currency)}</td>
                      <td className={`${tdClass} text-on-surface-variant`}>{formatCurrency(row.total_charges, row.currency)}</td>
                      <td className={`${tdClass} text-on-surface-variant text-xs font-mono`}>{row.provider_reference ?? "—"}</td>
                      <td className={tdClass}>
                        <StatusBadge {...adminWithdrawalBadge(row.status)} />
                        {row.status === "REJECTED" && row.rejection_reason && (
                          <p className="text-xs text-on-surface-variant mt-1">{row.rejection_reason}</p>
                        )}
                      </td>
                      <td className={`${tdClass} text-right`}>
                        {needsRefresh && (
                          <form action={refreshWithdrawalStatusAction.bind(null, row.withdrawal_id)} className="inline">
                            <button className="px-3 py-1.5 rounded-lg border border-outline-variant text-on-surface-variant text-xs font-semibold hover:bg-surface-container-low">
                              Refresh Status
                            </button>
                          </form>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
