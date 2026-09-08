import { beforeEach, describe, expect, it, vi } from "vitest";

// `actions.ts` transitively pulls in modules marked `import "server-only"`
// (mock-store / mock-session). That package throws outside a real RSC
// build; stub it so the unit under test can be imported in jsdom.
vi.mock("server-only", () => ({}));

// --- mocks -----------------------------------------------------------------

const signUp = vi.fn();
const signInWithPassword = vi.fn();
const resend = vi.fn();
const maybeSingle = vi.fn();

vi.mock("@/lib/supabase/server", () => ({
  createClient: async () => ({
    auth: { signUp, signInWithPassword, resend },
    from: () => ({ select: () => ({ eq: () => ({ maybeSingle }) }) }),
  }),
}));

const isSupabaseConfigured = vi.fn();
vi.mock("./supabase-status", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./supabase-status")>();
  return { ...actual, isSupabaseConfigured: () => isSupabaseConfigured() };
});

const getOnboardingStatus = vi.fn();
vi.mock("@/lib/onboarding/api", () => ({
  getOnboardingStatus: (...args: unknown[]) => getOnboardingStatus(...args),
}));

vi.mock("next/headers", () => ({
  headers: async () => new Map([["host", "infinityafrica.net"]]),
}));

class RedirectError extends Error {
  constructor(public location: string) {
    super(`NEXT_REDIRECT:${location}`);
  }
}
vi.mock("next/navigation", () => ({
  redirect: (location: string) => {
    throw new RedirectError(location);
  },
}));

// --- helpers -------------------------------------------------------------

function form(fields: Record<string, string>): FormData {
  const fd = new FormData();
  for (const [k, v] of Object.entries(fields)) fd.set(k, v);
  return fd;
}

const VALID_SIGNUP = {
  fullName: "Amani Mushi",
  email: "amani@shop.co.tz",
  phone: "+255700000000",
  password: "Str0ng!pass",
  confirmPassword: "Str0ng!pass",
};

async function importActions() {
  return import("./actions");
}

beforeEach(() => {
  vi.clearAllMocks();
  isSupabaseConfigured.mockReturnValue(true);
  process.env.NEXT_PUBLIC_SITE_URL = "https://infinityafrica.net";
});

// --- createAccountAction ------------------------------------------------

describe("createAccountAction", () => {
  it("when email confirmation is required (user, no session) shows the check-email message and does NOT redirect", async () => {
    signUp.mockResolvedValue({ data: { user: { id: "u1" }, session: null }, error: null });
    const { createAccountAction } = await importActions();

    const state = await createAccountAction(null, form(VALID_SIGNUP));

    expect(state?.awaitingEmailVerification).toBe(true);
    expect(state?.notice).toMatch(/check your email to verify/i);
    expect(state?.formError).toBeUndefined();
    // emailRedirectTo must point at our callback route.
    expect(signUp).toHaveBeenCalledWith(
      expect.objectContaining({
        options: expect.objectContaining({
          emailRedirectTo: "https://infinityafrica.net/auth/callback?next=%2Fonboarding",
        }),
      }),
    );
  });

  it("when signup returns an active session, redirects to /onboarding", async () => {
    signUp.mockResolvedValue({
      data: { user: { id: "u1" }, session: { access_token: "tok" } },
      error: null,
    });
    const { createAccountAction } = await importActions();

    await expect(createAccountAction(null, form(VALID_SIGNUP))).rejects.toMatchObject({
      location: "/onboarding",
    });
  });

  it("surfaces a real Supabase rejection as a form error", async () => {
    signUp.mockResolvedValue({
      data: { user: null, session: null },
      error: { status: 422, message: "Password is too weak", name: "AuthApiError" },
    });
    const { createAccountAction } = await importActions();

    const state = await createAccountAction(null, form(VALID_SIGNUP));
    expect(state?.formError).toBe("Password is too weak");
    expect(state?.awaitingEmailVerification).toBeFalsy();
  });
});

// --- loginAction ------------------------------------------------------

describe("loginAction", () => {
  it("shows a verify-email message (not 'Incorrect email or password') for an unconfirmed account", async () => {
    signInWithPassword.mockResolvedValue({
      data: { user: null, session: null },
      error: { status: 400, code: "email_not_confirmed", message: "Email not confirmed", name: "AuthApiError" },
    });
    const { loginAction } = await importActions();

    const state = await loginAction(null, form({ email: "amani@shop.co.tz", password: "Str0ng!pass" }));

    expect(state?.formError).toMatch(/verify your email before logging in/i);
    expect(state?.formError).not.toMatch(/incorrect email or password/i);
    expect(state?.awaitingEmailVerification).toBe(true);
  });

  it("still shows the generic message for genuinely wrong credentials", async () => {
    signInWithPassword.mockResolvedValue({
      data: { user: null, session: null },
      error: { status: 400, code: "invalid_credentials", message: "Invalid login credentials", name: "AuthApiError" },
    });
    const { loginAction } = await importActions();

    const state = await loginAction(null, form({ email: "amani@shop.co.tz", password: "wrong" }));
    expect(state?.formError).toBe("Incorrect email or password.");
  });

  it("redirects a verified merchant to their onboarding next_path", async () => {
    signInWithPassword.mockResolvedValue({
      data: { user: { id: "u1" }, session: { access_token: "tok" } },
      error: null,
    });
    maybeSingle.mockResolvedValue({ data: null });
    getOnboardingStatus.mockResolvedValue({ next_path: "/merchant/overview" });
    const { loginAction } = await importActions();

    await expect(
      loginAction(null, form({ email: "amani@shop.co.tz", password: "Str0ng!pass" })),
    ).rejects.toMatchObject({ location: "/merchant/overview" });
  });
});

// --- resendVerificationAction ----------------------------------------

describe("resendVerificationAction", () => {
  it("calls Supabase resend and returns a generic confirmation", async () => {
    resend.mockResolvedValue({ error: null });
    const { resendVerificationAction } = await importActions();

    const state = await resendVerificationAction(null, form({ email: "amani@shop.co.tz" }));

    expect(resend).toHaveBeenCalledWith(
      expect.objectContaining({ type: "signup", email: "amani@shop.co.tz" }),
    );
    expect(state?.awaitingEmailVerification).toBe(true);
    expect(state?.notice).toMatch(/fresh link/i);
  });

  it("rejects an obviously invalid email without calling Supabase", async () => {
    const { resendVerificationAction } = await importActions();
    const state = await resendVerificationAction(null, form({ email: "not-an-email" }));
    expect(resend).not.toHaveBeenCalled();
    expect(state?.formError).toMatch(/email address you signed up with/i);
  });
});
