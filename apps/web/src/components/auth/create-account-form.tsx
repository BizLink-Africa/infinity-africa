"use client";

import Link from "next/link";
import { useActionState } from "react";

import { createAccountAction, resendVerificationAction } from "@/lib/auth/actions";

const inputClass =
  "w-full border-0 border-b border-outline-variant bg-transparent pb-2 text-sm text-on-surface placeholder-outline focus:outline-none focus:border-primary-container transition-colors";
const labelClass = "block text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-2";
const errorClass = "mt-1.5 text-xs font-medium text-error";

function CheckYourEmail({ email, notice }: { email: string; notice?: string }) {
  const [resendState, resendAction, resending] = useActionState(resendVerificationAction, null);

  return (
    <div className="mt-8 space-y-4">
      <div className="rounded-lg bg-primary-container/10 px-4 py-3 text-sm text-on-surface">
        {resendState?.notice ?? notice ?? "Check your email to verify your account before continuing."}
      </div>

      {resendState?.formError && (
        <div className="rounded-lg bg-error/10 px-4 py-3 text-sm font-medium text-error">{resendState.formError}</div>
      )}

      <p className="text-sm text-on-surface-variant">
        We sent a verification link to <span className="font-semibold text-on-surface">{email}</span>. Click it to
        confirm your account, then you&apos;ll be taken straight to your merchant verification form. The link can take a
        minute to arrive — check your spam folder too.
      </p>

      <form action={resendAction}>
        <input type="hidden" name="email" value={email} />
        <button
          type="submit"
          disabled={resending}
          className="w-full inline-flex items-center justify-center gap-2 border border-outline-variant text-on-surface text-sm font-medium px-8 py-3 rounded-lg hover:bg-surface-container transition-colors disabled:opacity-60"
        >
          {resending ? "Sending…" : "Resend verification email"}
        </button>
      </form>

      <p className="text-center text-sm text-on-surface-variant">
        Already verified?{" "}
        <Link href="/merchant/login" className="font-semibold text-primary-container hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}

export function CreateAccountForm() {
  const [state, action, pending] = useActionState(createAccountAction, null);

  if (state?.awaitingEmailVerification) {
    return <CheckYourEmail email={state.values?.email ?? ""} notice={state.notice} />;
  }

  return (
    <form action={action} className="mt-8 space-y-6">
      {state?.formError && (
        <div className="rounded-lg bg-error/10 px-4 py-3 text-sm font-medium text-error">{state.formError}</div>
      )}
      {state?.notice && (
        <div className="rounded-lg bg-primary-container/10 px-4 py-3 text-sm text-on-surface">{state.notice}</div>
      )}

      <div>
        <label htmlFor="fullName" className={labelClass}>
          Full Name
        </label>
        <input
          id="fullName"
          name="fullName"
          type="text"
          autoComplete="name"
          placeholder="e.g. Amani Mushi"
          defaultValue={state?.values?.fullName}
          className={inputClass}
        />
        {state?.errors?.fullName?.map((msg) => (
          <p key={msg} className={errorClass}>
            {msg}
          </p>
        ))}
      </div>

      <div>
        <label htmlFor="email" className={labelClass}>
          Email Address
        </label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="off"
          placeholder="you@business.co.tz"
          defaultValue={state?.values?.email}
          className={inputClass}
        />
        {state?.errors?.email?.map((msg) => (
          <p key={msg} className={errorClass}>
            {msg}
          </p>
        ))}
      </div>

      <div>
        <label htmlFor="phone" className={labelClass}>
          Contact Number
        </label>
        <input
          id="phone"
          name="phone"
          type="tel"
          autoComplete="tel"
          placeholder="+255 7XX XXX XXX"
          defaultValue={state?.values?.phone}
          className={inputClass}
        />
        {state?.errors?.phone?.map((msg) => (
          <p key={msg} className={errorClass}>
            {msg}
          </p>
        ))}
      </div>

      <div>
        <label htmlFor="password" className={labelClass}>
          Password
        </label>
        <input id="password" name="password" type="password" autoComplete="new-password" className={inputClass} />
        <p className="mt-1.5 text-xs text-on-surface-variant">
          At least 8 characters, with uppercase, lowercase, a number, and a symbol.
        </p>
        {state?.errors?.password?.map((msg) => (
          <p key={msg} className={errorClass}>
            {msg}
          </p>
        ))}
      </div>

      <div>
        <label htmlFor="confirmPassword" className={labelClass}>
          Confirm Password
        </label>
        <input
          id="confirmPassword"
          name="confirmPassword"
          type="password"
          autoComplete="new-password"
          className={inputClass}
        />
        {state?.errors?.confirmPassword?.map((msg) => (
          <p key={msg} className={errorClass}>
            {msg}
          </p>
        ))}
      </div>

      <button
        type="submit"
        disabled={pending}
        className="w-full inline-flex items-center justify-center gap-2 bg-primary-container text-on-primary text-sm font-medium px-8 py-3.5 rounded-lg hover:opacity-90 transition-opacity disabled:opacity-60"
      >
        {pending ? "Creating account…" : "Create Account"}
      </button>

      <p className="text-center text-sm text-on-surface-variant">
        Already have an account?{" "}
        <Link href="/merchant/login" className="font-semibold text-primary-container hover:underline">
          Sign in
        </Link>
      </p>
    </form>
  );
}
