import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ApiKey } from "@/lib/portal/types";

const key: ApiKey = {
  id: "key-1",
  merchant_id: "merchant-1",
  name: "Website checkout",
  environment: "sandbox",
  key_prefix: "inf_sandbox_abc123",
  scopes: ["collections:write", "collections:read"],
  status: "active",
  last_used_at: null,
  last_used_ip: null,
  revoked_at: null,
  created_at: "2026-08-01T10:00:00Z",
  updated_at: "2026-08-01T10:00:00Z",
};

const listApiKeys = vi.fn();
const createApiKey = vi.fn();
const revokeApiKey = vi.fn();
const rotateApiKey = vi.fn();
const getMyMerchant = vi.fn();

vi.mock("@/lib/portal/api", () => ({
  listApiKeys: (...args: unknown[]) => listApiKeys(...args),
  createApiKey: (...args: unknown[]) => createApiKey(...args),
  revokeApiKey: (...args: unknown[]) => revokeApiKey(...args),
  rotateApiKey: (...args: unknown[]) => rotateApiKey(...args),
  getMyMerchant: (...args: unknown[]) => getMyMerchant(...args),
}));

describe("ApiKeysView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listApiKeys.mockResolvedValue([key]);
    getMyMerchant.mockResolvedValue({
      status: "active",
      kyc_status: "verified",
      api_production_enabled: true,
    });
  });

  it("always shows the never-expose-secrets warning", async () => {
    const { ApiKeysView } = await import("./api-keys-view");
    render(<ApiKeysView />);

    expect(
      screen.getByText(/Use secret keys only on your backend\./),
    ).toBeInTheDocument();
    expect(screen.getByText(/Never expose them in\s*frontend or mobile apps/)).toBeInTheDocument();
  });

  it("shows a Rotate button alongside Revoke for an active key", async () => {
    const { ApiKeysView } = await import("./api-keys-view");
    render(<ApiKeysView />);

    expect(await screen.findByRole("button", { name: "Rotate" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Revoke" })).toBeInTheDocument();
  });

  it("rotating a key reveals the new plaintext key and marks the old one revoked", async () => {
    rotateApiKey.mockResolvedValue({
      key: { ...key, id: "key-2", status: "active" },
      plaintext_key: "inf_sandbox_newkey123",
    });
    const { ApiKeysView } = await import("./api-keys-view");
    render(<ApiKeysView />);

    fireEvent.click(await screen.findByRole("button", { name: "Rotate" }));

    await waitFor(() => expect(rotateApiKey).toHaveBeenCalledWith("key-1"));
    expect(await screen.findByText("inf_sandbox_newkey123")).toBeInTheDocument();
    expect(screen.getByText("Copy this key now. You will not be able to view it again.")).toBeInTheDocument();
  });

  it("blocks generating a Live key and explains why when production access isn't enabled", async () => {
    getMyMerchant.mockResolvedValue({
      status: "active",
      kyc_status: "verified",
      api_production_enabled: false,
    });
    const { ApiKeysView } = await import("./api-keys-view");
    render(<ApiKeysView />);

    fireEvent.click(await screen.findByRole("button", { name: "Live" }));
    await screen.findByText(/Production API access isn.t enabled yet/);

    const triggerButtons = screen.getAllByRole("button", { name: "Generate API Key" });
    fireEvent.click(triggerButtons[0]);

    const submitButton = (await screen.findAllByRole("button", { name: "Generate API Key" })).find(
      (button) => button.getAttribute("type") === "submit",
    );
    expect(submitButton).toBeDisabled();
  });

  it("does not show Rotate/Revoke for an already-revoked key", async () => {
    listApiKeys.mockResolvedValue([{ ...key, status: "revoked" }]);
    const { ApiKeysView } = await import("./api-keys-view");
    render(<ApiKeysView />);

    await waitFor(() => expect(listApiKeys).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: "Rotate" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Revoke" })).not.toBeInTheDocument();
  });
});
