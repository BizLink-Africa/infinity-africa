"use client";

import { useState } from "react";

import { Card, tdClass, thClass } from "@/components/portal/card";
import { RefreshStatusButton } from "@/components/portal/refresh-status-button";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatCurrency, formatDateTime } from "@/lib/format";
import { refreshAdminCollectionStatusClient } from "@/lib/admin/refresh-collection-status-client";
import { adminCollectionBadge } from "@/lib/admin/status-tones";
import type { AdminCollectionRow } from "@/lib/admin/types";

export function CollectionsTable({ collections: initialCollections }: { collections: AdminCollectionRow[] }) {
  const [collections, setCollections] = useState(initialCollections);
  // Once a collection has been manually refreshed, keep showing the
  // button + its result message even after the status flips away from
  // pending/processing — otherwise the row re-renders as resolved and
  // the outcome message (e.g. "Payment completed") never gets seen.
  const [refreshedIds, setRefreshedIds] = useState<Set<string>>(new Set());

  return (
    <Card padded={false}>
      <div className="p-5 pb-3">
        <h3 className="text-2xl font-semibold text-on-background">All Collections</h3>
      </div>
      {collections.length === 0 ? (
        <p className="p-6 text-sm text-on-surface-variant">No collections have been recorded yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left min-w-[1100px]">
            <thead>
              <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                <th className={thClass}>Merchant</th>
                <th className={thClass}>Phone</th>
                <th className={thClass}>Method / Channel</th>
                <th className={thClass}>Amount</th>
                <th className={thClass}>Order / Reference</th>
                <th className={thClass}>Status</th>
                <th className={thClass}>Date</th>
                <th className={`${thClass} text-right`}>Actions</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {collections.map((row) => {
                const needsRefresh =
                  row.status === "pending" || row.status === "processing" || refreshedIds.has(row.collection_id);
                return (
                  <tr key={row.collection_id} className="border-t border-surface-container-highest">
                    <td className={`${tdClass} text-on-background font-medium`}>{row.merchant_name}</td>
                    <td className={tdClass}>{row.phone ?? "—"}</td>
                    <td className={`${tdClass} text-on-surface-variant`}>
                      <div>{row.method}</div>
                      {row.channel && <div className="text-xs">{row.channel}</div>}
                    </td>
                    <td className={`${tdClass} font-semibold text-on-background`}>{formatCurrency(row.amount, row.currency)}</td>
                    <td className={`${tdClass} text-on-surface-variant text-xs font-mono`}>
                      {row.order_id && <div>{row.order_id}</div>}
                      {row.provider_transid && <div>{row.provider_transid}</div>}
                      {!row.order_id && !row.provider_transid && "—"}
                    </td>
                    <td className={tdClass}>
                      <StatusBadge {...adminCollectionBadge(row.status)} />
                      {row.status === "failed" && (row.failure_reason || row.provider_payment_status) && (
                        <p className="text-xs text-on-surface-variant mt-1">
                          {row.failure_reason ?? row.provider_payment_status}
                        </p>
                      )}
                    </td>
                    <td className={`${tdClass} text-on-surface-variant text-xs`}>{formatDateTime(row.created_at)}</td>
                    <td className={`${tdClass} text-right`}>
                      {needsRefresh && (
                        <RefreshStatusButton
                          onRefresh={() => refreshAdminCollectionStatusClient(row.collection_id)}
                          onResult={(result) => {
                            setRefreshedIds((prev) => new Set(prev).add(row.collection_id));
                            setCollections((prev) =>
                              prev.map((c) => (c.collection_id === row.collection_id ? result : c)),
                            );
                          }}
                        />
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
  );
}
