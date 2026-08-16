"use client";

import Link from "next/link";

import { tdClass, thClass } from "@/components/portal/card";
import { StatusBadge, type BadgeTone } from "@/components/portal/status-badge";
import { formatDateTime } from "@/lib/format";
import {
  approveOnboardingAction,
  rejectOnboardingAction,
  requestInfoOnboardingAction,
} from "@/lib/onboarding/admin-actions";
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
              <td className={`${tdClass} font-medium text-on-background`}>{row.business_name}</td>
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
                  <form className="flex flex-col items-end gap-1.5">
                    <input
                      type="text"
                      name="note"
                      placeholder="Note (optional)"
                      className="w-40 rounded-lg border border-outline-variant bg-transparent px-2 py-1 text-xs text-on-surface placeholder-outline focus:outline-none focus:border-primary-container"
                    />
                    <div className="flex gap-1.5">
                      <button
                        formAction={approveOnboardingAction.bind(null, row.id)}
                        className="px-2.5 py-1 rounded-lg bg-primary-container text-on-primary text-xs font-semibold hover:opacity-90"
                      >
                        Approve
                      </button>
                      <button
                        formAction={rejectOnboardingAction.bind(null, row.id)}
                        className="px-2.5 py-1 rounded-lg border border-outline-variant text-on-surface-variant text-xs font-semibold hover:bg-surface-container-low"
                      >
                        Reject
                      </button>
                      <button
                        formAction={requestInfoOnboardingAction.bind(null, row.id)}
                        className="px-2.5 py-1 rounded-lg border border-outline-variant text-on-surface-variant text-xs font-semibold hover:bg-surface-container-low"
                      >
                        Request Info
                      </button>
                    </div>
                  </form>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
