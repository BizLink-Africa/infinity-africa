import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ApiKey } from "@/lib/portal/types";

const key: ApiKey = {
  id: "key-1",
  merchant_id: "merchant-1",
  name: "Website checkout",
  environment: "sandbox",
  key_prefix: "inf_sandbox_abc123",
  key_last4: "9zk1",
  scopes: ["collections:write", "collections:read"],
  status: "active",
  ip_whitelist_enabled: false,
  continue_without_ip_whitelist: true,
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
const renameApiKey = vi.fn();
const getMyMerchant = vi.fn();

vi.mock("@/lib/portal/api", () => ({
  listApiKeys: (...args: unknown[]) => listApiKeys(...args),
  createApiKey: (...args: unknown[]) => createApiKey(...args),
  revokeApiKey: (...args: unknown[]) => revokeApiKey(...args),
  rotateApiKey: (...args: unknown[]) => rotateApiKey(...args),
  renameApiKey: (...args: unknown[]) => renameApiKey(...args),
  getMyMerchant: (...args: unknown[]) => getMyMerchant(...args),
}));

describe("ApiKeysView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listApiKeys.mockResolvedValue([key]);
    getMyMerchant.mockResolvedValue({
      status: "active",
      kyc_status: "verified",
      api_access_suspended: false,
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

  it("blocks generating a Live key and explains why when the merchant isn't approved yet", async () => {
    getMyMerchant.mockResolvedValue({
      status: "pending",
      kyc_status: "unverified",
      api_access_suspended: false,
    });
    const { ApiKeysView } = await import("./api-keys-view");
    render(<ApiKeysView />);

    fireEvent.click(await screen.findByRole("button", { name: "Live" }));
    await screen.findByText(/Production API keys are available after your business account is approved/);

    const triggerButtons = screen.getAllByRole("button", { name: "Generate API Key" });
    fireEvent.click(triggerButtons[0]);

    const submitButton = (await screen.findAllByRole("button", { name: "Generate API Key" })).find(
      (button) => button.getAttribute("type") === "submit",
    );
    expect(submitButton).toBeDisabled();
  });

  it("blocks generating any key (sandbox or live) when API access is suspended", async () => {
    getMyMerchant.mockResolvedValue({
      status: "active",
      kyc_status: "verified",
      api_access_suspended: true,
    });
    const { ApiKeysView } = await import("./api-keys-view");
    render(<ApiKeysView />);

    await screen.findByText(/API access is currently suspended/);

    const triggerButtons = screen.getAllByRole("button", { name: "Generate API Key" });
    fireEvent.click(triggerButtons[0]);

    const submitButton = (await screen.findAllByRole("button", { name: "Generate API Key" })).find(
      (button) => button.getAttribute("type") === "submit",
    );
    expect(submitButton).toBeDisabled();
  });

  it("defaults to 'continue without IP whitelisting' and passes the merchant's choice through to createApiKey", async () => {
    createApiKey.mockResolvedValue({ key: { ...key, id: "key-2" }, plaintext_key: "inf_sandbox_newkey123" });
    const { ApiKeysView } = await import("./api-keys-view");
    render(<ApiKeysView />);

    // Wait for the key list to settle first — otherwise the trigger button
    // this test clicks can be the EmptyState's (0 sandbox keys, transient)
    // one instant and the table header's (1 sandbox key, from the mock)
    // the next, and fireEvent.click can land on a since-unmounted node.
    await screen.findByText("Website checkout");
    fireEvent.click(await screen.findByRole("button", { name: "Generate API Key" }));
    fireEvent.change(await screen.findByPlaceholderText("e.g. Website checkout integration"), {
      target: { value: "My integration" },
    });
    fireEvent.click(screen.getByLabelText(/Collections — create/));
    fireEvent.click(screen.getByRole("radio", { name: /Enable IP whitelisting/ }));

    const submitButton = (await screen.findAllByRole("button", { name: "Generate API Key" })).find(
      (button) => button.getAttribute("type") === "submit",
    )!;
    fireEvent.click(submitButton);

    await waitFor(() =>
      expect(createApiKey).toHaveBeenCalledWith(
        expect.objectContaining({ ip_whitelist_enabled: true, continue_without_ip_whitelist: false }),
      ),
    );
  });

  it("never writes the revealed secret to localStorage or sessionStorage", async () => {
    rotateApiKey.mockResolvedValue({
      key: { ...key, id: "key-2", status: "active" },
      plaintext_key: "inf_sandbox_newkey123",
    });
    const localSetItem = vi.spyOn(Storage.prototype, "setItem");
    const { ApiKeysView } = await import("./api-keys-view");
    render(<ApiKeysView />);

    fireEvent.click(await screen.findByRole("button", { name: "Rotate" }));
    await screen.findByText("inf_sandbox_newkey123");

    expect(localSetItem).not.toHaveBeenCalled();
    localSetItem.mockRestore();
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
