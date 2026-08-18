import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { UserRole } from "@infinity/shared";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { MerchantUser } from "@/lib/portal/types";

const existingUser: MerchantUser = {
  id: "row-1",
  user_id: "user-1",
  merchant_id: "merchant-1",
  full_name: "Amina Admin",
  email: "amina@merchant.co.tz",
  role: UserRole.MERCHANT_ADMIN,
  status: "active",
  created_at: "2026-08-01T10:00:00Z",
  updated_at: "2026-08-01T10:00:00Z",
};

const listMerchantUsers = vi.fn();
const createMerchantUser = vi.fn();

vi.mock("@/lib/portal/api", () => ({
  listMerchantUsers: (...args: unknown[]) => listMerchantUsers(...args),
  createMerchantUser: (...args: unknown[]) => createMerchantUser(...args),
  updateMerchantUser: vi.fn(),
  deactivateMerchantUser: vi.fn(),
}));

describe("UsersView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listMerchantUsers.mockResolvedValue([existingUser]);
  });

  it("shows the invited teammate's full name in the team table", async () => {
    const { UsersView } = await import("./users-view");
    render(<UsersView />);

    await waitFor(() => expect(screen.getByText("Amina Admin")).toBeInTheDocument());
  });

  it("shows an Add User button that opens the invite form", async () => {
    const { UsersView } = await import("./users-view");
    render(<UsersView />);

    await waitFor(() => expect(screen.getByText("Amina Admin")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Add User" }));

    expect(screen.getByPlaceholderText("e.g. David Komba")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("e.g. david@merchant.co.tz")).toBeInTheDocument();
  });

  it("requires a full name before Send Invite can be submitted", async () => {
    const { UsersView } = await import("./users-view");
    render(<UsersView />);

    await waitFor(() => expect(screen.getByText("Amina Admin")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Add User" }));

    fireEvent.change(screen.getByPlaceholderText("e.g. david@merchant.co.tz"), {
      target: { value: "david@merchant.co.tz" },
    });

    // No full name entered — the submit button stays disabled and the
    // create call never fires.
    expect(screen.getByRole("button", { name: "Send Invite" })).toBeDisabled();
    expect(createMerchantUser).not.toHaveBeenCalled();
  });

  it("invites a new teammate once a full name and email are provided", async () => {
    createMerchantUser.mockResolvedValue({
      id: "row-2",
      user_id: "user-2",
      merchant_id: "merchant-1",
      full_name: "David Komba",
      email: "david@merchant.co.tz",
      role: "MERCHANT_STAFF",
      status: "invited",
      created_at: "2026-08-02T10:00:00Z",
      updated_at: "2026-08-02T10:00:00Z",
    });

    const { UsersView } = await import("./users-view");
    render(<UsersView />);

    await waitFor(() => expect(screen.getByText("Amina Admin")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Add User" }));

    fireEvent.change(screen.getByPlaceholderText("e.g. David Komba"), { target: { value: "David Komba" } });
    fireEvent.change(screen.getByPlaceholderText("e.g. david@merchant.co.tz"), {
      target: { value: "david@merchant.co.tz" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send Invite" }));

    await waitFor(() =>
      expect(createMerchantUser).toHaveBeenCalledWith({
        full_name: "David Komba",
        email: "david@merchant.co.tz",
        role: "MERCHANT_STAFF",
      }),
    );
    await waitFor(() => expect(screen.getByText("David Komba")).toBeInTheDocument());
  });
});
