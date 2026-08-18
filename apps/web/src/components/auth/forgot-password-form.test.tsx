import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const resetPasswordForEmail = vi.fn();

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { resetPasswordForEmail },
  }),
}));

vi.mock("@/lib/auth/supabase-status", () => ({
  isSupabaseConfigured: () => true,
}));

describe("ForgotPasswordForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetPasswordForEmail.mockResolvedValue({ error: null });
  });

  it("renders an email field and a Send Reset Link button", async () => {
    const { ForgotPasswordForm } = await import("./forgot-password-form");
    render(<ForgotPasswordForm />);

    expect(screen.getByPlaceholderText("you@business.co.tz")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send Reset Link" })).toBeInTheDocument();
  });

  it("calls Supabase resetPasswordForEmail and shows a confirmation message", async () => {
    const { ForgotPasswordForm } = await import("./forgot-password-form");
    render(<ForgotPasswordForm />);

    fireEvent.change(screen.getByPlaceholderText("you@business.co.tz"), {
      target: { value: "merchant@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send Reset Link" }));

    await waitFor(() => expect(resetPasswordForEmail).toHaveBeenCalled());
    expect(resetPasswordForEmail.mock.calls[0][0]).toBe("merchant@example.com");
    await waitFor(() => expect(screen.getByText(/we've sent a link to reset your password/i)).toBeInTheDocument());
  });

  it("rejects an invalid email without calling Supabase", async () => {
    const { ForgotPasswordForm } = await import("./forgot-password-form");
    render(<ForgotPasswordForm />);

    fireEvent.change(screen.getByPlaceholderText("you@business.co.tz"), { target: { value: "not-an-email" } });
    fireEvent.click(screen.getByRole("button", { name: "Send Reset Link" }));

    await waitFor(() => expect(screen.getByText("Enter a valid email address.")).toBeInTheDocument());
    expect(resetPasswordForEmail).not.toHaveBeenCalled();
  });
});
