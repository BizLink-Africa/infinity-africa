"use client";

import { useState } from "react";

import { Icon } from "@/components/portal/icon";
import type { PublicPayByLink } from "@/lib/pay-by-link";

interface CheckoutResponseBody {
  success: boolean;
  data?: { payment_link_id: string; redirect_url: string };
  // `details` is only ever populated on a 422 (app/core/errors.py's
  // RequestValidationError handler) — the raw list of Pydantic field
  // errors. Same "surface the real reason" convention as
  // payment-form.tsx's own firstValidationMessage.
  error?: { message: string; details?: unknown };
}

function firstValidationMessage(details: unknown): string | null {
  if (!Array.isArray(details) || details.length === 0) return null;
  const first = details[0];
  if (!first || typeof first !== "object" || typeof (first as { msg?: unknown }).msg !== "string") return null;
  return (first as { msg: string }).msg.replace(/^Value error,\s*/, "");
}

const inputClass =
  "w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary text-sm";
const labelClass = "block text-sm font-medium text-on-surface-variant mb-1.5";

export function PayByLinkForm({ slug, link }: { slug: string; link: PublicPayByLink }) {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [idempotencyKey] = useState(() => crypto.randomUUID());

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setErrorMessage(null);

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/public/pay-by-link/${slug}/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
        body: JSON.stringify({
          first_name: firstName,
          last_name: lastName,
          email,
          phone,
          amount,
          currency: "TZS",
          description: description.trim() || null,
        }),
      });
      const body: CheckoutResponseBody = await response.json();

      if (!response.ok || !body.success || !body.data) {
        setErrorMessage(
          firstValidationMessage(body.error?.details) ?? body.error?.message ?? "Something went wrong. Please try again.",
        );
        setSubmitting(false);
        return;
      }

      // Full-page redirect — the customer leaves this permanent page
      // entirely and lands on the freshly created, ordinary payment
      // link's own "Choose how you want to pay" checkout page. Stays
      // "submitting" (no setSubmitting(false)) so the button doesn't
      // flash back to enabled during the brief navigation.
      window.location.href = body.data.redirect_url;
    } catch {
      setErrorMessage("We couldn't reach Infinity Africa. Check your connection and try again.");
      setSubmitting(false);
    }
  }

  return (
    <div className="p-6 sm:p-8">
      <div className="mb-6 text-center">
        <h1 className="text-xl font-bold text-on-surface">{link.display_name}</h1>
        {link.description && <p className="mt-1.5 text-sm text-on-surface-variant">{link.description}</p>}
        <p className="mt-3 flex items-center justify-center gap-1.5 text-xs text-on-surface-variant">
          <LockIcon />
          Secure payment powered by Infinity Africa
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelClass}>First name</label>
            <input
              className={inputClass}
              type="text"
              required
              value={firstName}
              onChange={(event) => setFirstName(event.target.value)}
              placeholder="Grace"
            />
          </div>
          <div>
            <label className={labelClass}>Last name</label>
            <input
              className={inputClass}
              type="text"
              required
              value={lastName}
              onChange={(event) => setLastName(event.target.value)}
              placeholder="Mwakalinga"
            />
          </div>
        </div>

        <div>
          <label className={labelClass}>Email</label>
          <input
            className={inputClass}
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="grace@example.com"
          />
        </div>

        <div>
          <label className={labelClass}>Mobile number</label>
          <input
            className={inputClass}
            type="tel"
            required
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            placeholder="+255 7XX XXX XXX"
          />
        </div>

        <div>
          <label className={labelClass}>Amount (TZS)</label>
          <div className="relative">
            <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-on-surface-variant text-sm font-semibold">
              TZS
            </span>
            <input
              className={`${inputClass} pl-12`}
              type="number"
              required
              min="1"
              step="0.01"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              placeholder="25,000"
            />
          </div>
        </div>

        <div>
          <label className={labelClass}>What&apos;s this for? (optional)</label>
          <input
            className={inputClass}
            type="text"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="e.g. Order #4821"
            maxLength={500}
          />
        </div>

        {errorMessage && (
          <div className="rounded-lg bg-error-container/10 text-on-error-container px-4 py-3 text-sm font-medium">
            {errorMessage}
          </div>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-primary-container text-on-primary text-sm font-medium py-3 rounded-lg hover:opacity-90 transition-opacity flex items-center justify-center gap-2 disabled:opacity-60"
        >
          {submitting ? (
            "Preparing secure payment…"
          ) : (
            <>
              <Icon name="lock" className="text-[18px]" />
              Proceed to Pay
            </>
          )}
        </button>
      </form>
    </div>
  );
}

function LockIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" strokeWidth={2} stroke="currentColor" className="h-3.5 w-3.5">
      <rect x="4.5" y="10.5" width="15" height="9.75" rx="1.5" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 10.5V7.5a3.75 3.75 0 017.5 0v3" />
    </svg>
  );
}
