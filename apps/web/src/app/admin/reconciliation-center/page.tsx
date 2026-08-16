"use client";

import { useEffect, useState } from "react";

import { AdminKpiCard } from "@/components/admin/kpi-card";
import { Card, tdClass, thClass } from "@/components/portal/card";
import { Icon } from "@/components/portal/icon";
import { PageHeader } from "@/components/portal/page-header";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatCurrency, formatDateTime } from "@/lib/format";
import {
  listDuplicateReferences,
  listFailedCallbacks,
  listProviderCallbackLogs,
  listUnmatchedTransactions,
  retryFailedCallback,
} from "@/lib/admin/api";
import { callbackMatchStatusBadge } from "@/lib/admin/status-tones";
import type { DuplicateReferenceRow, FailedCallbackRow, ProviderCallbackLogRow, UnmatchedTransactionRow } from "@/lib/admin/types";

export default function ReconciliationCenterPage() {
  const [failedCallbacks, setFailedCallbacks] = useState<FailedCallbackRow[]>([]);
  const [unmatched, setUnmatched] = useState<UnmatchedTransactionRow[]>([]);
  const [duplicates, setDuplicates] = useState<DuplicateReferenceRow[]>([]);
  const [callbackLogs, setCallbackLogs] = useState<ProviderCallbackLogRow[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    listFailedCallbacks().then(setFailedCallbacks);
    listUnmatchedTransactions().then(setUnmatched);
    listDuplicateReferences().then(setDuplicates);
    listProviderCallbackLogs().then(setCallbackLogs);
  }, []);

  async function handleRetry(row: FailedCallbackRow) {
    setBusyId(row.id);
    try {
      await retryFailedCallback(row.id);
      setFailedCallbacks((prev) => prev.filter((r) => r.id !== row.id));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader title="Reconciliation Center" description="Match provider callbacks against platform transactions and resolve exceptions." />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
        <AdminKpiCard icon="check_circle" label="Auto-Matched Today" value="3,842" />
        <AdminKpiCard icon="help" label="Unmatched Transactions" value={unmatched.length.toLocaleString()} />
        <AdminKpiCard icon="content_copy" label="Duplicate References" value={duplicates.length.toLocaleString()} />
        <AdminKpiCard icon="error" label="Failed Callbacks" value={failedCallbacks.length.toLocaleString()} />
      </div>

      {failedCallbacks.length > 0 && (
        <Card className="border-red-200" padded={false}>
          <div className="p-5 pb-3 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Icon name="error" className="text-error" />
              <h3 className="text-xl font-semibold text-on-background">Failed Callback Queue</h3>
            </div>
            <span className="bg-red-100 text-red-700 px-2.5 py-1 rounded-full text-xs font-semibold">{failedCallbacks.length} failed</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left min-w-[760px]">
              <thead>
                <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                  <th className={thClass}>Provider</th>
                  <th className={thClass}>Event Type</th>
                  <th className={thClass}>Reference</th>
                  <th className={thClass}>Received At</th>
                  <th className={thClass}>Error</th>
                  <th className={`${thClass} text-right`}>Actions</th>
                </tr>
              </thead>
              <tbody className="text-sm">
                {failedCallbacks.map((row) => (
                  <tr key={row.id} className="border-t border-surface-container-highest">
                    <td className={`${tdClass} font-medium text-on-background`}>{row.provider}</td>
                    <td className={`${tdClass} font-mono text-xs`}>{row.event_type}</td>
                    <td className={`${tdClass} font-mono text-xs`}>{row.reference}</td>
                    <td className={`${tdClass} text-on-surface-variant text-xs`}>{formatDateTime(row.received_at)}</td>
                    <td className={`${tdClass} text-error text-sm`}>{row.error}</td>
                    <td className={`${tdClass} text-right whitespace-nowrap`}>
                      <button
                        disabled={busyId === row.id}
                        onClick={() => handleRetry(row)}
                        className="inline-flex items-center gap-1 bg-primary-container text-on-primary text-xs font-semibold px-3 py-1.5 rounded-lg hover:opacity-90 disabled:opacity-60 mr-2"
                      >
                        <Icon name="refresh" className="text-[14px]" />
                        Retry
                      </button>
                      <button className="border border-outline-variant text-on-surface-variant text-xs font-semibold px-3 py-1.5 rounded-lg hover:bg-surface-container-low">
                        Manual Review
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Card padded={false}>
        <div className="p-5 pb-1">
          <h3 className="text-xl font-semibold text-on-background">Unmatched Transactions</h3>
          <p className="text-sm text-on-surface-variant mt-0.5">Provider callbacks that don&apos;t match any known transaction reference.</p>
        </div>
        <div className="overflow-x-auto mt-2">
          <table className="w-full text-left min-w-[600px]">
            <thead>
              <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                <th className={thClass}>Reference</th>
                <th className={thClass}>Provider</th>
                <th className={thClass}>Amount</th>
                <th className={thClass}>Received At</th>
                <th className={`${thClass} text-right`}>Actions</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {unmatched.map((row) => (
                <tr key={row.id} className="border-t border-surface-container-highest">
                  <td className={`${tdClass} font-mono text-xs text-on-background`}>{row.reference}</td>
                  <td className={`${tdClass} text-on-surface-variant`}>{row.provider}</td>
                  <td className={`${tdClass} font-semibold text-on-background`}>{formatCurrency(row.amount, "TZS")}</td>
                  <td className={`${tdClass} text-on-surface-variant text-xs`}>{formatDateTime(row.received_at)}</td>
                  <td className={`${tdClass} text-right`}>
                    <button className="border border-outline-variant text-on-surface-variant text-xs font-semibold px-3 py-1.5 rounded-lg hover:bg-surface-container-low">
                      Manual Review
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card padded={false}>
        <div className="p-5 pb-1">
          <h3 className="text-xl font-semibold text-on-background">Duplicate References</h3>
          <p className="text-sm text-on-surface-variant mt-0.5">The same provider reference was received more than once.</p>
        </div>
        <div className="overflow-x-auto mt-2">
          <table className="w-full text-left min-w-[600px]">
            <thead>
              <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                <th className={thClass}>Reference</th>
                <th className={thClass}>Occurrences</th>
                <th className={thClass}>First Seen</th>
                <th className={thClass}>Last Seen</th>
                <th className={`${thClass} text-right`}>Actions</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {duplicates.map((row) => (
                <tr key={row.id} className="border-t border-surface-container-highest">
                  <td className={`${tdClass} font-mono text-xs text-on-background`}>{row.reference}</td>
                  <td className={tdClass}>
                    <span className="bg-amber-100 text-amber-700 px-2.5 py-1 rounded-full text-xs font-semibold">{row.occurrences}×</span>
                  </td>
                  <td className={`${tdClass} text-on-surface-variant text-xs`}>{formatDateTime(row.first_seen)}</td>
                  <td className={`${tdClass} text-on-surface-variant text-xs`}>{formatDateTime(row.last_seen)}</td>
                  <td className={`${tdClass} text-right`}>
                    <button className="border border-outline-variant text-on-surface-variant text-xs font-semibold px-3 py-1.5 rounded-lg hover:bg-surface-container-low">
                      Manual Review
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card padded={false}>
        <div className="p-5 pb-1">
          <h3 className="text-xl font-semibold text-on-background">Provider Callback Logs</h3>
          <p className="text-sm text-on-surface-variant mt-0.5">Raw inbound webhook events from all payment providers.</p>
        </div>
        <div className="overflow-x-auto mt-2">
          <table className="w-full text-left min-w-[760px]">
            <thead>
              <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                <th className={thClass}>Timestamp</th>
                <th className={thClass}>Provider</th>
                <th className={thClass}>Event</th>
                <th className={thClass}>Reference</th>
                <th className={thClass}>HTTP</th>
                <th className={thClass}>Match Status</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {callbackLogs.map((row) => (
                <tr key={row.id} className="border-t border-surface-container-highest">
                  <td className={`${tdClass} font-mono text-xs`}>{row.timestamp.replace("T", " ").slice(0, 19)}</td>
                  <td className={`${tdClass} text-on-surface-variant`}>{row.provider}</td>
                  <td className={`${tdClass} font-mono text-xs`}>{row.event}</td>
                  <td className={`${tdClass} font-mono text-xs`}>{row.reference}</td>
                  <td className={`${tdClass} font-mono text-sm ${row.http_status < 400 ? "text-primary" : "text-error"}`}>{row.http_status}</td>
                  <td className={tdClass}>
                    <StatusBadge {...callbackMatchStatusBadge(row.match_status)} />
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
