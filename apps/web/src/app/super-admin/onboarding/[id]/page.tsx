import { notFound } from "next/navigation";

import { Card } from "@/components/portal/card";
import { PageHeader } from "@/components/portal/page-header";
import { StatusBadge, type BadgeTone } from "@/components/portal/status-badge";
import { formatDateTime } from "@/lib/format";
import { getOnboardingSubmission } from "@/lib/onboarding/api";
import {
  approveOnboardingAction,
  rejectOnboardingAction,
  requestInfoOnboardingAction,
} from "@/lib/onboarding/admin-actions";
import {
  ACCOUNT_STATUS_LABELS,
  AccountStatus,
  DOCUMENT_TYPE_LABELS,
  DOCUMENT_UPLOAD_STATUS_LABELS,
  SERVICE_NEEDED_LABELS,
} from "@infinity/shared";

const ACCOUNT_TONE: Record<AccountStatus, BadgeTone> = {
  [AccountStatus.PENDING_VERIFICATION]: "pending",
  [AccountStatus.VERIFIED]: "positive-solid",
  [AccountStatus.REJECTED]: "negative",
  [AccountStatus.INFO_REQUESTED]: "info",
};

export default async function OnboardingDetailPage(props: PageProps<"/super-admin/onboarding/[id]">) {
  const { id } = await props.params;
  const submission = await getOnboardingSubmission(id);

  if (!submission) notFound();

  return (
    <div className="space-y-8">
      <PageHeader
        title={submission.business_name}
        description={`Submitted ${formatDateTime(submission.submitted_at)}`}
        action={<StatusBadge label={ACCOUNT_STATUS_LABELS[submission.review_status]} tone={ACCOUNT_TONE[submission.review_status]} dot />}
      />

      <Card>
        <h3 className="text-lg font-semibold text-on-surface mb-4">Business Details</h3>
        <dl className="grid sm:grid-cols-2 gap-5 text-sm">
          <div>
            <dt className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide">Owner Email</dt>
            <dd className="mt-1 text-on-surface">{submission.owner_email}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide">Contact Phone</dt>
            <dd className="mt-1 text-on-surface">{submission.contact_phone ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide">Business Category</dt>
            <dd className="mt-1 text-on-surface">{submission.business_category}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide">Nature of Business</dt>
            <dd className="mt-1 text-on-surface">{submission.nature_of_business}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide">Address</dt>
            <dd className="mt-1 text-on-surface">
              {submission.physical_address}, {submission.region_city}
            </dd>
          </div>
          {submission.website_url && (
            <div>
              <dt className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide">Website / App Link</dt>
              <dd className="mt-1 text-on-surface">{submission.website_url}</dd>
            </div>
          )}
          <div>
            <dt className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide">Services Needed</dt>
            <dd className="mt-1 flex flex-wrap gap-1.5">
              {submission.services_needed.map((service) => (
                <span
                  key={service}
                  className="inline-flex items-center rounded-full bg-surface-container-highest px-2.5 py-1 text-xs font-medium text-on-surface-variant"
                >
                  {SERVICE_NEEDED_LABELS[service]}
                </span>
              ))}
            </dd>
          </div>
        </dl>
      </Card>

      <Card>
        <h3 className="text-lg font-semibold text-on-surface mb-4">Compliance Documents</h3>
        <ul className="space-y-3">
          {submission.documents.length === 0 && <p className="text-sm text-on-surface-variant">No documents uploaded yet.</p>}
          {submission.documents.map((doc) => (
            <li
              key={doc.id}
              className="flex items-center justify-between text-sm border-b border-surface-container-highest pb-3 last:border-0 last:pb-0"
            >
              <div>
                <p className="font-medium text-on-surface">{DOCUMENT_TYPE_LABELS[doc.document_type]}</p>
                <p className="text-xs text-on-surface-variant">
                  {doc.signed_url ? (
                    <a href={doc.signed_url} target="_blank" rel="noreferrer" className="text-primary-container hover:underline">
                      {doc.original_filename}
                    </a>
                  ) : (
                    doc.original_filename
                  )}
                </p>
              </div>
              <StatusBadge
                label={DOCUMENT_UPLOAD_STATUS_LABELS[doc.upload_status]}
                tone={doc.upload_status === "VERIFIED" ? "positive" : doc.upload_status === "REJECTED" ? "negative" : "pending"}
              />
            </li>
          ))}
        </ul>
      </Card>

      {submission.review_note && (
        <Card>
          <h3 className="text-lg font-semibold text-on-surface mb-2">Latest Review Note</h3>
          <p className="text-sm text-on-surface-variant">{submission.review_note}</p>
        </Card>
      )}

      <Card>
        <h3 className="text-lg font-semibold text-on-surface mb-4">Actions</h3>
        <form className="space-y-3">
          <textarea
            name="note"
            rows={3}
            placeholder="Add a note (optional) — shown to the merchant for Reject / Request More Info"
            className="w-full rounded-lg border border-outline-variant bg-transparent px-3 py-2 text-sm text-on-surface placeholder-outline focus:outline-none focus:border-primary-container"
          />
          <div className="flex gap-2">
            <button
              formAction={approveOnboardingAction.bind(null, submission.id)}
              className="px-4 py-2 rounded-lg bg-primary-container text-on-primary text-sm font-semibold hover:opacity-90"
            >
              Approve
            </button>
            <button
              formAction={rejectOnboardingAction.bind(null, submission.id)}
              className="px-4 py-2 rounded-lg border border-outline-variant text-on-surface-variant text-sm font-semibold hover:bg-surface-container-low"
            >
              Reject
            </button>
            <button
              formAction={requestInfoOnboardingAction.bind(null, submission.id)}
              className="px-4 py-2 rounded-lg border border-outline-variant text-on-surface-variant text-sm font-semibold hover:bg-surface-container-low"
            >
              Request More Info
            </button>
          </div>
        </form>
      </Card>
    </div>
  );
}
