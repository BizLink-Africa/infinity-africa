"use client";

import { Fragment, useState } from "react";

import { Card, tdClass, thClass } from "@/components/portal/card";
import { Icon } from "@/components/portal/icon";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatDateTime } from "@/lib/format";
import { approveDocumentRequestAction, rejectDocumentRequestAction } from "@/lib/admin/live-actions";
import type { AdminDocumentRequestRow } from "@/lib/admin/types";

export function DocumentRequestsTable({ rows }: { rows: AdminDocumentRequestRow[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <Card padded={false}>
      <div className="p-5 pb-3">
        <h3 className="text-2xl font-semibold text-on-background">Document Requests</h3>
      </div>
      {rows.length === 0 ? (
        <p className="p-6 text-sm text-on-surface-variant">No document requests have been made.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left min-w-[900px]">
            <thead>
              <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                <th className={thClass}>Merchant</th>
                <th className={thClass}>Requested</th>
                <th className={thClass}>Due</th>
                <th className={thClass}>Status</th>
                <th className={thClass}>Submitted Files</th>
                <th className={`${thClass} text-right`}>Actions</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {rows.map((request) => (
                <Fragment key={request.request_id}>
                  <tr className="border-t border-surface-container-highest">
                    <td className={`${tdClass} font-medium text-on-background`}>{request.merchant_name ?? "—"}</td>
                    <td className={tdClass}>{request.requested_documents.join(", ")}</td>
                    <td className={`${tdClass} text-on-surface-variant text-xs`}>{request.due_date ? formatDateTime(request.due_date) : "—"}</td>
                    <td className={tdClass}>
                      <StatusBadge
                        label={request.status}
                        tone={request.status === "APPROVED" ? "positive" : request.status === "REJECTED" ? "negative" : "pending"}
                      />
                    </td>
                    <td className={tdClass}>{request.files.length}</td>
                    <td className={`${tdClass} text-right`}>
                      <button
                        onClick={() => setExpanded(expanded === request.request_id ? null : request.request_id)}
                        className="inline-flex items-center gap-1 text-primary text-xs font-semibold hover:underline"
                      >
                        {expanded === request.request_id ? "Hide" : "View"}
                        <Icon name={expanded === request.request_id ? "expand_less" : "expand_more"} className="text-[16px]" />
                      </button>
                    </td>
                  </tr>
                  {expanded === request.request_id && (
                    <tr className="border-t border-surface-container-highest">
                      <td colSpan={6} className="p-0">
                        <div className="p-5 bg-surface-container-low space-y-4">
                          <p className="text-sm text-on-surface">{request.reason}</p>
                          {request.files.length === 0 ? (
                            <p className="text-xs text-on-surface-variant">No files submitted yet.</p>
                          ) : (
                            <ul className="space-y-1">
                              {request.files.map((file) => (
                                <li key={file.id} className="text-xs">
                                  {file.signed_url ? (
                                    <a href={file.signed_url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
                                      {file.original_filename} ({file.document_label})
                                    </a>
                                  ) : (
                                    <span>{file.original_filename} ({file.document_label})</span>
                                  )}
                                </li>
                              ))}
                            </ul>
                          )}
                          {request.status === "SUBMITTED" && (
                            <div className="flex gap-2">
                              <form action={approveDocumentRequestAction.bind(null, request.request_id)}>
                                <button className="bg-primary-container text-on-primary text-xs font-semibold py-2 px-4 rounded-lg hover:opacity-90">
                                  Approve
                                </button>
                              </form>
                              <form action={rejectDocumentRequestAction.bind(null, request.request_id)}>
                                <button className="border border-outline-variant text-on-surface-variant text-xs font-semibold py-2 px-4 rounded-lg hover:bg-surface-container-highest">
                                  Reject
                                </button>
                              </form>
                            </div>
                          )}
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
