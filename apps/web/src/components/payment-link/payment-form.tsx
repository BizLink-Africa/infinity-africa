"use client";

import { useEffect, useState } from "react";

import { formatCurrency, formatDateTime } from "@/lib/format";
import type { PublicPaymentLink } from "@/lib/payment-links";

import { QrCode } from "./qr-code";
import { StatusCard } from "./status-card";

const METHOD_OPTIONS = [
  { value: "USSD_PUSH", label: "Push USSD", hint: "Approve a USSD prompt sent to your phone" },
  { value: "STK_PUSH", label: "STK Push", hint: "Approve an STK prompt sent to your phone" },
  { value: "SELCOM_PESA_PUSH", label: "Push to Selcom Pesa", hint: "Approve in your Selcom Pesa wallet" },
  { value: "DYNAMIC_QR", label: "Dynamic QR Code", hint: "Scan to pay with any supported app" },
] as const;

// Distinct from the four options above (all of which go through the
// older /collect endpoint) — routes through the newer Selcom Checkout
// create-order-minimal -> wallet-payment flow instead
// (/pay/wallet-push). Not filtered by link.allowed_payment_methods:
// that field's DB constraint only recognizes the four values above, so
// this option is always offered regardless of what the merchant
// configured. See app/services/wallet_push.py for the backend side.
const WALLET_PUSH_METHOD = {
  value: "MOBILE_MONEY_PUSH",
  label: "Pay with Mobile Money Push",
  hint: "Approve the request sent to your phone",
} as const;

// "processing" = the initiation POST is in flight. "awaiting_confirmation" =
// initiated successfully (PROCESSING) and we're now polling the link's
// status waiting for the /v1/webhooks/selcom callback to resolve it — a
// real push/QR is never resolved synchronously by the collect call itself.
type SubmitState = "idle" | "processing" | "awaiting_confirmation" | "success" | "failed";

interface CollectResponseBody {
  success: boolean;
  data?: { status: string; qr_payload?: string; expires_at?: string | null };
  error?: { message: string };
}

interface WalletPushResponseBody {
  success: boolean;
  data?: { collection_id: string; payment_status: string; message: string };
  error?: { message: string };
}

interface LinkStatusBody {
  success: boolean;
  data?: { status: string };
}

interface CollectionStatusBody {
  success: boolean;
  data?: { status: string; message: string };
}

// The Mobile Money Push flow's own terminal outcomes — distinct from the
// generic "failed" the other four methods use, since a customer who
// cancelled or was rejected deserves more specific copy than a bare
// "payment failed" (task: Pending/Completed/Failed/Cancelled/Rejected/
// User cancelled).
const WALLET_PUSH_OUTCOME_COPY: Record<string, { title: string; message: string }> = {
  cancelled: { title: "Payment cancelled", message: "This payment was cancelled." },
  user_cancelled: { title: "Payment cancelled", message: "You cancelled this payment." },
  rejected: { title: "Payment rejected", message: "This payment was rejected." },
};

const POLL_INTERVAL_MS = 3000;
const POLL_TIMEOUT_MS = 5 * 60 * 1000;
const REDIRECT_DELAY_MS = 2500;

export function PaymentForm({ slug, link }: { slug: string; link: PublicPaymentLink }) {
  const availableMethods = METHOD_OPTIONS.filter((option) =>
    link.allowed_payment_methods.includes(option.value),
  );

  const [method, setMethod] = useState<string>(availableMethods[0]?.value ?? "");
  const [phone, setPhone] = useState(link.customer_phone ?? "");
  const [state, setState] = useState<SubmitState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID());
  const [qrPayload, setQrPayload] = useState<{ payload: string; expiresAt: string | null } | null>(null);
  const [walletPushMessage, setWalletPushMessage] = useState<string | null>(null);
  const [walletPushCollectionId, setWalletPushCollectionId] = useState<string | null>(null);
  const [walletPushOutcome, setWalletPushOutcome] = useState<string | null>(null);

  const needsPhone = method !== "DYNAMIC_QR";
  const isWalletPush = method === WALLET_PUSH_METHOD.value;
  const canSubmit = method.length > 0 && (!needsPhone || phone.trim().length > 0);

  useEffect(() => {
    if (state !== "awaiting_confirmation") return;

    const deadline = Date.now() + POLL_TIMEOUT_MS;
    let cancelled = false;

    async function pollWalletPush(collectionId: string) {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/public/payment-links/${slug}/collections/${collectionId}/status`,
        { cache: "no-store" },
      );
      const body: CollectionStatusBody = await response.json();
      const status = body.data?.status;

      if (status === "completed") {
        setState("success");
        return true;
      }
      if (status && status !== "pending") {
        // cancelled / user_cancelled / rejected / failed
        setWalletPushOutcome(status);
        setState("failed");
        setErrorMessage(body.data?.message ?? null);
        return true;
      }
      return false; // still pending — keep polling
    }

    async function pollPaymentLink() {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/public/payment-links/${slug}`, {
        cache: "no-store",
      });
      const body: LinkStatusBody = await response.json();
      const status = body.data?.status;

      if (status === "PAID") {
        setState("success");
        return true;
      }
      if (status === "EXPIRED" || status === "CANCELLED") {
        setState("failed");
        setErrorMessage("This payment link is no longer available.");
        return true;
      }
      return false;
    }

    async function poll() {
      if (cancelled) return;

      try {
        const resolved = walletPushCollectionId
          ? await pollWalletPush(walletPushCollectionId)
          : await pollPaymentLink();
        if (resolved) return;
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
  }, [state, slug, walletPushCollectionId]);

  // If the merchant configured a redirect URL, bounce the customer back to
  // it a couple seconds after the result is shown — long enough to read the
  // outcome, short enough not to feel stuck.
  useEffect(() => {
    const redirectUrl =
      state === "success" ? link.success_redirect_url : state === "failed" ? link.failure_redirect_url : null;
    if (!redirectUrl) return;

    const timer = setTimeout(() => {
      window.location.href = redirectUrl;
    }, REDIRECT_DELAY_MS);
    return () => clearTimeout(timer);
  }, [state, link.success_redirect_url, link.failure_redirect_url]);

  async function handleWalletPushSubmit() {
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/public/payment-links/${slug}/pay/wallet-push`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
          body: JSON.stringify({ customer_phone: phone.trim() }),
        },
      );
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

      // "pending" — the only other value this endpoint ever returns (see
      // app/schemas/payment_links.py::PaymentLinkWalletPushResponse).
      // From here the page polls GET .../collections/{id}/status (see the
      // polling effect above), which reflects the real, eventual outcome
      // once the webhook or a status refresh resolves it
      // (app/services/checkout_reconciliation.py) — completed, cancelled,
      // user_cancelled, rejected, or failed.
      setWalletPushMessage(body.data.message);
      setWalletPushCollectionId(body.data.collection_id);
      setState("awaiting_confirmation");
    } catch {
      setState("failed");
      setErrorMessage("We couldn't reach Infinity Africa. Check your connection and try again.");
    }
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!canSubmit || state === "processing") return;

    setState("processing");
    setErrorMessage(null);

    if (isWalletPush) {
      await handleWalletPushSubmit();
      return;
    }

    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/public/payment-links/${slug}/collect`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
          body: JSON.stringify({
            method,
            customer_phone: needsPhone ? phone.trim() : undefined,
          }),
        },
      );
      const body: CollectResponseBody = await response.json();

      if (!response.ok || !body.success || !body.data) {
        setState("failed");
        setErrorMessage(body.error?.message ?? "Something went wrong. Please try again.");
        return;
      }

      if (body.data.status === "successful") {
        setState("success");
      } else if (body.data.status === "processing") {
        if (method === "DYNAMIC_QR" && body.data.qr_payload) {
          setQrPayload({ payload: body.data.qr_payload, expiresAt: body.data.expires_at ?? null });
        }
        setState("awaiting_confirmation");
      } else {
        setState("failed");
        setErrorMessage("Your payment could not be completed. Please try again.");
      }
    } catch {
      setState("failed");
      setErrorMessage("We couldn't reach Infinity Africa. Check your connection and try again.");
    }
  }

  function handleRetry() {
    // A fresh key — retrying with the same one would just replay the
    // failed result instead of trying again.
    setIdempotencyKey(crypto.randomUUID());
    setQrPayload(null);
    setWalletPushMessage(null);
    setWalletPushCollectionId(null);
    setWalletPushOutcome(null);
    setState("idle");
    setErrorMessage(null);
  }

  if (state === "processing") {
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
        title={method === "DYNAMIC_QR" ? "Scan to complete payment" : "Waiting for your approval"}
        message={
          walletPushMessage ??
          (method === "DYNAMIC_QR"
            ? "Scan the QR code with your mobile money app. This page will update automatically."
            : "Approve the prompt on your phone. This page will update automatically.")
        }
      >
        {method === "DYNAMIC_QR" && qrPayload && (
          <QrCode payload={qrPayload.payload} expiresAt={qrPayload.expiresAt} />
        )}
      </StatusCard>
    );
  }

  if (state === "success") {
    return (
      <StatusCard
        variant="success"
        title="Payment successful"
        message={
          link.success_redirect_url
            ? `You paid ${link.merchant_name}. Redirecting you back to the merchant…`
            : `You paid ${link.merchant_name}.`
        }
        summary={{ merchantName: link.merchant_name, amount: link.amount, currency: link.currency }}
      />
    );
  }

  if (state === "failed") {
    const outcomeCopy = walletPushOutcome ? WALLET_PUSH_OUTCOME_COPY[walletPushOutcome] : undefined;
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

      <fieldset>
        <legend className="text-sm font-semibold text-on-surface">Choose how to pay</legend>
        <div className="mt-3 space-y-2">
          {availableMethods.map((option) => (
            <label
              key={option.value}
              className={`flex cursor-pointer items-start gap-3 rounded border p-3 transition-colors ${
                method === option.value
                  ? "border-primary-container bg-secondary-container/40"
                  : "border-outline-variant hover:bg-surface-container"
              }`}
            >
              <input
                type="radio"
                name="method"
                value={option.value}
                checked={method === option.value}
                onChange={() => setMethod(option.value)}
                className="mt-0.5 accent-primary-container"
              />
              <span>
                <span className="block text-sm font-medium text-on-surface">{option.label}</span>
                <span className="block text-xs text-on-surface-variant">{option.hint}</span>
              </span>
            </label>
          ))}

          <label
            key={WALLET_PUSH_METHOD.value}
            className={`flex cursor-pointer items-start gap-3 rounded border p-3 transition-colors ${
              isWalletPush
                ? "border-primary-container bg-secondary-container/40"
                : "border-outline-variant hover:bg-surface-container"
            }`}
          >
            <input
              type="radio"
              name="method"
              value={WALLET_PUSH_METHOD.value}
              checked={isWalletPush}
              onChange={() => setMethod(WALLET_PUSH_METHOD.value)}
              className="mt-0.5 accent-primary-container"
            />
            <span>
              <span className="block text-sm font-medium text-on-surface">{WALLET_PUSH_METHOD.label}</span>
              <span className="block text-xs text-on-surface-variant">{WALLET_PUSH_METHOD.hint}</span>
            </span>
          </label>
        </div>
      </fieldset>

      {method === "DYNAMIC_QR" && (
        <p className="mt-4 rounded border border-dashed border-outline-variant bg-surface-container p-4 text-center text-xs text-on-surface-variant">
          You&apos;ll get a scannable QR code as soon as you tap Pay below.
        </p>
      )}

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
        disabled={!canSubmit}
        className="mt-6 w-full rounded bg-primary-container px-4 py-3 text-sm font-semibold text-on-primary shadow-sm transition-colors hover:bg-primary disabled:cursor-not-allowed disabled:opacity-50"
      >
        Pay {formatCurrency(link.amount, link.currency)}
      </button>
    </form>
  );
}
