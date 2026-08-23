"use client";

import { useEffect, useState } from "react";

import { formatCurrency, formatDateTime } from "@/lib/format";
import type { PublicPaymentLink } from "@/lib/payment-links";

import { StatusCard } from "./status-card";

interface WalletPushResponseBody {
  success: boolean;
  data?: { collection_id: string; payment_status: string; message: string };
  error?: { message: string };
}

interface CollectionStatusBody {
  success: boolean;
  data?: { status: string; message: string };
}

// Distinct terminal outcomes for a wallet push — a customer who
// cancelled or was rejected deserves more specific copy than a bare
// "payment failed".
const OUTCOME_COPY: Record<string, { title: string; message: string }> = {
  cancelled: { title: "Payment cancelled", message: "This payment was cancelled." },
  user_cancelled: { title: "Payment cancelled", message: "You cancelled this payment." },
  rejected: { title: "Payment rejected", message: "This payment was rejected." },
};

const POLL_INTERVAL_MS = 3000;
const POLL_TIMEOUT_MS = 5 * 60 * 1000;
const REDIRECT_DELAY_MS = 2500;

/**
 * TEMPORARY (2026-08-23): Selcom's hosted checkout (`payment_gateway_url`
 * from create-order-minimal) returns "Page Not Found" for every order
 * tested — confirmed via an exhaustive live diagnostic (see
 * docs/selcom-checkout-collections.md, "Known issue" section) that rules
 * out our own request construction. Escalated to Selcom; not something
 * we can fix in code. Until they confirm it's resolved, this page uses
 * the wallet-push flow instead (POST .../pay/wallet-push,
 * app/services/wallet_push.py) — fully working, proven with two real
 * successful payments this session. The hosted-checkout backend
 * endpoint (POST .../pay/checkout) is untouched and ready to swap back
 * in once Selcom confirms a fix — see git history around this file for
 * that version.
 */
export function PaymentForm({ slug, link }: { slug: string; link: PublicPaymentLink }) {
  const needsPhone = !link.customer_phone;
  const [phone, setPhone] = useState(link.customer_phone ?? "");
  const [state, setState] = useState<"idle" | "submitting" | "awaiting_confirmation" | "success" | "failed">("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<string | null>(null);
  const [pushMessage, setPushMessage] = useState<string | null>(null);
  const [collectionId, setCollectionId] = useState<string | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID());

  useEffect(() => {
    if (state !== "awaiting_confirmation" || !collectionId) return;

    const deadline = Date.now() + POLL_TIMEOUT_MS;
    let cancelled = false;

    async function poll() {
      if (cancelled) return;

      try {
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL}/public/payment-links/${slug}/collections/${collectionId}/status`,
          { cache: "no-store" },
        );
        const body: CollectionStatusBody = await response.json();
        const status = body.data?.status;

        if (status === "completed") {
          setState("success");
          return;
        }
        if (status && status !== "pending") {
          // cancelled / user_cancelled / rejected / failed
          setOutcome(status);
          setErrorMessage(body.data?.message ?? null);
          setState("failed");
          return;
        }
      } catch {
        // Transient network blip — keep polling until the timeout.
      }

      if (Date.now() >= deadline) {
        setState("failed");
        setErrorMessage("We didn't receive confirmation in time. If you completed the payment, it may still be processing.");
        return;
      }

      setTimeout(poll, POLL_INTERVAL_MS);
    }

    const timer = setTimeout(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [state, collectionId, slug]);

  useEffect(() => {
    const redirectUrl =
      state === "success" ? link.success_redirect_url : state === "failed" ? link.failure_redirect_url : null;
    if (!redirectUrl) return;

    const timer = setTimeout(() => {
      window.location.href = redirectUrl;
    }, REDIRECT_DELAY_MS);
    return () => clearTimeout(timer);
  }, [state, link.success_redirect_url, link.failure_redirect_url]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!phone.trim()) return;

    setState("submitting");
    setErrorMessage(null);
    setOutcome(null);

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/public/payment-links/${slug}/pay/wallet-push`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
        body: JSON.stringify({ customer_phone: phone.trim() }),
      });
      const body: WalletPushResponseBody = await response.json();

      if (!response.ok || !body.success || !body.data) {
        setState("failed");
        setErrorMessage(body.error?.message ?? "Something went wrong. Please try again.");
        return;
      }

      if (body.data.payment_status === "failed") {
        setState("failed");
        setErrorMessage(body.data.message);
        return;
      }

      // "pending" — the only other value this endpoint returns. From
      // here the page polls .../collections/{id}/status until the
      // webhook or a manual refresh resolves the real outcome.
      setPushMessage(body.data.message);
      setCollectionId(body.data.collection_id);
      setState("awaiting_confirmation");
    } catch {
      setState("failed");
      setErrorMessage("We couldn't reach Infinity Africa. Check your connection and try again.");
    }
  }

  function handleRetry() {
    // A fresh key — retrying with the same one would just replay the
    // failed result instead of trying again.
    setIdempotencyKey(crypto.randomUUID());
    setErrorMessage(null);
    setOutcome(null);
    setPushMessage(null);
    setCollectionId(null);
    setState("idle");
  }

  if (state === "submitting") {
    return (
      <StatusCard
        variant="processing"
        title="Processing your payment"
        message="This will only take a moment. Please don't close this page."
      />
    );
  }

  if (state === "awaiting_confirmation") {
    return (
      <StatusCard
        variant="processing"
        title="Waiting for your approval"
        message={pushMessage ?? "Approve the prompt on your phone. This page will update automatically."}
      />
    );
  }

  if (state === "success") {
    return (
      <StatusCard
        variant="success"
        title="Payment successful"
        message={
          link.success_redirect_url
            ? "Thank you! Redirecting you back to the merchant…"
            : "Thank you! Your payment has been received."
        }
        summary={{ merchantName: link.merchant_name, amount: link.amount, currency: link.currency }}
      />
    );
  }

  if (state === "failed") {
    const outcomeCopy = outcome ? OUTCOME_COPY[outcome] : null;
    const title = outcomeCopy?.title ?? "Payment failed";
    const baseMessage = errorMessage ?? outcomeCopy?.message ?? "Your payment could not be completed.";

    return (
      <StatusCard
        variant="error"
        title={title}
        message={link.failure_redirect_url ? `${baseMessage} Redirecting you back to the merchant…` : baseMessage}
      >
        {!link.failure_redirect_url && (
          <button
            type="button"
            onClick={handleRetry}
            className="mt-5 w-full rounded bg-primary-container px-4 py-3 text-sm font-semibold text-on-primary shadow-sm transition-colors hover:bg-primary"
          >
            Try again
          </button>
        )}
      </StatusCard>
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
        disabled={!phone.trim()}
        className="mt-6 w-full rounded bg-primary-container px-4 py-3 text-sm font-semibold text-on-primary shadow-sm transition-colors hover:bg-primary disabled:cursor-not-allowed disabled:opacity-50"
      >
        Pay now
      </button>
      <p className="mt-3 text-center text-xs text-on-surface-variant">
        You&apos;ll get a prompt on your phone to approve with your PIN.
      </p>
    </form>
  );
}
