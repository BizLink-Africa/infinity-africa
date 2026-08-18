"use client";

import { useState } from "react";

import { createClient } from "@/lib/supabase/client";
import { isEmail } from "@/lib/auth/password";
import { isSupabaseConfigured } from "@/lib/auth/supabase-status";

const inputClass =
  "w-full border-0 border-b border-outline-variant bg-transparent pb-2 text-sm text-on-surface placeholder-outline focus:outline-none focus:border-primary-container transition-colors";
const labelClass = "block text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-2";

export function ForgotPasswordForm({
  resetPasswordPath = "/merchant/reset-password",
}: {
  /** Where the emailed reset link should send the user back to. */
  resetPasswordPath?: string;
}) {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "sent">("idle");
  const [error, setError] = useState("");

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError("");

    if (!isEmail(email)) {
      setError("Enter a valid email address.");
      return;
    }

    if (!isSupabaseConfigured()) {
      setError("Password reset isn't available in this environment yet. Contact support@infinityafrica.net.");
      return;
    }

    setStatus("loading");
    const supabase = createClient();
    const { error: resetError } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}${resetPasswordPath}`,
    });

    // Supabase deliberately doesn't reveal whether the email is registered
    // (avoids account enumeration) — treat every non-throwing outcome as
    // "sent", including an unregistered email.
    if (resetError) {
      setStatus("idle");
      setError("Something went wrong. Please try again.");
      return;
    }
    setStatus("sent");
  }

  if (status === "sent") {
    return (
      <div className="rounded-lg bg-primary-container/10 px-4 py-3 text-sm text-on-surface">
        If an account exists for <span className="font-semibold">{email}</span>, we&apos;ve sent a link to reset your
        password. Check your inbox (and spam folder).
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="mt-8 space-y-6">
      {error && <div className="rounded-lg bg-error/10 px-4 py-3 text-sm font-medium text-error">{error}</div>}

      <div>
        <label htmlFor="email" className={labelClass}>
          Email Address
        </label>
        <input
          id="email"
          name="email"
          type="email"
          placeholder="you@business.co.tz"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className={inputClass}
        />
      </div>

      <button
        type="submit"
        disabled={status === "loading"}
        className="w-full inline-flex items-center justify-center gap-2 bg-primary-container text-on-primary text-sm font-medium px-8 py-3.5 rounded-lg hover:opacity-90 transition-opacity disabled:opacity-60"
      >
        {status === "loading" ? "Sending…" : "Send Reset Link"}
      </button>
    </form>
  );
}
