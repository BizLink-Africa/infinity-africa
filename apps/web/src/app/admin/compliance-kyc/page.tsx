"use client";

import { useEffect, useState } from "react";

import { AdminKpiCard } from "@/components/admin/kpi-card";
import { Card, tdClass, thClass } from "@/components/portal/card";
import { PageHeader } from "@/components/portal/page-header";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatDateTime } from "@/lib/format";
import { approveKyc, listComplianceFlags, listKycQueue, rejectKyc } from "@/lib/admin/api";
import { riskLevelBadge } from "@/lib/admin/status-tones";
import type { ComplianceFlagRow, KycReviewRow } from "@/lib/admin/types";

function initials(name: string): string {
  return name
    .split(" ")
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export default function ComplianceKycPage() {
  const [queue, setQueue] = useState<KycReviewRow[]>([]);
  const [flags, setFlags] = useState<ComplianceFlagRow[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    listKycQueue().then(setQueue);
    listComplianceFlags().then(setFlags);
  }, []);

  async function handleApprove(review: KycReviewRow) {
    setBusyId(review.id);
    try {
      await approveKyc(review.id);
      setQueue((prev) => prev.filter((row) => row.id !== review.id));
    } finally {
      setBusyId(null);
    }
  }

  async function handleReject(review: KycReviewRow) {
    setBusyId(review.id);
    try {
      await rejectKyc(review.id);
      setQueue((prev) => prev.filter((row) => row.id !== review.id));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader title="Compliance/KYC" description="Review merchant identity verification and regulatory compliance status." />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <AdminKpiCard icon="verified_user" label="Verified Merchants" value="1,158" />
        <AdminKpiCard icon="hourglass_empty" label="Pending Review" value={queue.length.toLocaleString()} />
        <AdminKpiCard icon="flag" label="Flagged" value={flags.length.toLocaleString()} />
        <AdminKpiCard icon="block" label="Rejected" value="6" />
      </div>

      <Card padded={false}>
        <div className="p-5 pb-3">
          <h3 className="text-2xl font-semibold text-on-background">Pending KYC Review Queue</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left min-w-[680px]">
            <thead>
              <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                <th className={thClass}>Merchant</th>
                <th className={thClass}>Document Type</th>
                <th className={thClass}>Submitted Date</th>
                <th className={thClass}>Status</th>
                <th className={`${thClass} text-right`}>Actions</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {queue.map((review) => (
                <tr key={review.id} className="border-t border-surface-container-highest">
                  <td className={tdClass}>
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-primary-container/15 text-primary flex items-center justify-center font-bold text-xs shrink-0">
                        {initials(review.merchant_name)}
                      </div>
                      <span className="font-medium text-on-background">{review.merchant_name}</span>
                    </div>
                  </td>
                  <td className={`${tdClass} text-on-surface-variant`}>{review.document_type}</td>
                  <td className={`${tdClass} text-on-surface-variant text-xs`}>{formatDateTime(review.submitted_at)}</td>
                  <td className={tdClass}>
                    <StatusBadge label="Pending Review" tone="pending" />
                  </td>
                  <td className={`${tdClass} text-right whitespace-nowrap`}>
                    <button
                      disabled={busyId === review.id}
                      onClick={() => handleApprove(review)}
                      className="px-3 py-1.5 rounded-lg bg-primary-container text-on-primary text-xs font-semibold hover:opacity-90 disabled:opacity-60 mr-2"
                    >
                      Approve
                    </button>
                    <button
                      disabled={busyId === review.id}
                      onClick={() => handleReject(review)}
                      className="px-3 py-1.5 rounded-lg border border-outline-variant text-on-surface-variant text-xs font-semibold hover:bg-surface-container-low disabled:opacity-60"
                    >
                      Reject
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card padded={false}>
        <div className="p-5 pb-3">
          <h3 className="text-2xl font-semibold text-on-background">Flagged for Compliance Review</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left min-w-[680px]">
            <thead>
              <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                <th className={thClass}>Merchant</th>
                <th className={thClass}>Reason</th>
                <th className={thClass}>Flagged Date</th>
                <th className={thClass}>Risk Level</th>
                <th className={`${thClass} text-right`}>Actions</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {flags.map((flag) => (
                <tr key={flag.id} className="border-t border-surface-container-highest">
                  <td className={tdClass}>
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-primary-container/15 text-primary flex items-center justify-center font-bold text-xs shrink-0">
                        {initials(flag.merchant_name)}
                      </div>
                      <span className="font-medium text-on-background">{flag.merchant_name}</span>
                    </div>
                  </td>
                  <td className={`${tdClass} text-on-surface-variant text-sm`}>{flag.reason}</td>
                  <td className={`${tdClass} text-on-surface-variant text-xs`}>{formatDateTime(flag.flagged_at)}</td>
                  <td className={tdClass}>
                    <StatusBadge {...riskLevelBadge(flag.risk_level)} />
                  </td>
                  <td className={`${tdClass} text-right`}>
                    <button className="bg-surface border border-outline-variant text-on-surface-variant text-xs font-semibold px-3 py-1.5 rounded-lg hover:bg-surface-container-low">
                      Investigate
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
