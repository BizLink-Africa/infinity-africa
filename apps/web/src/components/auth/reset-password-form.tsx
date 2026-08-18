"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { createClient } from "@/lib/supabase/client";
import { PASSWORD_RULES, validatePassword } from "@/lib/auth/password";

const inputClass =
  "w-full border-0 border-b border-outline-variant bg-transparent pb-2 text-sm text-on-surface placeholder-outline focus:outline-none focus:border-primary-container transition-colors";
const labelClass = "block text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-2";

export function ResetPasswordForm({
  loginPath = "/merchant/login",
  forgotPasswordPath = "/merchant/forgot-password",
}: {
  /** Where to send the user after a successful reset. */
  loginPath?: string;
  /** Where "Request a new link" points when the emailed link is dead. */
  forgotPasswordPath?: string;
}) {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errors, setErrors] = useState<string[]>([]);
  const [linkError, setLinkError] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "success">("idle");

  useEffect(() => {
    // A link Supabase rejects outright (expired, already used) comes back
    // as #error=...&error_description=... in the redirect URL rather than
    // a working recovery session — surface that immediately instead of
    // letting the merchant fill out a form that can only fail.
    const hash = window.location.hash;
    if (hash.includes("error_description")) {
      const params = new URLSearchParams(hash.slice(1));
      const description = params.get("error_description");
      // Deliberately a post-mount sync, not a derivable-from-props value:
      // window.location.hash only exists client-side, so a lazy useState
      // initializer would desync from the server-rendered default and
      // produce a hydration mismatch (see role-context.tsx for the same
      // pattern).
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setLinkError(description ? description.replace(/\+/g, " ") : "This reset link is invalid or has expired.");
    }
  }, []);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();

    const passwordErrors = validatePassword(password);
    if (confirmPassword !== password) passwordErrors.push("Passwords do not match.");
    setErrors(passwordErrors);
    if (passwordErrors.length > 0) return;

    setStatus("loading");
    const supabase = createClient();
    const { error } = await supabase.auth.updateUser({ password });

    if (error) {
      setStatus("idle");
      const message = error.message.toLowerCase().includes("session")
        ? "This reset link is invalid or has expired. Request a new one."
        : error.message;
      setErrors([message]);
      return;
    }

    setStatus("success");
    await supabase.auth.signOut();
    setTimeout(() => router.push(loginPath), 2000);
  }

  if (linkError) {
    return (
      <div className="space-y-4">
        <div className="rounded-lg bg-error/10 px-4 py-3 text-sm font-medium text-error">{linkError}</div>
        <a
          href={forgotPasswordPath}
          className="block w-full text-center bg-primary-container text-on-primary text-sm font-medium px-8 py-3.5 rounded-lg hover:opacity-90 transition-opacity"
        >
          Request a new link
        </a>
      </div>
    );
  }

  if (status === "success") {
    return (
      <div className="rounded-lg bg-primary-container/10 px-4 py-3 text-sm text-on-surface">
        Your password has been updated. Redirecting you to login…
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="mt-8 space-y-6">
      {errors.length > 0 && (
        <div className="rounded-lg bg-error/10 px-4 py-3 text-sm font-medium text-error space-y-1">
          {errors.map((msg) => (
            <p key={msg}>{msg}</p>
          ))}
        </div>
      )}

      <div>
        <label htmlFor="password" className={labelClass}>
          New Password
        </label>
        <input
          id="password"
          name="password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className={inputClass}
        />
        <ul className="mt-2 space-y-0.5">
          {PASSWORD_RULES.map((rule) => {
            const met = rule.test(password);
            return (
              <li key={rule.label} className={`text-xs ${met ? "text-primary" : "text-on-surface-variant"}`}>
                {met ? "✓" : "•"} {rule.label}
              </li>
            );
          })}
        </ul>
      </div>

      <div>
        <label htmlFor="confirmPassword" className={labelClass}>
          Confirm New Password
        </label>
        <input
          id="confirmPassword"
          name="confirmPassword"
          type="password"
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
          className={inputClass}
        />
      </div>

      <button
        type="submit"
        disabled={status === "loading"}
        className="w-full inline-flex items-center justify-center gap-2 bg-primary-container text-on-primary text-sm font-medium px-8 py-3.5 rounded-lg hover:opacity-90 transition-opacity disabled:opacity-60"
      >
        {status === "loading" ? "Updating…" : "Set New Password"}
      </button>
    </form>
  );
}
