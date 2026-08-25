import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// requireCurrentUser/getCurrentUser would redirect an unauthenticated
// visitor to /merchant/login — the exact bug this page exists to fix. If
// the page ever starts calling either of these, these mocks throw, failing
// the test loudly instead of silently reintroducing the redirect-before-
// password-setup bug.
const requireCurrentUser = vi.fn(() => {
  throw new Error("requireCurrentUser must never be called on the invite-accept page");
});
const getCurrentUser = vi.fn(() => {
  throw new Error("getCurrentUser must never be called on the invite-accept page");
});

vi.mock("@/lib/auth/current-user", () => ({ requireCurrentUser, getCurrentUser }));

vi.mock("@/lib/portal/api", () => ({ acceptMyInvite: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

describe("MerchantInviteAcceptPage", () => {
  it("renders the set-password form without any existing session or auth guard", async () => {
    const { default: MerchantInviteAcceptPage } = await import("./page");
    render(<MerchantInviteAcceptPage />);

    expect(screen.getByRole("heading", { name: "Set your password" })).toBeInTheDocument();
    expect(screen.getByLabelText("New Password")).toBeInTheDocument();
    expect(screen.getByLabelText("Confirm Password")).toBeInTheDocument();
    expect(requireCurrentUser).not.toHaveBeenCalled();
    expect(getCurrentUser).not.toHaveBeenCalled();
  });
});
