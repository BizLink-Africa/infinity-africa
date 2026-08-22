"use client";

import { useEffect, useState } from "react";
import { COLLECTION_METHOD_LABELS, CollectionMethod } from "@infinity/shared";

import { Card, tdClass, thClass } from "@/components/portal/card";
import { Icon } from "@/components/portal/icon";
import { PageHeader } from "@/components/portal/page-header";
import { RefreshStatusButton } from "@/components/portal/refresh-status-button";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatCurrency, formatDateTime } from "@/lib/format";
import { createCollection, listCollections, refreshCollectionStatus } from "@/lib/portal/api";
import { collectionBadge } from "@/lib/portal/status-tones";
import type { Collection } from "@/lib/portal/types";

const METHODS = Object.values(CollectionMethod);

export default function CollectionsPage() {
  const [collections, setCollections] = useState<Collection[]>([]);
  // Once a collection has been manually refreshed, keep showing the
  // button + its result message even after the status flips away from
  // "processing" — otherwise the row re-renders as resolved and the
  // outcome message (e.g. "Payment completed") never gets seen.
  const [refreshedIds, setRefreshedIds] = useState<Set<string>>(new Set());
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState<CollectionMethod>(CollectionMethod.STK_PUSH);
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    listCollections().then(setCollections);
  }, []);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!customerName || !customerPhone || !amount) return;

    setSubmitting(true);
    try {
      const collection = await createCollection({
        customer_name: customerName,
        customer_phone: customerPhone,
        amount,
        method,
        description: description || null,
      });
      setCollections((prev) => [collection, ...prev]);
      setCustomerName("");
      setCustomerPhone("");
      setAmount("");
      setDescription("");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader title="Collections" description="Request one-off payments from customers via mobile money." />

      <Card id="create-collection" className="scroll-mt-24">
        <h3 className="text-2xl font-semibold text-on-background mb-5">Create Collection</h3>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1.5" htmlFor="cust-name">
                Customer Name
              </label>
              <input
                id="cust-name"
                className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary text-sm"
                placeholder="e.g. Grace Mwakalinga"
                type="text"
                value={customerName}
                onChange={(event) => setCustomerName(event.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1.5" htmlFor="cust-phone">
                Phone Number
              </label>
              <input
                id="cust-phone"
                className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary text-sm"
                placeholder="+255 7XX XXX XXX"
                type="tel"
                value={customerPhone}
                onChange={(event) => setCustomerPhone(event.target.value)}
              />
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1.5" htmlFor="cust-amount">
                Amount in TZS
              </label>
              <div className="relative">
                <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-on-surface-variant text-sm font-semibold">
                  TZS
                </span>
                <input
                  id="cust-amount"
                  className="w-full pl-12 pr-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary text-sm"
                  placeholder="50,000"
                  type="number"
                  min="1"
                  value={amount}
                  onChange={(event) => setAmount(event.target.value)}
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1.5" htmlFor="cust-channel">
                Channel
              </label>
              <select
                id="cust-channel"
                className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary text-sm"
                value={method}
                onChange={(event) => setMethod(event.target.value as CollectionMethod)}
              >
                {METHODS.map((m) => (
                  <option key={m} value={m}>
                    {COLLECTION_METHOD_LABELS[m]}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-on-surface-variant mb-1.5" htmlFor="cust-desc">
              Description
            </label>
            <input
              id="cust-desc"
              className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary text-sm"
              placeholder="e.g. Payment for 2 bags of maize flour"
              type="text"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </div>
          <button
            className="w-full sm:w-auto bg-primary-container text-on-primary text-sm font-medium py-3 px-6 rounded-lg hover:opacity-90 transition-opacity flex items-center justify-center gap-2 disabled:opacity-60"
            type="submit"
            disabled={submitting}
          >
            <Icon name="payments" className="text-[20px]" />
            {submitting ? "Requesting…" : "Request Collection"}
          </button>
        </form>
      </Card>

      <Card padded={false}>
        <div className="p-5 pb-3">
          <h3 className="text-2xl font-semibold text-on-background">Recent Collections</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left min-w-[760px]">
            <thead>
              <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                <th className={thClass}>Date</th>
                <th className={thClass}>Customer Phone</th>
                <th className={thClass}>Channel</th>
                <th className={thClass}>Amount</th>
                <th className={thClass}>Status</th>
                <th className={`${thClass} text-right`}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {collections.map((collection) => {
                const badge = collectionBadge(collection.status);
                const needsRefresh = collection.status === "processing" || refreshedIds.has(collection.id);
                return (
                  <tr key={collection.id} className="border-t border-surface-container-highest">
                    <td className={tdClass}>{formatDateTime(collection.initiated_at)}</td>
                    <td className={tdClass}>{collection.customer_phone}</td>
                    <td className={tdClass}>{collection.channel ?? COLLECTION_METHOD_LABELS[collection.method]}</td>
                    <td className={tdClass}>{formatCurrency(collection.amount, collection.currency)}</td>
                    <td className={tdClass}>
                      <StatusBadge {...badge} />
                      {collection.status === "failed" && collection.failure_reason && (
                        <p className="text-xs text-on-surface-variant mt-1">{collection.failure_reason}</p>
                      )}
                    </td>
                    <td className={`${tdClass} text-right`}>
                      {needsRefresh && (
                        <RefreshStatusButton
                          onRefresh={() => refreshCollectionStatus(collection.id)}
                          onResult={(result) => {
                            setRefreshedIds((prev) => new Set(prev).add(collection.id));
                            setCollections((prev) =>
                              prev.map((c) => (c.id === collection.id ? { ...c, ...result } : c)),
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
      </Card>
    </div>
  );
}
