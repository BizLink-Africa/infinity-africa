import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const updateUser = vi.fn();
const push = vi.fn();
const acceptMyInvite = vi.fn();

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { updateUser },
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

vi.mock("@/lib/portal/api", () => ({
  acceptMyInvite: (...args: unknown[]) => acceptMyInvite(...args),
}));

const INVALID_INVITE_MESSAGE = "Invitation expired or invalid. Please ask your merchant admin to send a new invitation.";

describe("AcceptInviteForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    updateUser.mockResolvedValue({ error: null });
    acceptMyInvite.mockResolvedValue({ id: "row-1", status: "active" });
    window.location.hash = "";
  });

  it("renders new-password fields and a Set Password button", async () => {
    const { AcceptInviteForm } = await import("./accept-invite-form");
    render(<AcceptInviteForm />);

    expect(screen.getByLabelText("New Password")).toBeInTheDocument();
    expect(screen.getByLabelText("Confirm Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Set Password" })).toBeInTheDocument();
  });

  it("calls Supabase updateUser, then links the staff member to their merchant, then shows success", async () => {
    const { AcceptInviteForm } = await import("./accept-invite-form");
    render(<AcceptInviteForm />);

    fireEvent.change(screen.getByLabelText("New Password"), { target: { value: "NewPass456!" } });
    fireEvent.change(screen.getByLabelText("Confirm Password"), { target: { value: "NewPass456!" } });
    fireEvent.click(screen.getByRole("button", { name: "Set Password" }));

    await waitFor(() => expect(updateUser).toHaveBeenCalledWith({ password: "NewPass456!" }));
    await waitFor(() => expect(acceptMyInvite).toHaveBeenCalledTimes(1));
    expect(await screen.findByText(/Merchant Portal/i)).toBeInTheDocument();
  });

  it("redirects to the merchant portal (not login) after successfully accepting", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { AcceptInviteForm } = await import("./accept-invite-form");
    render(<AcceptInviteForm portalPath="/merchant/overview" />);

    fireEvent.change(screen.getByLabelText("New Password"), { target: { value: "NewPass456!" } });
    fireEvent.change(screen.getByLabelText("Confirm Password"), { target: { value: "NewPass456!" } });
    fireEvent.click(screen.getByRole("button", { name: "Set Password" }));

    await vi.waitFor(() => expect(acceptMyInvite).toHaveBeenCalledTimes(1));
    await vi.advanceTimersByTimeAsync(1500);

    expect(push).toHaveBeenCalledWith("/merchant/overview");
    vi.useRealTimers();
  });

  it("rejects mismatched passwords without calling Supabase", async () => {
    const { AcceptInviteForm } = await import("./accept-invite-form");
    render(<AcceptInviteForm />);

    fireEvent.change(screen.getByLabelText("New Password"), { target: { value: "NewPass456!" } });
    fireEvent.change(screen.getByLabelText("Confirm Password"), { target: { value: "Different456!" } });
    fireEvent.click(screen.getByRole("button", { name: "Set Password" }));

    await waitFor(() => expect(screen.getByText("Passwords do not match.")).toBeInTheDocument());
    expect(updateUser).not.toHaveBeenCalled();
  });

  it("does not ask for an old/current password anywhere on the form", async () => {
    const { AcceptInviteForm } = await import("./accept-invite-form");
    render(<AcceptInviteForm />);

    expect(screen.queryByLabelText(/current password/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/old password/i)).not.toBeInTheDocument();
  });

  it("shows a friendly expired/invalid message, never redirecting to login automatically, when the link carries an error hash", async () => {
    window.location.hash = "#error=access_denied&error_description=Email+link+is+invalid+or+has+expired";
    const { AcceptInviteForm } = await import("./accept-invite-form");
    render(<AcceptInviteForm />);

    expect(await screen.findByText(INVALID_INVITE_MESSAGE)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to login" })).toBeInTheDocument();
    expect(screen.queryByLabelText("New Password")).not.toBeInTheDocument();
    expect(updateUser).not.toHaveBeenCalled();
  });

  it("shows the same friendly message when updateUser itself reports a dead/expired session", async () => {
    updateUser.mockResolvedValue({ error: { message: "Auth session missing" } });
    const { AcceptInviteForm } = await import("./accept-invite-form");
    render(<AcceptInviteForm />);

    fireEvent.change(screen.getByLabelText("New Password"), { target: { value: "NewPass456!" } });
    fireEvent.change(screen.getByLabelText("Confirm Password"), { target: { value: "NewPass456!" } });
    fireEvent.click(screen.getByRole("button", { name: "Set Password" }));

    expect(await screen.findByText(INVALID_INVITE_MESSAGE)).toBeInTheDocument();
    expect(acceptMyInvite).not.toHaveBeenCalled();
  });

  it("shows a recoverable error, not a silent failure, when the password is set but linking the staff account fails", async () => {
    acceptMyInvite.mockRejectedValue(new Error("No pending invitation found for your account"));
    const { AcceptInviteForm } = await import("./accept-invite-form");
    render(<AcceptInviteForm />);

    fireEvent.change(screen.getByLabelText("New Password"), { target: { value: "NewPass456!" } });
    fireEvent.change(screen.getByLabelText("Confirm Password"), { target: { value: "NewPass456!" } });
    fireEvent.click(screen.getByRole("button", { name: "Set Password" }));

    await waitFor(() => expect(updateUser).toHaveBeenCalled());
    expect(await screen.findByText(/Your password was set/i)).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });
});
