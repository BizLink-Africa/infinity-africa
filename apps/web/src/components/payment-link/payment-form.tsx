"use client";

import { useState } from "react";

import { formatCurrency, formatDateTime } from "@/lib/format";
import type { PublicPaymentLink } from "@/lib/payment-links";

import { StatusCard } from "./status-card";

interface CheckoutResponseBody {
  success: boolean;
  data?: { collection_id: string; payment_gateway_url: string | null };
  error?: { message: string };
}

/**
 * The single "Pay securely" flow (2026-08-23) — no payment-method choice
 * on Infinity's side. Creates the Selcom order via
 * POST .../pay/checkout, then does a full-page redirect to Selcom's own
 * hosted checkout (payment_gateway_url), which shows whichever methods
 * are enabled on the merchant's Selcom account. Nothing to poll here:
 * the customer leaves this site entirely: if they come back to this
 * same link later, the server-rendered wrapper page
 * (app/pay/[slug]/page.tsx) already shows "Already paid" once the
 * webhook/manual refresh resolves it.
 */
export function PaymentForm({ slug, link }: { slug: string; link: PublicPaymentLink }) {
  const needsPhone = !link.customer_phone;
  const [phone, setPhone] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID());

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (needsPhone && !phone.trim()) return;

    setSubmitting(true);
    setErrorMessage(null);

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/public/payment-links/${slug}/pay/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
        body: JSON.stringify({ customer_phone: needsPhone ? phone.trim() : undefined }),
      });
      const body: CheckoutResponseBody = await response.json();

      if (!response.ok || !body.success || !body.data?.payment_gateway_url) {
        setSubmitting(false);
        setErrorMessage(body.error?.message ?? "Something went wrong. Please try again.");
        return;
      }

      window.location.href = body.data.payment_gateway_url;
    } catch {
      setSubmitting(false);
      setErrorMessage("We couldn't reach Infinity Africa. Check your connection and try again.");
    }
  }

  function handleRetry() {
    // A fresh key — retrying with the same one would just replay the
    // failed result instead of trying again.
    setIdempotencyKey(crypto.randomUUID());
    setErrorMessage(null);
  }

  if (errorMessage) {
    return (
      <StatusCard variant="error" title="Something went wrong" message={errorMessage}>
        <button
          type="button"
          onClick={handleRetry}
          className="mt-5 w-full rounded bg-primary-container px-4 py-3 text-sm font-semibold text-on-primary shadow-sm transition-colors hover:bg-primary"
        >
          Try again
        </button>
      </StatusCard>
    );
  }

  if (submitting) {
    return (
      <StatusCard
        variant="processing"
        title="Redirecting you to checkout"
        message="You're being sent to Selcom's secure hosted checkout. Please don't close this page."
      />
    );
  }

  return (
    <form onSubmit={handleSubmit} className="p-6 sm:p-8">
      <p className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
        Paying {link.merchant_name}
      </p>
      <p className="mt-2 text-3xl font-bold text-on-surface">{formatCurrency(link.amount, link.currency)}</p>

      {link.description && <p className="mt-2 text-sm text-on-surface-variant">{link.description}</p>}

      {(link.customer_name || link.customer_phone) && (
        <p className="mt-3 text-sm text-on-surface-variant">
          For {[link.customer_name, link.customer_phone].filter(Boolean).join(" · ")}
        </p>
      )}

      {link.expires_at && (
        <p className="mt-1 text-xs text-on-surface-variant">Expires {formatDateTime(link.expires_at)}</p>
      )}

      <div className="my-6 border-t border-outline-variant" />

      <p className="rounded border border-dashed border-outline-variant bg-surface-container p-4 text-center text-xs text-on-surface-variant">
        Secure Selcom hosted checkout. You&apos;ll choose your payment method on the checkout page.
      </p>

      {needsPhone && (
        <div className="mt-4">
          <label htmlFor="phone" className="block text-sm font-medium text-on-surface">
            Phone number
          </label>
          <input
            id="phone"
            type="tel"
            required
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            placeholder="e.g. 0700 000 000"
            className="mt-1 w-full rounded border border-outline-variant px-3 py-2 text-sm text-on-surface focus:border-primary-container focus:outline-none focus:ring-1 focus:ring-primary-container"
          />
        </div>
      )}

      <button
        type="submit"
        disabled={needsPhone && !phone.trim()}
        className="mt-6 w-full rounded bg-primary-container px-4 py-3 text-sm font-semibold text-on-primary shadow-sm transition-colors hover:bg-primary disabled:cursor-not-allowed disabled:opacity-50"
      >
        Pay securely
      </button>
    </form>
  );
}
