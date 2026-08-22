"use client";

import { useState } from "react";

/** The subset of a refreshed collection this button needs to report a
 * result — deliberately loose so it works for both the merchant
 * (Collection) and Super Admin (AdminCollectionRow) shapes. */
export interface RefreshableCollectionStatus {
  status: string;
  provider_payment_status?: string | null;
  failure_reason?: string | null;
}

function describeResult(result: RefreshableCollectionStatus): { tone: "success" | "pending" | "failed"; text: string } {
  if (result.status === "successful") {
    return { tone: "success", text: "Payment completed" };
  }
  if (result.status === "processing") {
    return { tone: "pending", text: "Payment still pending with Selcom" };
  }

  const providerStatus = result.provider_payment_status;
  let text = "Payment failed";
  if (providerStatus === "CANCELLED") text = "Payment cancelled";
  else if (providerStatus === "USERCANCELLED") text = "Payment cancelled by customer";
  else if (providerStatus === "REJECTED") text = "Payment rejected";

  if (result.failure_reason) text = `${text}: ${result.failure_reason}`;
  return { tone: "failed", text };
}

/** "Refresh status" button for a single pending/processing collection —
 * calls the caller-supplied refresh function (merchant or admin
 * endpoint), then reports the outcome inline. Backend idempotency
 * (app/services/checkout_reconciliation.py::complete_checkout_collection_once)
 * means clicking this repeatedly never double-credits the merchant.
 * Generic over T so callers can pass through their own full row type
 * (Collection, AdminCollectionRow, ...) without it being narrowed away. */
export function RefreshStatusButton<T extends RefreshableCollectionStatus>({
  onRefresh,
  onResult,
}: {
  onRefresh: () => Promise<T>;
  onResult: (result: T) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ tone: "success" | "pending" | "failed" | "error"; text: string } | null>(
    null,
  );

  async function handleClick() {
    setLoading(true);
    setMessage(null);
    try {
      const result = await onRefresh();
      onResult(result);
      setMessage(describeResult(result));
    } catch (err) {
      setMessage({ tone: "error", text: err instanceof Error ? err.message : "Couldn't check payment status." });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="inline-flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={handleClick}
        disabled={loading}
        className="px-3 py-1.5 rounded-lg border border-outline-variant text-on-surface-variant text-xs font-semibold hover:bg-surface-container-low disabled:opacity-60 whitespace-nowrap"
      >
        {loading ? "Checking payment status…" : "Refresh status"}
      </button>
      {message && (
        <span
          className={
            message.tone === "success"
              ? "text-xs text-green-600"
              : message.tone === "failed" || message.tone === "error"
                ? "text-xs text-error"
                : "text-xs text-on-surface-variant"
          }
        >
          {message.text}
        </span>
      )}
    </div>
  );
}
