"use client";

import { useMemo, useState } from "react";
import { DISBURSEMENT_METHOD_LABELS } from "@infinity/shared";

import { Card, tdClass, thClass } from "@/components/portal/card";
import { Icon } from "@/components/portal/icon";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatCurrency, formatDateTime } from "@/lib/format";
import { approveWithdrawalAction, rejectWithdrawalAction } from "@/lib/admin/live-actions";
import { adminWithdrawalBadge } from "@/lib/admin/status-tones";
import type { AdminWithdrawalRow } from "@/lib/admin/types";

const STATUS_FILTERS = ["All", "Pending", "Processing", "Successful", "Failed", "Reversed"] as const;

export function WithdrawalsTable({ rows, queue }: { rows: AdminWithdrawalRow[]; queue: AdminWithdrawalRow[] }) {
  const [statusFilter, setStatusFilter] = useState<(typeof STATUS_FILTERS)[number]>("All");

  const filtered = useMemo(() => {
    if (statusFilter === "All") return rows;
    const map: Record<string, AdminWithdrawalRow["status"]> = {
      Pending: "PENDING",
      Processing: "PROCESSING",
      Successful: "SUCCESS",
      Failed: "FAILED",
      Reversed: "REVERSED",
    };
    return rows.filter((row) => row.status === map[statusFilter]);
  }, [rows, statusFilter]);

  return (
    <>
      {queue.length > 0 && (
        <Card className="border-amber-200" padded={false}>
          <div className="p-5 pb-3 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Icon name="warning" className="text-amber-600" />
              <div>
                <h3 className="text-xl font-semibold text-on-background">High-Value Approval Queue</h3>
                <p className="text-sm text-on-surface-variant mt-0.5">
                  Payouts requiring Super Admin approval before they&apos;re sent to the provider.
                </p>
              </div>
            </div>
            <span className="bg-amber-100 text-amber-700 px-2.5 py-1 rounded-full text-xs font-semibold shrink-0">
              {queue.length} pending
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left min-w-[760px]">
              <thead>
                <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                  <th className={thClass}>Merchant</th>
                  <th className={thClass}>Destination</th>
                  <th className={thClass}>Method</th>
                  <th className={thClass}>Amount</th>
                  <th className={thClass}>Requested</th>
                  <th className={`${thClass} text-right`}>Approval</th>
                </tr>
              </thead>
              <tbody className="text-sm">
                {queue.map((request) => (
                  <tr key={request.withdrawal_id} className="border-t border-surface-container-highest">
                    <td className={`${tdClass} font-medium text-on-background`}>{request.merchant_name}</td>
                    <td className={tdClass}>{request.destination}</td>
                    <td className={`${tdClass} text-on-surface-variant`}>{DISBURSEMENT_METHOD_LABELS[request.method]}</td>
                    <td className={`${tdClass} font-semibold text-on-background`}>{formatCurrency(request.amount, request.currency)}</td>
                    <td className={`${tdClass} text-on-surface-variant text-xs`}>{formatDateTime(request.created_at)}</td>
                    <td className={`${tdClass} text-right whitespace-nowrap`}>
                      <form action={approveWithdrawalAction.bind(null, request.withdrawal_id)} className="inline">
                        <button className="px-3 py-1.5 rounded-lg bg-primary-container text-on-primary text-xs font-semibold hover:opacity-90 mr-2">
                          Approve
                        </button>
                      </form>
                      <form action={rejectWithdrawalAction.bind(null, request.withdrawal_id)} className="inline">
                        <button className="px-3 py-1.5 rounded-lg border border-outline-variant text-on-surface-variant text-xs font-semibold hover:bg-surface-container-low">
                          Reject
                        </button>
                      </form>
                    </td>
                  </tr>
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
            <table className="w-full text-left min-w-[760px]">
              <thead>
                <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                  <th className={thClass}>Date</th>
                  <th className={thClass}>Merchant</th>
                  <th className={thClass}>Destination</th>
                  <th className={thClass}>Method</th>
                  <th className={thClass}>Amount</th>
                  <th className={thClass}>Provider Ref</th>
                  <th className={thClass}>Status</th>
                </tr>
              </thead>
              <tbody className="text-sm">
                {filtered.map((row) => (
                  <tr key={row.withdrawal_id} className="border-t border-surface-container-highest">
                    <td className={`${tdClass} text-on-surface-variant text-xs`}>{formatDateTime(row.created_at)}</td>
                    <td className={`${tdClass} font-medium text-on-background`}>{row.merchant_name}</td>
                    <td className={tdClass}>{row.destination}</td>
                    <td className={`${tdClass} text-on-surface-variant`}>{DISBURSEMENT_METHOD_LABELS[row.method]}</td>
                    <td className={`${tdClass} font-semibold text-on-background`}>{formatCurrency(row.amount, row.currency)}</td>
                    <td className={`${tdClass} text-on-surface-variant text-xs font-mono`}>{row.provider_reference ?? "—"}</td>
                    <td className={tdClass}>
                      <StatusBadge {...adminWithdrawalBadge(row.status)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
