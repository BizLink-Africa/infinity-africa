"use client";

import Link from "next/link";

import { tdClass, thClass } from "@/components/portal/card";
import { OnboardingReviewActions } from "@/components/super-admin/onboarding-review-actions";
import { StatusBadge, type BadgeTone } from "@/components/portal/status-badge";
import { formatDateTime } from "@/lib/format";
import type { OnboardingSubmission } from "@/lib/onboarding/types";
import { ACCOUNT_STATUS_LABELS, AccountStatus, DOCUMENT_UPLOAD_STATUS_LABELS, SERVICE_NEEDED_LABELS } from "@infinity/shared";

const ACCOUNT_TONE: Record<AccountStatus, BadgeTone> = {
  [AccountStatus.PENDING_VERIFICATION]: "pending",
  [AccountStatus.VERIFIED]: "positive-solid",
  [AccountStatus.REJECTED]: "negative",
  [AccountStatus.INFO_REQUESTED]: "info",
};

const DOCUMENT_TONE: Record<string, BadgeTone> = {
  UPLOADED: "pending",
  VERIFIED: "positive",
  REJECTED: "negative",
};

export function OnboardingTable({ rows }: { rows: OnboardingSubmission[] }) {
  if (rows.length === 0) {
    return <p className="p-6 text-sm text-on-surface-variant">No onboarding submissions yet.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left min-w-[1100px]">
        <thead>
          <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
            <th className={thClass}>Business Name</th>
            <th className={thClass}>Owner Email</th>
            <th className={thClass}>Contact Phone</th>
            <th className={thClass}>Nature of Business</th>
            <th className={thClass}>Physical Address</th>
            <th className={thClass}>Services Needed</th>
            <th className={thClass}>Document Status</th>
            <th className={thClass}>Account Status</th>
            <th className={`${thClass} text-right`}>Actions</th>
          </tr>
        </thead>
        <tbody className="text-sm">
          {rows.map((row) => (
            <tr key={row.id} className="border-t border-surface-container-highest align-top">
              <td className={tdClass}>
                <div className="font-medium text-on-background">{row.business_name}</div>
                {row.merchant_code && (
                  <div className="font-mono text-xs text-on-surface-variant">{row.merchant_code}</div>
                )}
              </td>
              <td className={`${tdClass} text-on-surface-variant`}>{row.owner_email}</td>
              <td className={`${tdClass} text-on-surface-variant`}>{row.contact_phone ?? "—"}</td>
              <td className={`${tdClass} text-on-surface-variant`}>{row.nature_of_business}</td>
              <td className={`${tdClass} text-on-surface-variant`}>
                {row.physical_address}, {row.region_city}
              </td>
              <td className={tdClass}>
                <div className="flex flex-wrap gap-1 max-w-[220px]">
                  {row.services_needed.map((service) => (
                    <span
                      key={service}
                      className="inline-flex items-center rounded-full bg-surface-container-highest px-2 py-0.5 text-[11px] font-medium text-on-surface-variant"
                    >
                      {SERVICE_NEEDED_LABELS[service]}
                    </span>
                  ))}
                </div>
              </td>
              <td className={tdClass}>
                <StatusBadge label={DOCUMENT_UPLOAD_STATUS_LABELS[row.document_status]} tone={DOCUMENT_TONE[row.document_status]} />
              </td>
              <td className={tdClass}>
                <StatusBadge label={ACCOUNT_STATUS_LABELS[row.review_status]} tone={ACCOUNT_TONE[row.review_status]} />
                <p className="mt-1 text-[11px] text-outline">{formatDateTime(row.submitted_at)}</p>
              </td>
              <td className={`${tdClass} text-right`}>
                <div className="flex flex-col items-end gap-2">
                  <Link
                    href={`/super-admin/onboarding/${row.id}`}
                    className="text-xs font-semibold text-primary-container hover:underline"
                  >
                    View
                  </Link>
                  <OnboardingReviewActions submissionId={row.id} variant="compact" />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
