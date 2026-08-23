"use client";

import { useEffect, useState } from "react";

import { Icon } from "@/components/portal/icon";
import { formatCurrency, formatDateTime } from "@/lib/format";
import type { PublicPaymentLink } from "@/lib/payment-links";

import { SelcomQrDisplay } from "./selcom-qr-display";
import { StatusCard } from "./status-card";

type PayMethod = "WALLET_PUSH" | "SELCOM_PESA" | "TANQR";

interface PayResponseBody {
  success: boolean;
  data?: {
    collection_id: string;
    method: PayMethod;
    status: string;
    message: string;
    qr: string | null;
    payment_token: string | null;
    payment_gateway_url: string | null;
  };
  error?: { message: string };
}

interface CollectionStatusBody {
  success: boolean;
  data?: { status: string; message: string };
}

// Distinct terminal outcomes for a push/QR attempt — a customer who
// cancelled or was rejected deserves more specific copy than a bare
// "payment failed".
const OUTCOME_COPY: Record<string, { title: string; message: string }> = {
  cancelled: { title: "Payment cancelled", message: "This payment was cancelled." },
  user_cancelled: { title: "Payment cancelled", message: "You cancelled this payment." },
  rejected: { title: "Payment rejected", message: "This payment was rejected." },
};

const METHOD_LABEL: Record<PayMethod, string> = {
  WALLET_PUSH: "Pay by Mobile Money Push",
  SELCOM_PESA: "Pay with Selcom Pesa",
  TANQR: "Scan QR / TanQR",
};

const POLL_INTERVAL_MS = 3000;
const POLL_TIMEOUT_MS = 5 * 60 * 1000;
const REDIRECT_DELAY_MS = 2500;

/**
 * Three active payment methods only — Mobile Money Push, Selcom Pesa,
 * Scan QR / TanQR — dispatched through the single unified
 * POST .../pay endpoint (app/services/collection_payment.py). Hosted
 * checkout / card are never shown here; see
 * docs/selcom-checkout-collections.md for why hosted checkout stays
 * inactive.
 */
export function PaymentForm({ slug, link }: { slug: string; link: PublicPaymentLink }) {
  const [method, setMethod] = useState<PayMethod | null>(null);
  const [phone, setPhone] = useState(link.customer_phone ?? "");
  const [state, setState] = useState<"choose" | "phone_entry" | "submitting" | "awaiting_confirmation" | "success" | "failed">(
    "choose",
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<string | null>(null);
  const [pendingMessage, setPendingMessage] = useState<string | null>(null);
  const [collectionId, setCollectionId] = useState<string | null>(null);
  const [qr, setQr] = useState<string | null>(null);
  const [paymentToken, setPaymentToken] = useState<string | null>(null);
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

  async function submitPay(chosenMethod: PayMethod, chosenPhone: string) {
    setState("submitting");
    setErrorMessage(null);
    setOutcome(null);

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/public/payment-links/${slug}/pay`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
        body: JSON.stringify({
          method: chosenMethod,
          customer_phone: chosenPhone.trim() || null,
        }),
      });
      const body: PayResponseBody = await response.json();

      if (!response.ok || !body.success || !body.data) {
        setState("failed");
        setErrorMessage(body.error?.message ?? "Something went wrong. Please try again.");
        return;
      }

      if (body.data.status === "failed") {
        setState("failed");
        setErrorMessage(body.data.message);
        return;
      }

      setPendingMessage(body.data.message);
      setCollectionId(body.data.collection_id);
      setQr(body.data.qr);
      setPaymentToken(body.data.payment_token);
      setState("awaiting_confirmation");
    } catch {
      setState("failed");
      setErrorMessage("We couldn't reach Infinity Africa. Check your connection and try again.");
    }
  }

  function handleChooseMethod(chosenMethod: PayMethod) {
    setMethod(chosenMethod);
    // TANQR never needs a phone typed in — submit right away so the QR
    // shows as fast as possible. The push methods need a phone; if the
    // link already has one on file, skip straight to submitting too.
    // Otherwise move to a dedicated phone_entry phase — a stable state,
    // not re-derived from the live `phone` value, so typing into the
    // field doesn't flip the UI back to the chooser mid-entry.
    if (chosenMethod === "TANQR" || phone.trim()) {
      submitPay(chosenMethod, chosenMethod === "TANQR" ? "" : phone);
    } else {
      setState("phone_entry");
    }
  }

  function handlePhoneSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!method || !phone.trim()) return;
    submitPay(method, phone);
  }

  function handleRetry() {
    // A fresh key — retrying with the same one would just replay the
    // failed result instead of trying again.
    setIdempotencyKey(crypto.randomUUID());
    setErrorMessage(null);
    setOutcome(null);
    setPendingMessage(null);
    setCollectionId(null);
    setQr(null);
    setPaymentToken(null);
    setMethod(null);
    setState("choose");
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
        title={method === "TANQR" ? "Scan to pay" : "Payment pending confirmation"}
        message={pendingMessage ?? "This page will update automatically."}
      >
        {method === "TANQR" && qr && (
          <div className="w-full">
            <SelcomQrDisplay qr={qr} />
            {paymentToken && <p className="mt-2 text-center text-xs text-on-surface-variant">Token: {paymentToken}</p>}
          </div>
        )}
      </StatusCard>
    );
  }

  if (state === "success") {
    return (
      <StatusCard
        variant="success"
        title="Payment completed"
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
    const title = outcomeCopy?.title ?? "Payment reversed/failed";
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

  // state === "choose" | "phone_entry"
  const needsPhoneStep = state === "phone_entry";

  return (
    <div>
      <div className="bg-primary p-6 text-on-primary sm:p-8">
        <p className="text-xs font-semibold uppercase tracking-wide text-on-primary/70">Paying {link.merchant_name}</p>
        <p className="mt-2 text-3xl font-bold">{formatCurrency(link.amount, link.currency)}</p>

        {link.description && <p className="mt-2 text-sm text-on-primary/80">{link.description}</p>}

        {(link.customer_name || link.customer_phone) && (
          <p className="mt-3 text-sm text-on-primary/80">
            For {[link.customer_name, link.customer_phone].filter(Boolean).join(" · ")}
          </p>
        )}

        {link.expires_at && <p className="mt-1 text-xs text-on-primary/70">Expires {formatDateTime(link.expires_at)}</p>}
      </div>

      <div className="p-6 sm:p-8">
        {needsPhoneStep ? (
          <form onSubmit={handlePhoneSubmit}>
            <label htmlFor="phone" className="block text-sm font-medium text-on-surface">
              Phone number
            </label>
            <input
              id="phone"
              type="tel"
              required
              autoFocus
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              placeholder="e.g. 0700 000 000"
              className="mt-1 w-full rounded border border-outline-variant px-3 py-2 text-sm text-on-surface focus:border-primary-container focus:outline-none focus:ring-1 focus:ring-primary-container"
            />
            <button
              type="submit"
              disabled={!phone.trim()}
              className="mt-4 w-full rounded bg-primary-container px-4 py-3 text-sm font-semibold text-on-primary shadow-sm transition-colors hover:bg-primary disabled:cursor-not-allowed disabled:opacity-50"
            >
              {method ? METHOD_LABEL[method] : "Continue"}
            </button>
            <button
              type="button"
              onClick={() => {
                setMethod(null);
                setState("choose");
              }}
              className="mt-2 w-full text-center text-xs font-medium text-on-surface-variant hover:underline"
            >
              Choose a different method
            </button>
          </form>
        ) : (
          <>
            <p className="text-sm font-medium text-on-surface mb-3">Choose how you want to pay</p>
            <div className="space-y-2.5">
              <PaymentMethodButton
                icon="smartphone"
                label={METHOD_LABEL.WALLET_PUSH}
                description="Approve with your mobile money PIN"
                onClick={() => handleChooseMethod("WALLET_PUSH")}
              />
              <PaymentMethodButton
                icon="account_balance_wallet"
                label={METHOD_LABEL.SELCOM_PESA}
                description="Approve in your Selcom Pesa app"
                onClick={() => handleChooseMethod("SELCOM_PESA")}
              />
              <PaymentMethodButton
                icon="qr_code_scanner"
                label={METHOD_LABEL.TANQR}
                description="Scan with any supported payment app"
                onClick={() => handleChooseMethod("TANQR")}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function PaymentMethodButton({
  icon,
  label,
  description,
  onClick,
}: {
  icon: string;
  label: string;
  description: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full flex items-center gap-3.5 rounded border border-outline-variant px-4 py-3.5 text-left transition-colors hover:border-primary-container hover:bg-primary-container/5"
    >
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent text-primary">
        <Icon name={icon} className="text-[22px]" />
      </span>
      <span className="flex-1">
        <span className="block text-sm font-semibold text-on-surface">{label}</span>
        <span className="block text-xs text-on-surface-variant">{description}</span>
      </span>
      <ChevronIcon />
    </button>
  );
}

function ChevronIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" strokeWidth={2} stroke="currentColor" className="h-4 w-4 shrink-0 text-on-surface-variant">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
    </svg>
  );
}
