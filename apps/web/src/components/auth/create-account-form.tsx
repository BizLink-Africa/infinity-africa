"use client";

import Link from "next/link";
import { useActionState } from "react";

import { createAccountAction } from "@/lib/auth/actions";

const inputClass =
  "w-full border-0 border-b border-outline-variant bg-transparent pb-2 text-sm text-on-surface placeholder-outline focus:outline-none focus:border-primary-container transition-colors";
const labelClass = "block text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-2";
const errorClass = "mt-1.5 text-xs font-medium text-error";

export function CreateAccountForm() {
  const [state, action, pending] = useActionState(createAccountAction, null);

  return (
    <form action={action} className="mt-8 space-y-6">
      {state?.formError && (
        <div className="rounded-lg bg-error/10 px-4 py-3 text-sm font-medium text-error">{state.formError}</div>
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
