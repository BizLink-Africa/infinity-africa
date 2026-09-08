import { type EmailOtpType } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

import { createClient } from "@/lib/supabase/server";

/**
 * Supabase email-confirmation callback.
 *
 * The merchant sign-up (lib/auth/actions.ts::createAccountAction) calls
 * `supabase.auth.signUp` with `emailRedirectTo` pointing here. Supabase
 * emails a link that, once clicked, lands back on this route with either:
 *
 *   - `?code=...`                     (PKCE — the default for @supabase/ssr;
 *                                      exchange it for a session)
 *   - `?token_hash=...&type=signup`   (older / cross-device style — verify
 *                                      the OTP directly)
 *
 * On success we establish the session cookie and forward the merchant to
 * document/business verification (`/onboarding`). On any failure — an
 * expired or already-consumed link, or the link opened in a browser that
 * never held the PKCE verifier — we send them to /merchant/login with a
 * plain-language notice, never a stack trace and never a bare 400.
 *
 * A hash-fragment callback (`#access_token=...`) can't be handled here
 * because fragments are never sent to the server; the sign-up flow above
 * never produces one, so there is nothing to catch for it.
 */

const SAFE_NEXT = /^\/[a-zA-Z0-9/_-]*$/;

function loginRedirect(origin: string, notice: string) {
  const url = new URL("/merchant/login", origin);
  url.searchParams.set("notice", notice);
  return NextResponse.redirect(url);
}

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);

  const rawNext = searchParams.get("next") ?? "/onboarding";
  const next = SAFE_NEXT.test(rawNext) ? rawNext : "/onboarding";

  const code = searchParams.get("code");
  const tokenHash = searchParams.get("token_hash");
  const type = searchParams.get("type") as EmailOtpType | null;
  const errorDescription = searchParams.get("error_description");

  if (errorDescription) {
    return loginRedirect(
      origin,
      "Your verification link is invalid or has expired. Sign in and we'll send you a new one.",
    );
  }

  const supabase = await createClient();

  if (code) {
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(new URL(next, origin));
    }
  } else if (tokenHash && type) {
    const { error } = await supabase.auth.verifyOtp({ type, token_hash: tokenHash });
    if (!error) {
      return NextResponse.redirect(new URL(next, origin));
    }
  }

  // Either there was no usable token, or the exchange failed. The most
  // common benign cause is the link being opened on a different device
  // from the one that signed up (so no PKCE verifier is present) or the
  // link being clicked a second time after it was already consumed — the
  // account itself is fine in both cases, they just need to sign in.
  return loginRedirect(
    origin,
    "Your email is verified. Sign in to continue your merchant verification.",
  );
}
