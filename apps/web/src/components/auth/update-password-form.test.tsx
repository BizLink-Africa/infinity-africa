import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const signInWithPassword = vi.fn();
const updateUser = vi.fn();

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { signInWithPassword, updateUser },
  }),
}));

describe("UpdatePasswordForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    signInWithPassword.mockResolvedValue({ error: null });
    updateUser.mockResolvedValue({ error: null });
  });

  it("shows an Update Password button that calls Supabase Auth on submit", async () => {
    const { UpdatePasswordForm } = await import("./update-password-form");
    render(<UpdatePasswordForm email="merchant@example.com" source="supabase" />);

    fireEvent.change(screen.getByPlaceholderText("Enter current password"), { target: { value: "OldPass123!" } });
    fireEvent.change(screen.getByPlaceholderText("Enter new password"), { target: { value: "NewPass456!" } });
    fireEvent.change(screen.getByPlaceholderText("Re-enter new password"), { target: { value: "NewPass456!" } });

    fireEvent.click(screen.getByRole("button", { name: "Update Password" }));

    await waitFor(() =>
      expect(signInWithPassword).toHaveBeenCalledWith({ email: "merchant@example.com", password: "OldPass123!" }),
    );
    await waitFor(() => expect(updateUser).toHaveBeenCalledWith({ password: "NewPass456!" }));
    await waitFor(() => expect(screen.getByText("Your password has been updated.")).toBeInTheDocument());
  });

  it("rejects a weak new password without calling Supabase", async () => {
    const { UpdatePasswordForm } = await import("./update-password-form");
    render(<UpdatePasswordForm email="merchant@example.com" source="supabase" />);

    fireEvent.change(screen.getByPlaceholderText("Enter current password"), { target: { value: "OldPass123!" } });
    fireEvent.change(screen.getByPlaceholderText("Enter new password"), { target: { value: "weak" } });
    fireEvent.change(screen.getByPlaceholderText("Re-enter new password"), { target: { value: "weak" } });

    fireEvent.click(screen.getByRole("button", { name: "Update Password" }));

    await waitFor(() => expect(screen.getByText(/Password must be at least 8 characters/)).toBeInTheDocument());
    expect(signInWithPassword).not.toHaveBeenCalled();
    expect(updateUser).not.toHaveBeenCalled();
  });

  it("does not render a password form for mock-authenticated accounts", async () => {
    const { UpdatePasswordForm } = await import("./update-password-form");
    render(<UpdatePasswordForm email="merchant@example.com" source="mock" />);

    expect(screen.queryByRole("button", { name: "Update Password" })).not.toBeInTheDocument();
    expect(screen.getByText(/local mock authentication/i)).toBeInTheDocument();
  });
});
